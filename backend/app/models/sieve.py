import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.config.database import Base
from app.config.types import GUID, JSONType


class SieveRun(Base):
    """sieve 抓取 run 的本地台账。

    存在的主要理由是**续跑**：`POST /api/scrapes` 没有幂等键、被接受就扣费，
    所以 session_id 一旦拿到就必须立刻单独提交（见 app/tasks/sieve_tasks.py），
    崩溃/重启后靠这张表接着轮询，而不是重新建一次 run。
    """

    __tablename__ = "sieve_runs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    # 远端 run id；创建前后的短暂窗口里为 None
    session_id: Mapped[str] = mapped_column(String(128), nullable=True, index=True)
    # starting  已落库、POST 还没回来
    # ambiguous POST 超时/网络错误，无法确认是否创建成功（不自动重试）
    # running   已拿到 session_id，轮询中
    # done / refused / error
    status: Mapped[str] = mapped_column(String(20), default="starting")
    # scrape | follow_up —— 追问也记一条，便于前端按时间线展示
    kind: Mapped[str] = mapped_column(String(20), default="scrape")
    parent_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=True)

    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    target_urls: Mapped[list] = mapped_column(JSONType(), nullable=True)
    fields: Mapped[list] = mapped_column(JSONType(), nullable=True)
    schema: Mapped[dict] = mapped_column(JSONType(), nullable=True)
    output_schema: Mapped[dict] = mapped_column(JSONType(), nullable=True)
    table_shape: Mapped[str] = mapped_column(String(10), nullable=True)
    compliance_mode: Mapped[str] = mapped_column(String(20), default="regular")

    # 远端返回的 turn 计数：判断追问结果是否已推进（done 但 turns 没动 = 还是上一轮的答案）
    turns: Mapped[int] = mapped_column(Integer, default=0)
    # 追问发起前的远端 turn 基线。必须在行上存下来：补轮询任务要用它，
    # 而 `turns` 会在轮询过程中被远端值覆盖掉。
    baseline_turns: Mapped[int] = mapped_column(Integer, nullable=True)

    summary: Mapped[str] = mapped_column(Text, nullable=True)
    result: Mapped[dict] = mapped_column(JSONType(), nullable=True)
    files: Mapped[list] = mapped_column(JSONType(), nullable=True)
    local_files: Mapped[list] = mapped_column(JSONType(), nullable=True)
    schema_conformance: Mapped[str] = mapped_column(String(20), nullable=True)
    refusal_code: Mapped[str] = mapped_column(String(50), nullable=True)
    error: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('starting','ambiguous','running','done','refused','error')",
            name="ck_sieve_run_status",
        ),
        Index("ix_sieve_runs_status_updated", "status", "updated_at"),
    )

    class Status:
        STARTING = "starting"
        AMBIGUOUS = "ambiguous"
        RUNNING = "running"
        DONE = "done"
        REFUSED = "refused"
        ERROR = "error"

    class Kind:
        SCRAPE = "scrape"
        FOLLOW_UP = "follow_up"

    # 还没到终态、需要（或可能需要）继续轮询的状态
    PENDING_STATUSES = (Status.STARTING, Status.RUNNING)
