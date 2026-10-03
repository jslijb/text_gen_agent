"""sieve Celery 任务测试：落库顺序、终态处理、追问基线与补轮询。

Stub 掉 SieveClient（HTTP 边界之上的一层），被测的是任务里的落库/状态机逻辑。
"""
import uuid

import pytest

from app.config.settings import settings
from app.models.sieve import SieveRun
from app.services.sieve_client import (
    SieveAmbiguousRequest,
    SieveAuthError,
    SieveRefused,
    SieveTimeout,
)
from app.tasks import sieve_tasks


@pytest.fixture(autouse=True)
def no_redis_lock(monkeypatch):
    """轮询锁依赖 Redis；这里直接放行，确保测试不依赖外部服务。"""
    monkeypatch.setattr(sieve_tasks, "_acquire_poll_lock", lambda run_id: True)
    monkeypatch.setattr(sieve_tasks, "_release_poll_lock", lambda run_id: None)


class StubClient:
    """可编程的假客户端，记录调用、按剧本返回或抛错。"""

    calls: list = []
    start_payload: dict | object = {"status": "queued", "session_id": "sess_9"}
    wait_payload: dict | object = {"status": "done", "turns": 1}
    wait_error: Exception | None = None
    turn_payload: dict | object | None = None
    turn_error: Exception | None = None
    message_error: Exception | None = None

    def __init__(self, *args, **kwargs):
        # 注意：不要在这里清空 calls —— 一次任务里会 new 好几个客户端，
        # 清空会把同一测试里前面的调用记录冲掉。清空由 fixture 负责。
        self.base_url = settings.SIEVE_BASE_URL

    def start_scrape(self, **kwargs):
        type(self).calls.append(("start_scrape", kwargs))
        if isinstance(self.__class__.start_payload, Exception):
            raise self.__class__.start_payload
        return self.__class__.start_payload

    def wait_for_run(self, session_id, max_wait=None, on_status=None):
        type(self).calls.append(("wait_for_run", session_id, max_wait))
        if self.__class__.wait_error is not None:
            raise self.__class__.wait_error
        payload = self.__class__.wait_payload
        if on_status is not None:
            on_status(payload)
        return payload

    def wait_for_turn(self, session_id, previous_turns, max_wait=None, on_status=None):
        type(self).calls.append(("wait_for_turn", session_id, previous_turns))
        if self.__class__.turn_error is not None:
            raise self.__class__.turn_error
        payload = self.__class__.turn_payload
        if on_status is not None:
            on_status(payload)
        return payload

    def send_message(self, session_id, **kwargs):
        type(self).calls.append(("send_message", session_id, kwargs))
        if self.__class__.message_error is not None:
            raise self.__class__.message_error
        return {"status": "running", "turns": 2}

    def download_file(self, url, dest_path):
        from pathlib import Path

        p = Path(dest_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"data")
        type(self).calls.append(("download_file", url))
        return str(p)


@pytest.fixture
def stub_client(monkeypatch):
    for attr, value in [
        ("start_payload", {"status": "queued", "session_id": "sess_9"}),
        ("wait_payload", {"status": "done", "turns": 1}),
        ("wait_error", None),
        ("turn_payload", None),
        ("turn_error", None),
        ("message_error", None),
        ("calls", []),
    ]:
        setattr(StubClient, attr, value)
    monkeypatch.setattr(sieve_tasks, "SieveClient", StubClient)
    return StubClient


def make_run(db_session, **kwargs):
    defaults = dict(
        id=str(uuid.uuid4()),
        status="starting",
        kind="scrape",
        instruction="Extract the text and author of each quote",
        compliance_mode="regular",
        turns=0,
    )
    defaults.update(kwargs)
    run = SieveRun(**defaults)
    db_session.add(run)
    db_session.commit()
    return run


class TestCreateAndPoll:
    def test_session_id_is_committed_before_polling(self, db_session, stub_client, monkeypatch):
        """创建成功 → 立刻单独落库；即使随后崩掉，也能靠 session_id 继续轮询而不是重开。"""
        run = make_run(db_session)

        def crash(self, session_id, max_wait=None, on_status=None):
            raise RuntimeError("worker crashed mid-poll")

        monkeypatch.setattr(stub_client, "wait_for_run", crash, raising=False)

        with pytest.raises(RuntimeError):
            sieve_tasks._create_and_poll(str(run.id))

        db_session.expire_all()
        row = db_session.query(SieveRun).filter(SieveRun.id == run.id).first()
        assert row.session_id == "sess_9"
        assert row.status == SieveRun.Status.RUNNING

    def test_ambiguous_post_is_recorded_and_never_retried(self, db_session, stub_client):
        run = make_run(db_session)
        stub_client.start_payload = SieveAmbiguousRequest("timeout after send")

        result = sieve_tasks._create_and_poll(str(run.id))

        assert result["status"] == SieveRun.Status.AMBIGUOUS
        starts = [c for c in stub_client.calls if c[0] == "start_scrape"]
        assert len(starts) == 1, "创建接口没有幂等键：只允许试一次"
        assert not [c for c in stub_client.calls if c[0] == "wait_for_run"]
        db_session.expire_all()
        row = db_session.query(SieveRun).filter(SieveRun.id == run.id).first()
        assert row.status == SieveRun.Status.AMBIGUOUS
        assert "timeout" in row.error

    def test_create_error_marks_error(self, db_session, stub_client):
        run = make_run(db_session)
        stub_client.start_payload = SieveAuthError("key revoked")
        result = sieve_tasks._create_and_poll(str(run.id))
        assert result["status"] == SieveRun.Status.ERROR

    def test_done_persists_payload_and_downloads_files(
        self, db_session, stub_client, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(settings, "SIEVE_FILES_DIR", str(tmp_path))
        run = make_run(db_session, session_id="sess_9", status="running")
        stub_client.wait_payload = {
            "status": "done",
            "session_id": "sess_9",
            "turns": 1,
            "summary": "3 quotes",
            "files": [{"name": "quotes.csv", "size": 10, "ext": "csv", "url": "/files/quotes.csv"}],
            "schema_conformance": {"status": "partial"},
            "result": {"rows": 3},
        }

        result = sieve_tasks._poll_run(str(run.id))

        assert result["status"] == "done"
        db_session.expire_all()
        row = db_session.query(SieveRun).filter(SieveRun.id == run.id).first()
        assert row.status == SieveRun.Status.DONE
        assert row.summary == "3 quotes"
        assert row.result == {"rows": 3}
        assert row.schema_conformance == "partial"
        assert row.local_files and row.local_files[0].endswith("quotes.csv")
        assert ("download_file", f"{settings.SIEVE_BASE_URL}/files/quotes.csv") in stub_client.calls

    def test_refused_is_terminal_and_records_code(self, db_session, stub_client):
        run = make_run(db_session, session_id="sess_9", status="running")
        stub_client.wait_error = SieveRefused("refused", refusal={"code": "quota"})

        result = sieve_tasks._poll_run(str(run.id))

        assert result["status"] == "refused"
        db_session.expire_all()
        row = db_session.query(SieveRun).filter(SieveRun.id == run.id).first()
        assert row.status == SieveRun.Status.REFUSED
        assert row.refusal_code == "quota"

    def test_budget_exhausted_keeps_running_for_resume(self, db_session, stub_client):
        run = make_run(db_session, session_id="sess_9", status="running")
        stub_client.wait_error = SieveTimeout("budget used")

        result = sieve_tasks._poll_run(str(run.id))

        assert result["status"] == "running"
        db_session.expire_all()
        row = db_session.query(SieveRun).filter(SieveRun.id == run.id).first()
        assert row.status == SieveRun.Status.RUNNING

    def test_missing_session_id_is_not_polled(self, db_session, stub_client):
        run = make_run(db_session, status="starting")
        result = sieve_tasks._poll_run(str(run.id))
        assert result["status"] == "skipped"
        assert not [c for c in stub_client.calls if c[0] == "wait_for_run"]


class TestFollowUp:
    def _pair(self, db_session, baseline=1):
        parent = make_run(db_session, session_id="sess_9", status="done", turns=baseline)
        child = make_run(
            db_session,
            kind="follow_up",
            parent_id=parent.id,
            status="starting",
            instruction="只留作者",
            turns=baseline,
            baseline_turns=baseline,
        )
        return parent, child

    def test_waits_for_turns_to_advance_past_baseline(self, db_session, stub_client):
        parent, child = self._pair(db_session, baseline=1)
        stub_client.turn_payload = {
            "status": "done", "turns": 2, "session_id": "sess_9", "result": {"answer": "new"},
        }

        result = sieve_tasks._followup(str(child.id))

        assert result["status"] == "done"
        assert result["parent_id"] == str(parent.id)
        assert ("send_message", "sess_9", {"instruction": "只留作者"}) in stub_client.calls
        turn_calls = [c for c in stub_client.calls if c[0] == "wait_for_turn"]
        assert turn_calls == [("wait_for_turn", "sess_9", 1)]
        db_session.expire_all()
        row = db_session.query(SieveRun).filter(SieveRun.id == child.id).first()
        assert row.status == SieveRun.Status.DONE
        assert row.result == {"answer": "new"}

    def test_in_flight_turn_records_error_without_polling(self, db_session, stub_client):
        from app.services.sieve_client import SieveTurnInFlight

        _, child = self._pair(db_session)
        stub_client.message_error = SieveTurnInFlight("已有 turn 在飞")

        result = sieve_tasks._followup(str(child.id))

        assert result["status"] == "error"
        assert not [c for c in stub_client.calls if c[0] == "wait_for_turn"]
        db_session.expire_all()
        row = db_session.query(SieveRun).filter(SieveRun.id == child.id).first()
        assert row.status == SieveRun.Status.ERROR
        assert "SieveTurnInFlight" in row.error

    def test_followup_without_parent_session_marks_error(self, db_session, stub_client):
        parent = make_run(db_session, session_id=None, status="ambiguous")
        child = make_run(db_session, kind="follow_up", parent_id=parent.id, status="starting")
        result = sieve_tasks._followup(str(child.id))
        assert result["status"] == "error"
        assert not stub_client.calls


class TestResume:
    def test_dispatches_pending_runs_only(self, db_session, monkeypatch):
        running = make_run(db_session, status="running", session_id="sess_running")
        ambiguous = make_run(db_session, status="ambiguous", session_id=None)
        done = make_run(db_session, status="done", session_id="sess_done")
        followup = make_run(
            db_session, status="running", session_id="sess_running", kind="follow_up",
            parent_id=running.id, baseline_turns=3,
        )

        dispatched: list[tuple] = []

        class StubTask:
            @staticmethod
            def delay(run_id, expect_turns_after=None):
                dispatched.append((run_id, expect_turns_after))

        monkeypatch.setattr(sieve_tasks, "poll_sieve_run_task", StubTask)

        result = sieve_tasks._resume_pending()

        assert result["dispatched"] == 2
        ids = {run_id for run_id, _ in dispatched}
        assert ids == {str(running.id), str(followup.id)}
        assert str(ambiguous.id) not in ids, "创建结果不明的 run 不能重派（可能二次扣费）"
        assert str(done.id) not in ids
        # 追问要用落库的基线接力，否则跨进程恢复后会读到上一轮的答案
        assert (str(followup.id), 3) in dispatched
        assert (str(running.id), None) in dispatched
