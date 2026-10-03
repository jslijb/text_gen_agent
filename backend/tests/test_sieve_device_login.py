"""设备登录脚本测试（离线）：录制响应打在 HTTP 边界，不碰真实网络。"""
import importlib.util
import json
from pathlib import Path

import httpx
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sieve_device_login.py"
_spec = importlib.util.spec_from_file_location("sieve_device_login", SCRIPT)
login = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(login)

BASE = "https://scrape.usesieve.com"
FAKE_KEY = "dc_sk_this_is_a_fake_key_value"


class FakeAPI:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        status, payload = item[0], item[1]
        if isinstance(payload, bytes):
            return httpx.Response(status, content=payload, request=request)
        return httpx.Response(status, json=payload, request=request)


# 记下真实的 Client：下面的 monkeypatch 会把 httpx.Client 换成工厂，
# 工厂内部必须用这个原始构造器，否则自己调自己会无限递归。
_REAL_CLIENT = httpx.Client


def make_client(fake):
    return _REAL_CLIENT(transport=httpx.MockTransport(fake), timeout=5)


def test_request_device_code_posts_client_name():
    fake = FakeAPI((200, {"device_code": "dev-1", "user_code": "WDJB-MJHT",
                          "verification_uri_complete": f"{BASE}/device?code=WDJB-MJHT",
                          "expires_in": 600, "interval": 5}))
    code = login.request_device_code(make_client(fake), BASE, "Freebuff")
    assert code["user_code"] == "WDJB-MJHT"
    body = json.loads(fake.requests[0].content)
    assert body == {"client_name": "Freebuff"}
    assert fake.requests[0].url.path == "/api/auth/device/code"


def test_request_device_code_failure_exits():
    fake = FakeAPI((500, {"error": "boom"}))
    with pytest.raises(SystemExit):
        login.request_device_code(make_client(fake), BASE, "Freebuff")


def test_poll_returns_key_on_success():
    fake = FakeAPI((200, {"api_key": FAKE_KEY, "token_type": "Bearer", "key_name": "k"}))
    sleeps: list[float] = []
    key = login.poll_token(make_client(fake), BASE, "dev-1", 5, 600, sleep=sleeps.append)
    assert key == FAKE_KEY
    assert sleeps == [5.0]
    assert json.loads(fake.requests[0].content) == {"device_code": "dev-1"}


def test_poll_keeps_going_while_pending():
    fake = FakeAPI(
        (400, {"error": "authorization_pending"}),
        (400, {"error": "authorization_pending"}),
        (200, {"api_key": FAKE_KEY}),
    )
    sleeps: list[float] = []
    key = login.poll_token(make_client(fake), BASE, "dev-1", 5, 600, sleep=sleeps.append)
    assert key == FAKE_KEY
    assert len(fake.requests) == 3


def test_slow_down_adds_five_seconds():
    fake = FakeAPI(
        (400, {"error": "slow_down"}),
        (200, {"api_key": FAKE_KEY}),
    )
    sleeps: list[float] = []
    key = login.poll_token(make_client(fake), BASE, "dev-1", 5, 600, sleep=sleeps.append)
    assert key == FAKE_KEY
    assert sleeps == [5.0, 10.0]


@pytest.mark.parametrize("error", ["access_denied", "expired_token"])
def test_user_side_terminals_return_none(error):
    fake = FakeAPI((400, {"error": error}))
    assert login.poll_token(make_client(fake), BASE, "dev-1", 5, 600, sleep=lambda s: None) is None


def test_non_json_error_body_exits():
    fake = FakeAPI((400, b"<html>nope</html>"))
    with pytest.raises(SystemExit):
        login.poll_token(make_client(fake), BASE, "dev-1", 5, 600, sleep=lambda s: None)


def test_main_print_only_writes_state_and_does_not_poll(tmp_path, monkeypatch, capsys):
    fake = FakeAPI((200, {"device_code": "dev-1", "user_code": "WDJB-MJHT",
                          "verification_uri_complete": f"{BASE}/device", "expires_in": 600,
                          "interval": 5}))
    monkeypatch.setattr(login.httpx, "Client", lambda **kw: make_client(fake))

    out = tmp_path / "state.json"
    rc = login.main(["--print-only", "--state-file", str(out), "--env-file", str(tmp_path / ".env")])

    assert rc == 0
    assert json.loads(out.read_text(encoding="utf-8"))["device_code"] == "dev-1"
    assert len(fake.requests) == 1  # 只申请，不轮询
    printed = capsys.readouterr().out
    assert "WDJB-MJHT" in printed
    assert "只批准你自己发起的代码" in printed  # 防钓鱼提示必须出现
    assert not (tmp_path / ".env").exists()


def test_main_from_state_writes_key_without_printing_it(tmp_path, monkeypatch, capsys):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({
        "device_code": "dev-1", "user_code": "WDJB-MJHT",
        "verification_uri_complete": f"{BASE}/device", "interval": 5, "expires_in": 600,
    }), encoding="utf-8")
    fake = FakeAPI((400, {"error": "authorization_pending"}), (200, {"api_key": FAKE_KEY}))
    monkeypatch.setattr(login.httpx, "Client", lambda **kw: make_client(fake))
    monkeypatch.setattr(login.time, "sleep", lambda s: None)

    env = tmp_path / ".env"
    env.write_text("AGNES_KEY=abc\n", encoding="utf-8")
    rc = login.main(["--from-state", "--state-file", str(state), "--env-file", str(env)])

    assert rc == 0
    content = env.read_text(encoding="utf-8")
    assert "AGNES_KEY=abc" in content          # 其它变量保留
    assert f"SIEVE_API_KEY={FAKE_KEY}" in content
    assert not state.exists(), "拿到 key 后状态文件要删掉"

    printed = capsys.readouterr().out
    assert FAKE_KEY not in printed, "密钥绝不能出现在输出里"


def test_main_refuses_to_overwrite_without_force(tmp_path, monkeypatch, capsys):
    env = tmp_path / ".env"
    env.write_text("SIEVE_API_KEY=dc_sk_existing\n", encoding="utf-8")
    called = []
    monkeypatch.setattr(login.httpx, "Client", lambda **kw: called.append(kw))

    rc = login.main(["--env-file", str(env), "--state-file", str(tmp_path / "s.json")])

    assert rc == 2
    assert called == []  # 连设备码都不申请
    assert env.read_text(encoding="utf-8") == "SIEVE_API_KEY=dc_sk_existing\n"


def test_set_key_writes_secret_without_touching_the_device_flow(tmp_path, monkeypatch, capsys):
    """设备登录走不通时的落地路径：粘贴 Settings → API keys 里建的 key。"""
    called = []
    monkeypatch.setattr(login.httpx, "Client", lambda **kw: called.append(kw))
    monkeypatch.setattr(login, "read_key_from_stdin", lambda *a, **k: FAKE_KEY)
    env = tmp_path / ".env"

    rc = login.main(["--set-key", "--env-file", str(env)])

    assert rc == 0
    assert called == [], "不该发起任何 HTTP 请求"
    assert env.read_text(encoding="utf-8") == f"SIEVE_API_KEY={FAKE_KEY}\n"
    assert FAKE_KEY not in capsys.readouterr().out, "密钥不能出现在输出里"


def test_set_key_refuses_overwrite_without_force(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("SIEVE_API_KEY=dc_sk_existing\n", encoding="utf-8")
    monkeypatch.setattr(login, "read_key_from_stdin", lambda *a, **k: FAKE_KEY)

    assert login.main(["--set-key", "--env-file", str(env)]) == 2
    assert "dc_sk_existing" in env.read_text(encoding="utf-8")


def test_mask_hides_the_body():
    masked = login._mask(FAKE_KEY)
    assert FAKE_KEY not in masked
    assert "6" in masked or "位" in masked
