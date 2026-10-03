#!/usr/bin/env python
"""sieve 设备登录（device code 流程）—— 一次性拿 SIEVE_API_KEY。

用法（仓库根目录，用项目自己的 conda 环境）：

    python backend/scripts/sieve_device_login.py                # 一步到底：申请 → 等你批准 → 写盘
    python backend/scripts/sieve_device_login.py --print-only   # 只申请并打印链接/代码，把 device_code 存进状态文件
    python backend/scripts/sieve_device_login.py --from-state   # 用状态文件里那个 code 继续轮询（进程被杀后可接着等）
    python backend/scripts/sieve_device_login.py --set-key      # 设备登录不可用时：粘贴 Settings → API keys 里手工建的 key

⚠️ 2026-09-25 实测：`scrape.usesieve.com` 当前拒给未鉴权请求——
   `POST /api/auth/device/code` 稳定返回 401 `{"error":"unauthorized"}`，
   所以设备登录这条路暂时走不通（服务端问题，不是脚本问题）。
   此时请用 `--set-key`：在网页版 Settings → API keys 建一把 key 粘进来。

流程：
1. `POST /api/auth/device/code` 申请 device_code + user_code；
2. **把 verification_uri_complete 和 user_code 显示给你**，由你在浏览器里
   登录/注册、核对代码一致、点 Approve —— 脚本永远不会替你打开链接或点批准；
3. 每 interval 秒 `POST /api/auth/device/token` 轮询（slow_down 加 5s，10 分钟过期）；
4. 把 api_key 原样写进 `backend/.env` 的 `SIEVE_API_KEY`，**不打印、不写日志、不入库**。

防钓鱼提示（2026 年已有攻击者自建 device code 流程骗用户批准）：
- 批准页会显示这个代码是从哪里申请的，以及你自己的位置；
- 批准页把工具名标为"自报"，因为它是脚本填的；
- 只批准**你自己发起**的代码。若你没跑过这个脚本，就别点 Approve。
- 代码 10 分钟过期、只能用一次；拿到 key 后状态文件会被删掉。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

# 让脚本在被直接执行时也能 import 到 app.*（backend/app/...）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.secret_store import env_file_path, has_secret, set_secret  # noqa: E402
from app.config.settings import settings  # noqa: E402

SECRET_NAME = "SIEVE_API_KEY"
HTTP_TIMEOUT = 60.0
# device_code 的暂存文件（logs/ 已被 gitignore）：只存一次性设备码，拿到 key 就删
DEFAULT_STATE_FILE = "logs/sieve_device_login.json"


def _mask(api_key: str) -> str:
    """只留前缀和长度，密钥本体不落任何输出。"""
    head = api_key[:6] if len(api_key) >= 6 else ""
    return f"{head}…（{len(api_key)} 位）"


def _print_instructions(verification: str, user_code: str, expires_in: int) -> None:
    print()
    print("=" * 68)
    print("请在浏览器里完成授权（脚本不会替你操作）")
    print("=" * 68)
    print(f"  1. 打开： {verification}")
    print(f"  2. 核对页面上的代码与下面一致： {user_code}")
    print(f"  3. 登录/注册后点 Approve（{expires_in // 60} 分钟内有效，只能用一次）")
    print()
    print("  ⚠️  只批准你自己发起的代码。你没跑过这个脚本的话，请不要点 Approve")
    print("      —— 攻击者会把自己的代码发给别人骗批准。")
    print("  ⚠️  批准页上的工具名是自报的（脚本填的），不要只凭工具名判断。")
    print()


def request_device_code(client: httpx.Client, base_url: str, client_name: str) -> dict:
    resp = client.post(f"{base_url}/api/auth/device/code", json={"client_name": client_name})
    if resp.status_code != 200:
        raise SystemExit(f"申请 device code 失败: HTTP {resp.status_code} {resp.text[:300]}")
    return resp.json()


def poll_token(
    client: httpx.Client,
    base_url: str,
    device_code: str,
    interval: float,
    expires_in: int,
    sleep=time.sleep,
    echo=print,
) -> str | None:
    """轮询直到拿到 api_key；access_denied / expired_token / 超时返回 None。

    契约：400 + {"error": ...} —— authorization_pending 继续等；slow_down 间隔 +5s；
    access_denied 用户拒绝；expired_token 从第 1 步重来。
    """
    deadline = time.monotonic() + expires_in
    while time.monotonic() < deadline:
        sleep(interval)
        resp = client.post(f"{base_url}/api/auth/device/token", json={"device_code": device_code})
        if resp.status_code == 200:
            return (resp.json() or {}).get("api_key")
        try:
            error = (resp.json() or {}).get("error")
        except ValueError:
            raise SystemExit(f"轮询返回非 JSON: HTTP {resp.status_code} {resp.text[:200]}")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5
            echo(f"  服务端要求放慢：轮询间隔改为 {interval:.0f}s")
            continue
        if error == "access_denied":
            echo("❌ 你在浏览器里拒绝了这次授权，已停止。")
            return None
        if error == "expired_token":
            echo("⌛ 代码已过期（10 分钟）。重新执行本脚本即可。")
            return None
        raise SystemExit(f"轮询失败: HTTP {resp.status_code} {resp.text[:200]}")
    echo("⌛ 等待超时，代码可能已过期。重新执行本脚本即可。")
    return None


def read_key_from_stdin(prompt: str = "粘贴 API key（输入不会回显）: ") -> str:
    """隐藏输入读一个 key —— 不走 argv，不进 shell 历史，不出现在终端记录里。"""
    import getpass

    key = getpass.getpass(prompt).strip()
    if not key:
        raise SystemExit("没有读到 key，未做任何修改")
    return key


def _write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def _read_state(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"找不到状态文件 {path}，请先跑一次 --print-only")
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="sieve 设备登录，把 SIEVE_API_KEY 写进 backend/.env"
    )
    parser.add_argument("--base-url", default=settings.SIEVE_BASE_URL, help="sieve 服务地址")
    parser.add_argument("--client-name", default="Freebuff", help="批准页显示的工具名（自报）")
    parser.add_argument("--env-file", default=None, help="自定义 .env 路径（默认 backend/.env）")
    parser.add_argument("--dry-run", action="store_true", help="拿到 key 也不写盘，只做校验")
    parser.add_argument("--force", action="store_true", help="已存在 SIEVE_API_KEY 时允许覆盖")
    parser.add_argument("--state-file", default=DEFAULT_STATE_FILE, help="device_code 暂存文件")
    parser.add_argument("--print-only", action="store_true", help="只申请并打印链接/代码，不轮询")
    parser.add_argument("--from-state", action="store_true", help="用状态文件里的 device_code 继续轮询")
    parser.add_argument("--set-key", action="store_true",
                        help="跳过设备登录：直接在隐藏输入里粘贴 Settings → API keys 的 key")
    parser.add_argument("--wait", type=int, default=600, help="轮询总时长上限（秒）")
    args = parser.parse_args(argv)

    base_url = args.base_url.rstrip("/")
    env_path = env_file_path(args.env_file)
    state_path = Path(args.state_file)

    if not args.dry_run and has_secret(SECRET_NAME, args.env_file) and not args.force:
        # 不覆盖既有 key：换 key 是用户的决定，不是脚本的默认行为
        print(f"⚠️  {env_path} 里已经存在 {SECRET_NAME}，未做任何修改。")
        print("    确认要换新 key 请加 --force 重跑。")
        return 2

    if args.set_key:
        api_key = read_key_from_stdin()
        if args.dry_run:
            print(f"✅ 读到 key（{_mask(api_key)}），--dry-run 模式不写盘。")
            return 0
        set_secret(SECRET_NAME, api_key, args.env_file)
        print(f"✅ {SECRET_NAME} 已写入 {env_path}（{_mask(api_key)}）")
        print("   注意：docker 的 env_file 只在容器创建时读取，")
        print("   需要 `docker compose up -d --force-recreate backend worker beat` 才生效。")
        return 0

    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        if args.from_state:
            state = _read_state(state_path)
            device_code = state["device_code"]
            user_code = state.get("user_code", "")
            verification = state.get("verification_uri_complete", "")
            interval = float(state.get("interval", 5))
            expires_in = min(int(state.get("expires_in", 600)), args.wait)
            _print_instructions(verification, user_code, expires_in)
        else:
            code = request_device_code(client, base_url, args.client_name)
            device_code = code["device_code"]
            user_code = code.get("user_code", "")
            verification = code.get("verification_uri_complete") or code.get("verification_uri", "")
            interval = float(code.get("interval", 5))
            expires_in = int(code.get("expires_in", 600))
            _write_state(state_path, {
                "device_code": device_code,
                "user_code": user_code,
                "verification_uri_complete": verification,
                "interval": interval,
                "expires_in": expires_in,
            })
            _print_instructions(verification, user_code, expires_in)
            if args.print_only:
                print(f"（--print-only：device_code 已暂存到 {state_path}，稍后用 --from-state 继续）")
                return 0

        api_key = poll_token(client, base_url, device_code, interval, min(expires_in, args.wait))
        if not api_key:
            return 1

    state_path.unlink(missing_ok=True)

    if args.dry_run:
        print(f"✅ 已拿到 key（{_mask(api_key)}），--dry-run 模式不写盘。")
        return 0

    set_secret(SECRET_NAME, api_key, args.env_file)
    # 只回显写到了哪里，密钥本体不出现在任何输出里
    print(f"✅ {SECRET_NAME} 已写入 {env_path}（{_mask(api_key)}）")
    print("   注意：docker 的 env_file 只在容器创建时读取，")
    print("   需要 `docker compose up -d --force-recreate backend worker beat` 才生效。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
