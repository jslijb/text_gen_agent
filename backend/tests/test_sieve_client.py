"""sieve 客户端测试。

录制响应只出现在 **HTTP 边界**（`httpx.MockTransport`）：
请求头/URL/body 是真实构建的，状态机、退避、错误映射都是真实代码。
"""
import json

import httpx
import pytest

from app.services import sieve_client as sc
from app.services.sieve_client import (
    DEFAULT_COMPLIANCE_MODE,
    SieveAmbiguousRequest,
    SieveAuthError,
    SieveClient,
    SieveInsufficientCredits,
    SieveNotFound,
    SieveNotConfigured,
    SieveRateLimited,
    SieveRefused,
    SieveRequestRejected,
    SieveServerError,
    SieveTimeout,
    SieveTurnInFlight,
    SieveUnknownStatus,
    classify_status,
    describe_conformance,
    files_with_urls,
)

BASE = "https://scrape.usesieve.com"
KEY = "dc_sk_test_key"


class FakeAPI:
    """按顺序吐录制响应、记录真实请求的 httpx 传输层。"""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if not self.responses:
            raise AssertionError(f"没有更多录制响应了: {request.method} {request.url}")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        status, payload = item[0], item[1]
        headers = item[2] if len(item) > 2 else {}
        if isinstance(payload, bytes):
            return httpx.Response(status, content=payload, headers=headers, request=request)
        return httpx.Response(status, json=payload, headers=headers, request=request)

    @property
    def method_and_paths(self):
        return [(r.method, r.url.path) for r in self.requests]


def make_client(fake: FakeAPI, api_key: str = KEY, sleeps: list | None = None):
    sleeps = [] if sleeps is None else sleeps
    client = SieveClient(
        api_key=api_key,
        base_url=BASE,
        transport=httpx.MockTransport(fake),
        sleep=sleeps.append,
    )
    return client, sleeps


QUEUED = (202, {"status": "queued", "session_id": "sess_123", "poll": "/api/scrapes/sess_123"})


# --------------------------------------------------------------------------- #
# 请求构建
# --------------------------------------------------------------------------- #
class TestRequestBuilding:
    def test_start_scrape_builds_expected_request(self):
        fake = FakeAPI(QUEUED)
        client, _ = make_client(fake)

        payload = client.start_scrape(
            instruction="Extract the text and author of each quote",
            target_urls=["https://quotes.toscrape.com"],
            fields=["text", "author"],
            output_schema={"type": "object"},
            table_shape="long",
        )

        assert payload["session_id"] == "sess_123"
        req = fake.requests[0]
        assert req.method == "POST"
        assert str(req.url) == f"{BASE}/api/scrapes"
        assert req.headers["authorization"] == f"Bearer {KEY}"
        body = json.loads(req.content)
        assert body["instruction"] == "Extract the text and author of each quote"
        assert body["target_urls"] == ["https://quotes.toscrape.com"]
        assert body["fields"] == ["text", "author"]
        assert body["output_schema"] == {"type": "object"}
        assert body["table_shape"] == "long"
        # 未显式选择时用 regular；yolo 只能由用户显式指定
        assert body["compliance_mode"] == DEFAULT_COMPLIANCE_MODE == "regular"

    def test_instruction_is_required(self):
        fake = FakeAPI(QUEUED)
        client, _ = make_client(fake)
        with pytest.raises(SieveRequestRejected):
            client.start_scrape(instruction="   ")
        assert fake.requests == []

    def test_target_urls_must_be_http(self):
        fake = FakeAPI(QUEUED)
        client, _ = make_client(fake)
        with pytest.raises(SieveRequestRejected):
            client.start_scrape(instruction="x", target_urls=["file:///etc/passwd"])
        assert fake.requests == []

    def test_output_schema_size_limit(self):
        fake = FakeAPI(QUEUED)
        client, _ = make_client(fake)
        huge = {"type": "string", "description": "x" * (33 * 1024)}
        with pytest.raises(SieveRequestRejected) as e:
            client.start_scrape(instruction="x", output_schema=huge)
        assert "32" in str(e.value)
        assert fake.requests == []

    def test_compliance_mode_is_validated(self):
        fake = FakeAPI(QUEUED)
        client, _ = make_client(fake)
        with pytest.raises(SieveRequestRejected):
            client.start_scrape(instruction="x", compliance_mode="reckless")
        assert fake.requests == []

    def test_document_upload_uses_multipart_file_field(self):
        """带文档时改走 multipart，文件放 "file" 字段，复杂字段序列化成 JSON 字符串。"""
        fake = FakeAPI(QUEUED)
        client, _ = make_client(fake)
        import tempfile, os

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("hello")
            path = fh.name
        try:
            client.start_scrape(instruction="summarize", file_path=path)
        finally:
            os.unlink(path)
        req = fake.requests[-1]
        assert req.headers["content-type"].startswith("multipart/form-data")
        assert b'name="file"' in req.content
        assert b'name="instruction"' in req.content

    def test_unexpected_success_code_is_an_error(self):
        fake = FakeAPI((200, {"session_id": "sess_1"}))
        client, _ = make_client(fake)
        with pytest.raises(SieveServerError):
            client.start_scrape(instruction="x")


# --------------------------------------------------------------------------- #
# 超时/重试规则
# --------------------------------------------------------------------------- #
class TestRetryRules:
    def test_post_timeout_is_never_retried(self):
        """POST /api/scrapes 没有幂等键，第一次可能已经成功 —— 绝不自动重发。"""
        fake = FakeAPI(httpx.TimeoutException("read timeout"))
        client, sleeps = make_client(fake)

        with pytest.raises(SieveAmbiguousRequest):
            client.start_scrape(instruction="x")

        assert len(fake.requests) == 1, "超时后重发一次就可能重复扣费"
        assert sleeps == []

    def test_post_network_error_is_never_retried(self):
        fake = FakeAPI(httpx.ConnectError("connection refused"))
        client, _ = make_client(fake)
        with pytest.raises(SieveAmbiguousRequest):
            client.start_scrape(instruction="x")
        assert len(fake.requests) == 1

    def test_post_500_is_retried_because_no_run_was_created(self):
        fake = FakeAPI((500, {"error": "boom"}), QUEUED)
        client, sleeps = make_client(fake)

        payload = client.start_scrape(instruction="x")

        assert payload["session_id"] == "sess_123"
        assert fake.method_and_paths == [("POST", "/api/scrapes")] * 2
        assert len(sleeps) == 1

    def test_post_429_honours_retry_after(self):
        fake = FakeAPI((429, {"error": "slow"}, {"Retry-After": "7"}), QUEUED)
        client, sleeps = make_client(fake)

        client.start_scrape(instruction="x")

        assert sleeps == [7.0]

    def test_get_retries_transient_network_error(self):
        fake = FakeAPI(
            httpx.TimeoutException("boom"),
            (200, {"status": "running", "turns": 0}),
        )
        client, _ = make_client(fake)

        payload = client.get_scrape("sess_123")

        assert payload["status"] == "running"
        assert len(fake.requests) == 2

    def test_gives_up_after_max_attempts(self):
        fake = FakeAPI(*[(500, {"error": "boom"})] * sc.SAFE_RETRY_ATTEMPTS)
        client, _ = make_client(fake)
        with pytest.raises(SieveServerError):
            client.get_scrape("sess_123")
        assert len(fake.requests) == sc.SAFE_RETRY_ATTEMPTS


# --------------------------------------------------------------------------- #
# 错误映射
# --------------------------------------------------------------------------- #
class TestErrorMapping:
    @pytest.mark.parametrize(
        "code,payload,expected",
        [
            (400, {"error": "bad request"}, SieveRequestRejected),
            (401, {"error": "invalid key"}, SieveAuthError),
            (402, {"error": "no credits"}, SieveInsufficientCredits),
            (404, {"error": "not found"}, SieveNotFound),
            (409, {"error": "turn in flight"}, SieveTurnInFlight),
        ],
    )
    def test_status_code_mapping(self, code, payload, expected):
        fake = FakeAPI((code, payload))
        client, _ = make_client(fake)
        with pytest.raises(expected) as e:
            client.get_scrape("sess_123")
        assert str(code) in str(e.value)
        assert len(fake.requests) == 1, "4xx 不该被重试"

    def test_429_exhausted_keeps_retry_after(self):
        fake = FakeAPI(*[(429, {"error": "slow"}, {"Retry-After": "13"})] * sc.SAFE_RETRY_ATTEMPTS)
        client, _ = make_client(fake)
        with pytest.raises(SieveRateLimited) as e:
            client.get_scrape("sess_123")
        assert e.value.retry_after == 13.0

    def test_non_dict_error_body_does_not_crash(self):
        fake = FakeAPI((400, b"<html>bad</html>"))
        client, _ = make_client(fake)
        with pytest.raises(SieveRequestRejected):
            client.get_scrape("sess_123")

    def test_not_configured_makes_no_request(self):
        fake = FakeAPI(QUEUED)
        client, _ = make_client(fake, api_key="")
        assert client.configured is False
        with pytest.raises(SieveNotConfigured):
            client.get_scrape("sess_123")
        with pytest.raises(SieveNotConfigured):
            client.start_scrape(instruction="x")
        assert fake.requests == []


# --------------------------------------------------------------------------- #
# 状态机与轮询
# --------------------------------------------------------------------------- #
class TestStatusHandling:
    @pytest.mark.parametrize(
        "status,expected",
        [
            ("running", "running"),
            ("queued", "running"),  # 创建接口的取值，出现在轮询里同样算在跑
            ("done", "done"),
            ("refused", "refused"),
        ],
    )
    def test_known_statuses(self, status, expected):
        assert classify_status({"status": status}) == expected

    @pytest.mark.parametrize("status", ["paused", "", None, "completed"])
    def test_unknown_status_is_an_error(self, status):
        with pytest.raises(SieveUnknownStatus):
            classify_status({"status": status})

    def test_poll_backs_off_from_five_seconds(self):
        fake = FakeAPI(
            (200, {"status": "running", "turns": 0}),
            (200, {"status": "running", "turns": 0}),
            (200, {"status": "done", "turns": 0, "result": {"ok": True}}),
        )
        client, sleeps = make_client(fake)

        payload = client.wait_for_run("sess_123")

        assert payload["result"] == {"ok": True}
        assert sleeps[0] == sc.POLL_INITIAL_DELAY == 5.0
        assert sleeps[1] > sleeps[0]
        assert all(s <= sc.POLL_MAX_DELAY for s in sleeps)

    def test_done_payload_is_returned_as_is(self):
        done = {
            "status": "done",
            "session_id": "sess_123",
            "summary": "3 quotes",
            "files": [{"name": "quotes.csv", "size": 120, "ext": "csv", "url": "/files/1"}],
            "schema_conformance": {"status": "pass"},
            "result": {"rows": 3},
            "turns": 1,
        }
        fake = FakeAPI((200, done))
        client, _ = make_client(fake)
        assert client.wait_for_run("sess_123") == done

    def test_refused_is_terminal_and_carries_the_code(self):
        fake = FakeAPI((200, {"status": "refused", "refusal": {"code": "quota"}}))
        client, _ = make_client(fake)

        with pytest.raises(SieveRefused) as e:
            client.wait_for_run("sess_123")

        assert e.value.code == "quota"
        assert e.value.is_quota is True
        assert len(fake.requests) == 1, "refused 是终态，不该继续轮询"

    def test_unknown_status_stops_polling(self):
        fake = FakeAPI((200, {"status": "paused"}))
        client, _ = make_client(fake)
        with pytest.raises(SieveUnknownStatus):
            client.wait_for_run("sess_123")
        assert len(fake.requests) == 1

    def test_wait_budget_leaves_run_running(self):
        """预算用尽不是失败：run 还在跑，状态该留在 running 等接力。"""
        fake = FakeAPI(*[(200, {"status": "running"})] * 3)
        client, _ = make_client(fake)
        with pytest.raises(SieveTimeout):
            client.wait_for_run("sess_123", max_wait=0)


class TestFollowUpTurns:
    def test_waits_until_turns_advance_past_the_recorded_turn(self):
        """status 已是 done 但 turns 没动 = 还是上一轮的答案，必须继续等。"""
        fake = FakeAPI(
            (200, {"status": "done", "turns": 1, "result": {"answer": "old"}}),
            (200, {"status": "running", "turns": 1}),
            (200, {"status": "done", "turns": 2, "result": {"answer": "new"}}),
        )
        client, _ = make_client(fake)

        payload = client.wait_for_turn("sess_123", previous_turns=1)

        assert payload["result"] == {"answer": "new"}
        assert payload["turns"] == 2
        assert len(fake.requests) == 3

    def test_turn_that_never_advances_keeps_polling(self):
        fake = FakeAPI(*[(200, {"status": "done", "turns": 1})] * 3)
        client, _ = make_client(fake)
        with pytest.raises(SieveTimeout):
            client.wait_for_turn("sess_123", previous_turns=1, max_wait=0)

    def test_message_payload_matches_create_body(self):
        fake = FakeAPI((202, {"status": "running", "turns": 2}))
        client, _ = make_client(fake)
        client.send_message("sess_123", instruction="now only the authors")
        req = fake.requests[0]
        assert str(req.url) == f"{BASE}/api/scrapes/sess_123/messages"
        body = json.loads(req.content)
        assert body["instruction"] == "now only the authors"
        assert body["compliance_mode"] == "regular"

    def test_in_flight_turn_maps_to_409_exception(self):
        fake = FakeAPI((409, {"error": "a turn is already in flight"}))
        client, _ = make_client(fake)
        with pytest.raises(SieveTurnInFlight):
            client.send_message("sess_123", instruction="x")


# --------------------------------------------------------------------------- #
# 交付文件与结论翻译
# --------------------------------------------------------------------------- #
class TestFilesAndConformance:
    def test_relative_file_urls_are_prefixed(self):
        files = [
            {"name": "a.csv", "url": "/files/a.csv"},
            {"name": "b.csv", "url": "https://cdn.example.com/b.csv"},
        ]
        out = files_with_urls(files, BASE)
        assert out[0]["url"] == f"{BASE}/files/a.csv"
        assert out[1]["url"] == "https://cdn.example.com/b.csv"

    def test_download_file_sends_bearer_to_prefixed_url(self):
        fake = FakeAPI((200, b"name,text\na,b\n"))
        client, _ = make_client(fake)
        import tempfile, os

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "out", "a.csv")
            client.download_file("/files/a.csv", dest)
            assert open(dest, "rb").read() == b"name,text\na,b\n"
        req = fake.requests[0]
        assert str(req.url) == f"{BASE}/files/a.csv"
        assert req.headers["authorization"] == f"Bearer {KEY}"

    def test_download_file_maps_404(self):
        fake = FakeAPI((404, {"error": "gone"}))
        client, _ = make_client(fake)
        import tempfile, os

        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(SieveNotFound):
                client.download_file("/files/a.csv", os.path.join(tmp, "a.csv"))

    @pytest.mark.parametrize(
        "status,ok",
        [
            ("pass", True),
            ("partial", True),
            ("fail", False),
            ("not_checkable", False),
            ("no_artifact", False),
        ],
    )
    def test_conformance_translation(self, status, ok):
        result = describe_conformance({"status": status})
        assert result["ok"] is ok
        if status == "fail":
            # fail 绝不能被当成干净数据
            assert result["warning"]

    def test_fail_conformance_is_flagged_for_the_caller(self):
        result = describe_conformance({"status": "fail"})
        assert result["ok"] is False
        assert "fail" in result["warning"]

    def test_credits_passthrough(self):
        credits = {"plan": "free", "limit": 100, "used": 7, "remaining": 93}
        fake = FakeAPI((200, credits))
        client, _ = make_client(fake)
        assert client.get_credits() == credits
        assert str(fake.requests[0].url) == f"{BASE}/api/me/credits"
