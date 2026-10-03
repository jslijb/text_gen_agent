"""sieve 抓取 API 客户端（https://scrape.usesieve.com）

与项目其它外部服务保持同一套约定：
- HTTP 客户端复用已有依赖（httpx，见 services/video_service.py），不新增第二个客户端库；
- 密钥只从环境变量取（`SIEVE_API_KEY`，落在 backend/.env，随 docker env_file 注入
  backend / worker / beat 三个容器），**永不出现在日志、返回值或前端**；
- 未配置密钥时整个模块以 `SieveNotConfigured` 优雅失败，其它功能完全不受影响。

契约要点（照 sieve 官方文档实现，逐条对应）：
1. 每个请求带 `Authorization: Bearer $SIEVE_API_KEY`，服务端专用。
2. `POST /api/scrapes` 创建 run：202 → `{status: queued, session_id, poll}`。
   **该接口没有幂等键，且被接受即扣费。超时/网络错误一律不自动重试**
   （第一次调用可能已经成功）——抛 `SieveAmbiguousRequest` 交给上层决定。
   只有 429 与 5xx 可以安全重试（这两种情况确定没有创建 run）。
3. 轮询 `GET /api/scrapes/<session_id>`：起始 5s，退避到约 30s，没有短超时。
   status 只有 running（续跑）/ done（读 summary、files[]、schema_conformance、result）/
   refused（终态，refusal.code 说明原因）三种；其它值视为错误。
4. `files[].url` 是相对地址，取件时要拼 base URL 并带 Bearer 头。
5. 追问走 `POST /api/scrapes/<session_id>/messages`。必须先记录 turn，
   再轮询到 status=done **且 turns 已推进**，否则会读到上一轮的答案。409 = 有 turn 在飞。
6. `output_schema` 校验结果看 `schema_conformance.status`：pass / partial / fail /
   not_checkable / no_artifact。**fail 不能当干净数据交付**（见 `describe_conformance`）。

本模块只做 HTTP 与状态机，不碰数据库：session_id 的落库、任务的续跑都在
`app/tasks/sieve_tasks.py`（复用 Celery + SQLAlchemy 的既有套路）。
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Iterable

import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)

# 轮询节奏：5s 起步，退避到约 30s。run 通常要几分钟，不设短超时。
POLL_INITIAL_DELAY = 5.0
POLL_MAX_DELAY = 30.0
# 单次 HTTP 请求超时（秒）。给足时间，避免"看起来卡住其实是超时太短"。
DEFAULT_TIMEOUT = 60.0
# 创建 run 时可能带文档上传，给更宽的超时
CREATE_TIMEOUT = 120.0
# 429 / 5xx 的安全重试次数与基础退避
SAFE_RETRY_ATTEMPTS = 3
SAFE_RETRY_BASE_DELAY = 2.0
# output_schema 上限 32KB
OUTPUT_SCHEMA_MAX_BYTES = 32 * 1024

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_REFUSED = "refused"

# GET /api/scrapes/<id> 的合法 status。queued 是创建响应的取值，
# 出现在轮询里同样按"还在跑"处理（否则刚创建就被判成未知状态）。
_RUNNING_STATUSES = {STATUS_RUNNING, STATUS_QUEUED}
_TERMINAL_STATUSES = {STATUS_DONE, STATUS_REFUSED}
KNOWN_STATUSES = _RUNNING_STATUSES | _TERMINAL_STATUSES

VALID_COMPLIANCE_MODES = ("conservative", "regular", "yolo")
VALID_TABLE_SHAPES = ("long", "wide")
DEFAULT_COMPLIANCE_MODE = "regular"


# --------------------------------------------------------------------------- #
# 异常：一个 HTTP 状态码一个类型，上层不用再解析 status_code
# --------------------------------------------------------------------------- #
class SieveError(Exception):
    """sieve 调用失败的基类。"""


class SieveNotConfigured(SieveError):
    """SIEVE_API_KEY 未配置——抓取功能整体关闭。"""


class SieveRequestRejected(SieveError):
    """400：请求本身有问题，改请求，不要重试。"""


class SieveAuthError(SieveError):
    """401：密钥缺失/被吊销，需要用户处理。"""


class SieveInsufficientCredits(SieveError):
    """402：额度不足（GET /api/me/credits 可看 plan/limit/used/remaining）。"""


class SieveNotFound(SieveError):
    """404：不存在或不属于本账号。"""


class SieveRateLimited(SieveError):
    """429：等 Retry-After 后再来。"""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class SieveServerError(SieveError):
    """5xx：服务端故障，GET 可退避重试，不影响本项目的其它功能。"""


class SieveAmbiguousRequest(SieveError):
    """POST 超时/网络错误：**第一次调用可能已经成功**，绝不自动重试。"""


class SieveTurnInFlight(SieveError):
    """409：已有一个 turn 在飞，等一会再发同一条追问。"""


class SieveRefused(SieveError):
    """refused：终态，run 从未真正开始。"""

    def __init__(self, message: str, refusal: dict | None = None):
        super().__init__(message)
        self.refusal = refusal or {}

    @property
    def code(self) -> str:
        return str(self.refusal.get("code") or "")

    @property
    def is_quota(self) -> bool:
        """额度类拒绝（refusal.quota）——与其它拒绝区分，便于前端提示充值/提额。"""
        return self.code == "quota"


class SieveUnknownStatus(SieveError):
    """轮询拿到契约外的 status：当成错误处理，不猜测。"""


class SieveTimeout(SieveError):
    """调用方给的等待预算用完了，run 其实还在跑——落库保持 running，稍后接着轮询。"""


# --------------------------------------------------------------------------- #
# 纯函数：状态与校验结论
# --------------------------------------------------------------------------- #
def status_of(payload: dict) -> str:
    """取 run 的 status（缺字段按未知处理）。"""
    return str((payload or {}).get("status") or "")


def classify_status(payload: dict) -> str:
    """把 payload 归一化成 running / done / refused 三类，其它一律报错。

    契约：「running」→ keep polling；「done」→ 读结果；「refused」→ 终态；
    其它值视为错误。`queued` 是创建接口的取值，出现在轮询里等同 running。
    """
    status = status_of(payload)
    if status in _RUNNING_STATUSES:
        return STATUS_RUNNING
    if status in _TERMINAL_STATUSES:
        return status
    raise SieveUnknownStatus(f"sieve 返回了未知的 run status: {status!r}（契约只有 running/done/refused）")


def describe_conformance(conformance: dict | None) -> dict:
    """把 schema_conformance 翻译成「能不能当干净数据交付」。

    返回 {status, ok, warning}：
    - pass             → 干净
    - partial          → 无违规，但声明的列有缺失，交付时要说明
    - fail             → 修复后仍不符合 schema，**禁止当干净数据**
    - not_checkable / no_artifact → 没有可校验的产物
    """
    status = str((conformance or {}).get("status") or "not_checkable")
    if status == "pass":
        return {"status": status, "ok": True, "warning": None}
    if status == "partial":
        return {"status": status, "ok": True, "warning": "部分声明的列缺失（schema_conformance=partial）"}
    if status == "fail":
        return {
            "status": status,
            "ok": False,
            "warning": "schema 修复后仍不符合 output_schema，不能作为干净数据使用（schema_conformance=fail）",
        }
    if status in ("not_checkable", "no_artifact"):
        return {"status": status, "ok": False, "warning": f"没有可校验的产物（schema_conformance={status}）"}
    return {"status": status, "ok": False, "warning": f"未知的 schema_conformance: {status!r}"}


def files_with_urls(files: Iterable[dict] | None, base_url: str) -> list[dict]:
    """files[].url 是相对地址，取件前拼上 base URL。"""
    root = (base_url or "").rstrip("/")
    out = []
    for f in files or []:
        item = dict(f or {})
        url = item.get("url")
        if url and not str(url).startswith(("http://", "https://")):
            item["url"] = f"{root}/{str(url).lstrip('/')}"
        out.append(item)
    return out


def validate_output_schema(output_schema: dict | None) -> None:
    """output_schema 必须 ≤32KB（按序列化后的 UTF-8 字节数算）。"""
    if output_schema is None:
        return
    size = len(json.dumps(output_schema, ensure_ascii=False).encode("utf-8"))
    if size > OUTPUT_SCHEMA_MAX_BYTES:
        raise SieveRequestRejected(
            f"output_schema 过大（{size} 字节 > {OUTPUT_SCHEMA_MAX_BYTES} 字节上限）"
        )


# --------------------------------------------------------------------------- #
# 客户端
# --------------------------------------------------------------------------- #
class SieveClient:
    """sieve 抓取 API 客户端。

    Args:
        api_key: 不传则用 settings.SIEVE_API_KEY（即 backend/.env 里的值）。
        base_url: 不传则用 settings.SIEVE_BASE_URL。
        transport: httpx transport。测试用 `httpx.MockTransport(handler)`
                   把录制响应放在**HTTP 边界**，被测的仍是这套真实代码。
        sleep: 便于测试把退避等待加速。
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] | None = None,
    ):
        self.api_key = settings.SIEVE_API_KEY if api_key is None else api_key
        self.base_url = (base_url or settings.SIEVE_BASE_URL or "").rstrip("/")
        self._sleep = sleep or time.sleep
        self._client = httpx.Client(transport=transport, follow_redirects=False)

    # -- 基础设施 ---------------------------------------------------------- #
    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _require_config(self) -> None:
        if not self.configured:
            raise SieveNotConfigured(
                "未配置 SIEVE_API_KEY：抓取功能已关闭（在 backend/.env 中写入 SIEVE_API_KEY，或跑一次 "
                "backend/scripts/sieve_device_login.py 完成设备登录授权）"
            )

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

    def file_url(self, relative_or_absolute: str) -> str:
        """补全 files[].url（sieve 返回的是相对地址）。"""
        url = str(relative_or_absolute or "")
        if url.startswith(("http://", "https://")):
            return url
        return f"{self.base_url}/{url.lstrip('/')}"

    # -- 统一请求入口 ------------------------------------------------------ #
    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        data: dict | None = None,
        files: dict | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retry_safe: bool = False,
    ) -> tuple[int, dict]:
        """发一个请求，把状态码映射成异常，并按契约决定能不能重试。

        Args:
            retry_safe: 幂等（GET）。网络错误/超时可安全重试。
                POST 一律 False —— 创建接口没有幂等键、被接受即扣费，
                超时只能抛 `SieveAmbiguousRequest`，不能自动再发一次。

        Returns:
            (status_code, payload)

        Raises:
            各 Sieve* 异常（见模块顶部契约）。
        """
        self._require_config()
        url = f"{self.base_url}{path}"
        attempts = 0
        delay = SAFE_RETRY_BASE_DELAY
        last_error: Exception | None = None

        while attempts < SAFE_RETRY_ATTEMPTS:
            attempts += 1
            try:
                response = self._client.request(
                    method.upper(),
                    url,
                    headers=self._headers(),
                    json=json_body,
                    data=data,
                    files=files,
                    timeout=timeout,
                )
            except (httpx.TimeoutException, httpx.TransportError) as e:
                if not retry_safe:
                    # POST：第一次可能已经成功（run 已创建并扣费），绝不自动重试。
                    raise SieveAmbiguousRequest(
                        f"{method.upper()} {path} 超时/网络错误（{type(e).__name__}: {e}），"
                        "无法确认是否已创建 run，已放弃自动重试"
                    ) from e
                last_error = e
                logger.warning(f"sieve {method.upper()} {path} 网络错误（第 {attempts} 次）: {e}")
                if attempts < SAFE_RETRY_ATTEMPTS:
                    self._sleep(delay)
                    delay = min(delay * 2, POLL_MAX_DELAY)
                continue
            except httpx.HTTPError as e:  # 其它 httpx 层错误，同样不做自动重试判断
                if not retry_safe:
                    raise SieveAmbiguousRequest(
                        f"{method.upper()} {path} 请求失败（{type(e).__name__}: {e}），已放弃自动重试"
                    ) from e
                last_error = e
                if attempts < SAFE_RETRY_ATTEMPTS:
                    self._sleep(delay)
                    delay = min(delay * 2, POLL_MAX_DELAY)
                continue

            code = response.status_code
            payload = self._parse_body(response)

            if 200 <= code < 300:
                return code, payload

            if code == 429:
                retry_after = self._retry_after(response)
                if attempts < SAFE_RETRY_ATTEMPTS:
                    wait_for = retry_after if retry_after is not None else delay
                    logger.warning(f"sieve 限流 429，{wait_for}s 后重试（第 {attempts} 次）")
                    self._sleep(wait_for)
                    delay = min(delay * 2, POLL_MAX_DELAY)
                    continue
                raise SieveRateLimited(
                    f"sieve 限流（429），请等待 {retry_after if retry_after is not None else 'Retry-After'} 后重试",
                    retry_after=retry_after,
                )

            if 500 <= code < 600:
                # 5xx 确定没有创建 run，可以安全重试。
                last_error = SieveServerError(f"sieve 服务端错误 {code}: {self._short(payload)}")
                logger.warning(f"sieve {code}（第 {attempts} 次）: {self._short(payload)}")
                if attempts < SAFE_RETRY_ATTEMPTS:
                    self._sleep(delay)
                    delay = min(delay * 2, POLL_MAX_DELAY)
                    continue
                raise last_error

            raise self._map_error(code, payload)

        raise last_error or SieveServerError("sieve 请求失败")

    def _parse_body(self, response: httpx.Response) -> dict:
        try:
            body = response.json()
        except ValueError:
            return {"raw": response.text[:500]}
        return body if isinstance(body, dict) else {"data": body}

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        raw = response.headers.get("Retry-After")
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _short(payload: dict) -> str:
        if "error" in payload:
            return str(payload["error"])[:300]
        return json.dumps(payload, ensure_ascii=False)[:300]

    def _map_error(self, code: int, payload: dict) -> SieveError:
        detail = self._short(payload)
        if code == 400:
            return SieveRequestRejected(f"sieve 拒绝了请求（400）: {detail}")
        if code == 401:
            return SieveAuthError(f"sieve 密钥缺失或已吊销（401）: {detail}")
        if code == 402:
            return SieveInsufficientCredits(f"sieve 额度不足（402）: {detail}")
        if code == 404:
            return SieveNotFound(f"sieve 未找到该资源（404）: {detail}")
        if code == 409:
            return SieveTurnInFlight(f"sieve 已有 turn 在飞行中（409）: {detail}")
        return SieveError(f"sieve 返回 {code}: {detail}")

    # -- 业务接口 ---------------------------------------------------------- #
    def _run_body(
        self,
        instruction: str,
        target_urls: list[str] | None = None,
        fields: list | None = None,
        schema: dict | None = None,
        output_schema: dict | None = None,
        table_shape: str | None = None,
        compliance_mode: str | None = None,
    ) -> dict:
        if not (instruction and instruction.strip()):
            raise SieveRequestRejected("instruction 必填：用自然语言描述要抓什么")
        mode = compliance_mode or DEFAULT_COMPLIANCE_MODE
        if mode not in VALID_COMPLIANCE_MODES:
            raise SieveRequestRejected(
                f"compliance_mode 非法: {mode!r}，合法值 {VALID_COMPLIANCE_MODES}"
            )
        if table_shape is not None and table_shape not in VALID_TABLE_SHAPES:
            raise SieveRequestRejected(
                f"table_shape 非法: {table_shape!r}，合法值 {VALID_TABLE_SHAPES}"
            )
        validate_output_schema(output_schema)

        body: dict[str, Any] = {"instruction": instruction.strip(), "compliance_mode": mode}
        if target_urls:
            urls = list(target_urls)
            bad = [u for u in urls if not str(u).startswith(("http://", "https://"))]
            if bad:
                raise SieveRequestRejected(f"target_urls 必须是公开的 http(s) 地址，收到: {bad}")
            body["target_urls"] = urls
        if fields:
            body["fields"] = list(fields)
        if schema:
            body["schema"] = schema
        if output_schema:
            body["output_schema"] = output_schema
        if table_shape:
            body["table_shape"] = table_shape
        return body

    def start_scrape(
        self,
        instruction: str,
        target_urls: list[str] | None = None,
        fields: list | None = None,
        schema: dict | None = None,
        output_schema: dict | None = None,
        table_shape: str | None = None,
        compliance_mode: str | None = None,
        file_path: str | Path | None = None,
    ) -> dict:
        """POST /api/scrapes —— 创建一次抓取。

        Returns: 服务端 payload（含 session_id / poll）；调用方必须**先落库 session_id**
                 再去做任何别的事，否则崩溃后会重复创建 run（重复扣费）。

        Raises: SieveAmbiguousRequest（超时/网络错误，可能已创建，别重试）。
        """
        body = self._run_body(
            instruction, target_urls, fields, schema, output_schema, table_shape, compliance_mode
        )
        if file_path is None:
            code, payload = self._request(
                "POST", "/api/scrapes", json_body=body, timeout=CREATE_TIMEOUT
            )
        else:
            path = Path(file_path)
            # multipart：复杂字段以 JSON 字符串传，文件放 "file" 字段
            form = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                    for k, v in body.items()}
            with open(path, "rb") as fh:
                files = {"file": (path.name, fh.read(), "application/octet-stream")}
            code, payload = self._request(
                "POST", "/api/scrapes", data=form, files=files, timeout=CREATE_TIMEOUT
            )

        if code != 202:
            raise SieveServerError(f"创建 run 返回了意外状态码 {code}: {self._short(payload)}")
        if not payload.get("session_id"):
            raise SieveServerError(f"创建 run 的响应缺少 session_id: {self._short(payload)}")
        logger.info(
            f"sieve run 已入队: session_id={payload.get('session_id')} "
            f"instruction_len={len(body['instruction'])} urls={len(body.get('target_urls') or [])}"
        )
        return payload

    def get_scrape(self, session_id: str) -> dict:
        """GET /api/scrapes/<session_id>（幂等，网络错误可退避重试）。"""
        _, payload = self._request("GET", f"/api/scrapes/{session_id}", retry_safe=True, timeout=DEFAULT_TIMEOUT)
        status = status_of(payload)
        logger.info(f"sieve run 状态: session_id={session_id} status={status}")
        return payload

    def send_message(self, session_id: str, **kwargs) -> dict:
        """POST /api/scrapes/<session_id>/messages —— 追问（body 字段与创建一致）。

        Raises: SieveTurnInFlight（409，等一会再发同一条）。
        """
        body = self._run_body(
            kwargs.get("instruction", ""),
            kwargs.get("target_urls"),
            kwargs.get("fields"),
            kwargs.get("schema"),
            kwargs.get("output_schema"),
            kwargs.get("table_shape"),
            kwargs.get("compliance_mode"),
        )
        _, payload = self._request(
            "POST", f"/api/scrapes/{session_id}/messages", json_body=body, timeout=CREATE_TIMEOUT
        )
        return payload

    def get_credits(self) -> dict:
        """GET /api/me/credits —— plan / limit / used / remaining。"""
        _, payload = self._request("GET", "/api/me/credits", retry_safe=True)
        return payload

    def download_file(self, relative_or_absolute_url: str, dest_path: str | Path) -> str:
        """取 files[] 里的交付文件（拼 base URL + Bearer 头）。"""
        url = self.file_url(relative_or_absolute_url)
        self._require_config()
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self._client.stream("GET", url, headers=self._headers(), timeout=DEFAULT_TIMEOUT) as resp:
            if resp.status_code != 200:
                raise self._map_error(resp.status_code, {"raw": resp.read()[:300].decode("utf-8", "ignore")})
            with open(dest, "wb") as fh:
                for chunk in resp.iter_bytes():
                    fh.write(chunk)
        logger.info(f"sieve 交付文件已下载: {dest} ({dest.stat().st_size} bytes)")
        return str(dest)

    # -- 轮询 -------------------------------------------------------------- #
    def wait_for_run(
        self,
        session_id: str,
        max_wait: float | None = None,
        on_status: Callable[[dict], None] | None = None,
    ) -> dict:
        """轮询到终态：done 返回 payload，refused 抛 SieveRefused。

        起始间隔 5s，每次退避 1.5 倍，上限约 30s。run 要几分钟甚至更久，
        max_wait=None（默认）表示不设总时限——由上层（Celery 任务）决定何时收手。
        """
        return self._poll(
            session_id, max_wait=max_wait, on_status=on_status, expect_turns_after=None
        )

    def wait_for_turn(
        self,
        session_id: str,
        previous_turns: int,
        max_wait: float | None = None,
        on_status: Callable[[dict], None] | None = None,
    ) -> dict:
        """等追问的结果：必须 status=done **且 turns 已推进**，否则会读到上一轮的答案。"""
        return self._poll(
            session_id, max_wait=max_wait, on_status=on_status, expect_turns_after=int(previous_turns)
        )

    def _poll(
        self,
        session_id: str,
        max_wait: float | None,
        on_status: Callable[[dict], None] | None,
        expect_turns_after: int | None,
    ) -> dict:
        started = time.monotonic()
        delay = POLL_INITIAL_DELAY
        while True:
            payload = self.get_scrape(session_id)
            if on_status is not None:
                on_status(payload)
            state = classify_status(payload)

            if state == STATUS_REFUSED:
                refusal = payload.get("refusal") or {}
                raise SieveRefused(
                    f"sieve 拒绝了本次抓取（refusal.code={refusal.get('code') or 'unknown'}）",
                    refusal=refusal,
                )
            if state == STATUS_DONE:
                if expect_turns_after is None:
                    return payload
                turns = payload.get("turns")
                try:
                    turns = int(turns)
                except (TypeError, ValueError):
                    raise SieveUnknownStatus(
                        f"等待追问结果时 turns 字段不可用: {turns!r}"
                    )
                if turns > expect_turns_after:
                    return payload
                # status 已是 done 但 turns 没动 —— 读到的是上一轮的答案，继续等。
                logger.info(
                    f"sieve 追问仍在处理中: session_id={session_id} "
                    f"turns={turns} 期望 > {expect_turns_after}"
                )

            if max_wait is not None and (time.monotonic() - started) >= max_wait:
                # run 还在跑，是我们自己的等待预算用完了 —— 不是失败，
                # 上层保留 running 状态，由补轮询任务接着等。
                raise SieveTimeout(
                    f"等待 run 超过 {max_wait}s，仍在运行中（session_id={session_id}，稍后可继续轮询）"
                )

            self._sleep(delay)
            delay = min(delay * 1.5, POLL_MAX_DELAY)


def get_client(**kwargs) -> SieveClient:
    """按项目惯例提供入口函数（同 hot_topic_fetcher.generate_* 的用法）。"""
    return SieveClient(**kwargs)
