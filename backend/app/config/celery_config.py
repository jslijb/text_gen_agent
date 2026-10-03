from celery import Celery
from celery.schedules import crontab
from app.config.settings import settings
from app.config.logging_config import setup_logging

# Celery worker 是独立进程，需单独初始化文件日志（用户规则6）
setup_logging()

celery_app = Celery(
    "ai_novel",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.novel_tasks", "app.tasks.publish_tasks", "app.tasks.knowledge_tasks", "app.tasks.cover_tasks", "app.tasks.sieve_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # v1.5.0：禁用 Celery 劫持 root logger，让 setup_logging() 的 RotatingFileHandler 生效
    # 否则 Worker 进程的日志只输出到控制台，不写入 app.log/error.log，排错困难
    worker_hijack_root_logger=False,
    # 任务超时：8章小说（写作+审核+修订）需较长时间，调高到 30 分钟
    task_time_limit=1800,       # 硬超时 30 分钟，超时直接 kill
    task_soft_time_limit=1740,  # 软超时 29 分钟，给任务机会清理
    # 结果过期时间：7 天，便于排查
    result_expires=7 * 24 * 3600,
    # spec 5.4.1 规则 3：日更调度 + spec 5.3.1 规则 4：知识库过期审视
    # 注意：精确日更时间（按项目 daily_publish_time 配置）由 publish_tasks 内动态调度，
    # 这里配置每小时检查一次待发布章节 + 每日凌晨 3 点清理知识库
    beat_schedule={
        "check-daily-publish": {
            "task": "app.tasks.publish_tasks.check_and_publish_scheduled",
            # 2026-09-15：由固定间隔 3600 秒改为 crontab 每 10 分钟。
            # 原因：schedule=3600 是按间隔排的，触发相位由 beat 进程启动时刻决定
            # （历史日志实测相位为 HH:55、HH:54），加上 publish_tasks 里当时用的是
            # "分钟精确相等"判定，daily_publish_time=08:00 几乎永远撞不上 → 日更从未触发。
            # crontab 把相位钉在 :00/:10/:20…，配合"到点即触发 + 当日去重"才可靠。
            "schedule": crontab(minute="*/10"),
        },
        "cleanup-knowledge": {
            "task": "app.tasks.knowledge_tasks.cleanup_knowledge_base",
            "schedule": crontab(hour=3, minute=0),  # 每日凌晨3点清理过期知识库
        },
        # sieve 抓取：run 要跑几分钟甚至更久，单次 worker 任务的轮询预算用完后
        # 状态留在 running，由这个补轮询任务接力（也是重启/崩溃后的恢复路径）。
        "resume-sieve-runs": {
            "task": "app.tasks.sieve_tasks.resume_pending_sieve_runs",
            "schedule": crontab(minute="*/5"),
        },
    },
)

celery_app.autodiscover_tasks(["app.tasks"])