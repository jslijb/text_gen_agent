"""sieve API 端点测试（用 conftest 的 client / db_session fixture）。"""
import uuid

import pytest

from app.config.settings import settings
from app.models.sieve import SieveRun
from app.services.sieve_client import (
    SieveAuthError,
    SieveInsufficientCredits,
    SieveNotConfigured,
    SieveRateLimited,
)


@pytest.fixture
def configured(monkeypatch):
    """把 SIEVE_API_KEY 设成测试值；不真正发请求（worker 的 .delay 被打桩）。"""
    monkeypatch.setattr(settings, "SIEVE_API_KEY", "dc_sk_test_key")
    yield


@pytest.fixture
def no_enqueue(monkeypatch):
    """拦住 Celery 入队 —— API 测试不连 broker。

    替换的是**模块属性**（API 里在调用时 `from app.tasks.sieve_tasks import ...`），
    直接改 task 对象上的 delay 会被 celery 的 shared_task 代理挡住。
    """
    from app.tasks import sieve_tasks

    enqueued: list[tuple] = []

    class NoopTask:
        @staticmethod
        def delay(*args, **kwargs):
            enqueued.append((args, kwargs))

    monkeypatch.setattr(sieve_tasks, "run_sieve_scrape_task", NoopTask)
    monkeypatch.setattr(sieve_tasks, "sieve_followup_task", NoopTask)
    return enqueued


class TestUnconfigured:
    def test_status_reports_disabled(self, client, monkeypatch):
        monkeypatch.setattr(settings, "SIEVE_API_KEY", "")
        resp = client.get("/api/v1/sieve/status")
        assert resp.status_code == 200
        assert resp.json()["configured"] is False

    def test_create_run_is_503_and_writes_nothing(self, client, db_session, monkeypatch):
        """未配置 key 时抓取整体关闭，且不留下任何半成品记录。"""
        monkeypatch.setattr(settings, "SIEVE_API_KEY", "")
        resp = client.post("/api/v1/sieve/runs", json={"instruction": "抓一下"})
        assert resp.status_code == 503
        assert "SIEVE_API_KEY" in resp.json()["detail"]
        assert db_session.query(SieveRun).count() == 0


class TestCreateRun:
    def test_creates_placeholder_row_and_enqueues(self, client, db_session, configured, no_enqueue):
        resp = client.post(
            "/api/v1/sieve/runs",
            json={
                "instruction": "Extract the text and author of each quote",
                "target_urls": ["https://quotes.toscrape.com"],
                "fields": ["text", "author"],
                "output_schema": {"type": "object"},
            },
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "starting"
        assert body["session_id"] is None  # session_id 由 worker 拿到后立刻落库
        assert body["compliance_mode"] == "regular"

        db_session.expire_all()
        run = db_session.query(SieveRun).filter(SieveRun.id == body["id"]).first()
        assert run is not None
        assert run.instruction == "Extract the text and author of each quote"
        assert run.target_urls == ["https://quotes.toscrape.com"]
        assert len(no_enqueue) == 1

    def test_instruction_is_required(self, client, configured):
        resp = client.post("/api/v1/sieve/runs", json={"instruction": ""})
        assert resp.status_code == 422  # pydantic 的 min_length

    def test_oversized_output_schema_is_400(self, client, configured):
        resp = client.post(
            "/api/v1/sieve/runs",
            json={
                "instruction": "x",
                "output_schema": {"type": "string", "description": "x" * (33 * 1024)},
            },
        )
        assert resp.status_code == 400
        assert "output_schema" in resp.json()["detail"]

    def test_yolo_is_rejected_by_validation(self, client, configured):
        resp = client.post(
            "/api/v1/sieve/runs", json={"instruction": "x", "compliance_mode": "yolo!"}
        )
        assert resp.status_code == 422

    def test_yolo_is_accepted_when_the_user_chooses_it(self, client, configured, no_enqueue):
        resp = client.post(
            "/api/v1/sieve/runs", json={"instruction": "x", "compliance_mode": "yolo"}
        )
        assert resp.status_code == 202
        assert resp.json()["compliance_mode"] == "yolo"


class TestReadRuns:
    def test_list_and_detail(self, client, db_session, configured):
        run = SieveRun(
            id=str(uuid.uuid4()),
            session_id="sess_1",
            status="done",
            kind="scrape",
            instruction="抓报价",
            schema_conformance="fail",
            summary="只拿到 2/5 列",
        )
        db_session.add(run)
        db_session.commit()

        listed = client.get("/api/v1/sieve/runs").json()
        assert listed["total"] == 1
        assert listed["items"][0]["poll"] == "/api/scrapes/sess_1"

        detail = client.get(f"/api/v1/sieve/runs/{run.id}").json()
        # fail 的产物不能被当成干净数据：API 直接把结论和警告一起给出
        assert detail["schema_conformance"] == "fail"
        assert detail["conformance_ok"] is False
        assert detail["conformance_warning"]

    def test_missing_run_is_404(self, client, configured):
        assert client.get(f"/api/v1/sieve/runs/{uuid.uuid4()}").status_code == 404

    def test_refresh_pulls_remote_status(self, client, db_session, configured, monkeypatch):
        run = SieveRun(
            id=str(uuid.uuid4()), session_id="sess_1", status="running",
            kind="scrape", instruction="抓", turns=0,
        )
        db_session.add(run)
        db_session.commit()

        class StubClient:
            def __init__(self, *a, **k):
                pass

            def get_scrape(self, session_id):
                assert session_id == "sess_1"
                return {"status": "running", "turns": 3}

        monkeypatch.setattr("app.api.sieve.SieveClient", StubClient)
        resp = client.get(f"/api/v1/sieve/runs/{run.id}?refresh=true")
        assert resp.status_code == 200
        assert resp.json()["turns"] == 3


class TestFollowUp:
    def _parent(self, db_session, **kwargs):
        run = SieveRun(
            id=str(uuid.uuid4()), kind="scrape", instruction="原始任务",
            status="done", turns=1, **kwargs
        )
        db_session.add(run)
        db_session.commit()
        return run

    def test_followup_records_turn_baseline_then_enqueues(
        self, client, db_session, configured, no_enqueue
    ):
        """先记 turn（含基线）再入队 —— 顺序反了就会读到上一轮的答案。"""
        parent = self._parent(db_session, session_id="sess_1")

        resp = client.post(
            f"/api/v1/sieve/runs/{parent.id}/messages", json={"instruction": "只留作者"}
        )

        assert resp.status_code == 202
        body = resp.json()
        assert body["kind"] == "follow_up"
        assert body["parent_id"] == str(parent.id)
        # 基线必须落库：轮询到 done 但 turns 没推进时要靠它判断"还是上一轮的答案"
        assert body["turns"] == 1
        db_session.expire_all()
        child = db_session.query(SieveRun).filter(SieveRun.id == body["id"]).first()
        assert child.baseline_turns == 1
        assert len(no_enqueue) == 1

    def test_followup_without_session_id_is_409(self, client, db_session, configured, no_enqueue):
        parent = self._parent(db_session, session_id=None)
        resp = client.post(
            f"/api/v1/sieve/runs/{parent.id}/messages", json={"instruction": "x"}
        )
        assert resp.status_code == 409

    def test_followup_on_missing_run_is_404(self, client, configured):
        resp = client.post(f"/api/v1/sieve/runs/{uuid.uuid4()}/messages", json={"instruction": "x"})
        assert resp.status_code == 404


class TestErrorMappingEndpoint:
    @pytest.mark.parametrize(
        "error,expected",
        [
            (SieveAuthError("key revoked"), 401),
            (SieveInsufficientCredits("out of credits"), 402),
            (SieveNotConfigured("no key"), 503),
        ],
    )
    def test_client_errors_map_to_http(self, client, monkeypatch, error, expected):
        class StubClient:
            def __init__(self, *a, **k):
                pass

            def get_credits(self):
                raise error

        monkeypatch.setattr("app.api.sieve.SieveClient", StubClient)
        resp = client.get("/api/v1/sieve/credits")
        assert resp.status_code == expected

    def test_rate_limit_sets_retry_after_header(self, client, monkeypatch):
        class StubClient:
            def __init__(self, *a, **k):
                pass

            def get_credits(self):
                raise SieveRateLimited("slow down", retry_after=9)

        monkeypatch.setattr("app.api.sieve.SieveClient", StubClient)
        resp = client.get("/api/v1/sieve/credits")
        assert resp.status_code == 429
        assert resp.headers["retry-after"] == "9"

    def test_credits_passthrough(self, client, monkeypatch):
        class StubClient:
            def __init__(self, *a, **k):
                pass

            def get_credits(self):
                return {"plan": "pro", "limit": 500, "used": 20, "remaining": 480}

        monkeypatch.setattr("app.api.sieve.SieveClient", StubClient)
        body = client.get("/api/v1/sieve/credits").json()
        assert body["plan"] == "pro"
        assert body["remaining"] == 480
