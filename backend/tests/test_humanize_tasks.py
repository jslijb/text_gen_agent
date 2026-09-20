"""
TDD 测试：humanize_chapter 任务（去AI化核心）。

复现用户反馈的问题：
1. 任务卡住 1 小时进度 0%
2. 切换 quick 策略也要能用

覆盖：
- quick 策略完整流程（不依赖 LLM，可稳定测试）
- ai_score_before 立即提交（前端能看到处理中状态）
- 任务异常时不堆积（明确失败而不是卡住）
"""
import pytest
from unittest.mock import patch, MagicMock
from app.tasks.novel_tasks import humanize_chapter, humanize_project
from app.models.project import Project
from app.models.chapter import Chapter


@pytest.fixture
def project_with_chapters(db_session):
    """创建一个项目 + 2 章（直接写 DB，用于任务测试）"""
    import uuid
    project = Project(
        id=str(uuid.uuid4()),
        name="测试项目",
        synopsis="测试简介",
        genre="悬疑推理",
        target_word_count=10000,
        initial_chapters=2,
        daily_chapters=1,
        status="pending_review",
    )
    db_session.add(project)
    db_session.commit()

    ch1 = Chapter(
        id=str(uuid.uuid4()),
        project_id=project.id,
        chapter_number=1,
        title="第一章",
        content="值得注意的是，他感到非常震惊。不仅如此，这具有重要意义。",
        original_content="",
        review_status="pending",
        publish_status="unpublished",
    )
    ch2 = Chapter(
        id=str(uuid.uuid4()),
        project_id=project.id,
        chapter_number=2,
        title="第二章",
        content="他推开门走了进去。屋里很暗，他摸索着找到灯的开关。",
        original_content="",
        review_status="pending",
        publish_status="unpublished",
    )
    db_session.add_all([ch1, ch2])
    db_session.commit()
    return project, [ch1, ch2]


@pytest.fixture
def project_with_chapters_via_api(client, db_session):
    """通过 API 创建项目+章节（用于 API 测试）"""
    import uuid
    project = Project(
        id=str(uuid.uuid4()),
        name="API测试项目",
        synopsis="API测试简介",
        genre="悬疑推理",
        target_word_count=10000,
        initial_chapters=2,
        daily_chapters=1,
        status="pending_review",
    )
    db_session.add(project)
    db_session.commit()
    ch1 = Chapter(
        id=str(uuid.uuid4()),
        project_id=project.id,
        chapter_number=1,
        title="第一章",
        content="值得注意的是，他感到非常震惊。不仅如此，这具有重要意义。",
        original_content="",
        review_status="pending",
        publish_status="unpublished",
    )
    ch2 = Chapter(
        id=str(uuid.uuid4()),
        project_id=project.id,
        chapter_number=2,
        title="第二章",
        content="他推开门走了进去。屋里很暗，他摸索着找到灯的开关。",
        original_content="",
        review_status="pending",
        publish_status="unpublished",
    )
    db_session.add_all([ch1, ch2])
    db_session.commit()
    return project.id, [ch1, ch2]


class TestHumanizeChapterQuick:
    """quick 策略不依赖 LLM，是验证任务流程的关键测试"""

    def test_quick_strategy_completes_and_writes_scores(self, db_session, project_with_chapters):
        """quick 策略应完整执行：写入 ai_score_before 和 ai_score_after"""
        project, chapters = project_with_chapters
        ch1 = chapters[0]

        # 执行 quick 策略（不走 LLM，纯正则）
        humanize_chapter.apply(args=[str(ch1.id), "quick"]).get()

        db_session.expire_all()
        updated = db_session.query(Chapter).filter(Chapter.id == ch1.id).first()
        assert updated.ai_score_before is not None, "ai_score_before 应已写入"
        assert updated.ai_score_after is not None, "ai_score_after 应已写入"
        assert updated.original_content != "", "original_content 应保存原文"
        assert "值得注意的是" not in updated.content, "quick 应替换掉 AI 套话"

    def test_quick_strategy_speed(self, db_session, project_with_chapters):
        """quick 策略应在 30 秒内完成（不卡住）"""
        import time
        project, chapters = project_with_chapters
        ch1 = chapters[0]

        start = time.time()
        humanize_chapter.apply(args=[str(ch1.id), "quick"]).get()
        elapsed = time.time() - start

        assert elapsed < 30, f"quick 策略耗时 {elapsed:.1f}s，应 <30s（用户反馈卡 1 小时）"

    def test_humanize_chapter_exception_does_not_block(self, db_session, project_with_chapters):
        """任务异常时应明确失败，不卡住"""
        project, chapters = project_with_chapters
        ch1 = chapters[0]

        # mock humanize 抛异常（模拟 LLM 挂了）
        import asyncio
        from app.services.humanizer import Humanizer
        original_humanize = Humanizer.humanize
        async def mock_humanize(self, text, strategy="default"):
            raise Exception("模拟LLM挂了")
        with patch.object(Humanizer, "humanize", mock_humanize):
            # 不应抛异常（任务内已 try/except），应正常返回
            humanize_chapter.apply(args=[str(ch1.id), "quick"]).get()

        db_session.expire_all()
        updated = db_session.query(Chapter).filter(Chapter.id == ch1.id).first()
        # 异常时 ai_score_after 不应写入（任务在 humanize 步骤失败）
        assert updated.ai_score_after is None


class TestHumanizeProjectBatch:
    """全局去 AI 化任务测试"""

    def test_batch_quick_processes_all_chapters(self, db_session, project_with_chapters):
        """全局 quick 策略应处理所有章节，不应用 .get() 同步等待子任务"""
        project, chapters = project_with_chapters

        humanize_project.apply(args=[str(project.id), "quick"]).get()

        db_session.expire_all()
        all_chapters = db_session.query(Chapter).filter(Chapter.project_id == project.id).order_by(Chapter.chapter_number).all()
        assert len(all_chapters) == 2
        for ch in all_chapters:
            assert ch.ai_score_before is not None, f"第{ch.chapter_number}章 ai_score_before 未写入"
            assert ch.ai_score_after is not None, f"第{ch.chapter_number}章 ai_score_after 未写入"

    def test_batch_no_get_within_task(self, db_session, project_with_chapters, monkeypatch):
        """humanize_project 不应调用 .get() 同步等待子任务（Celery 禁止）"""
        project, chapters = project_with_chapters

        # 监控是否调用了 .get()
        from app.tasks.novel_tasks import humanize_chapter
        get_called = {"n": 0}
        original_apply = humanize_chapter.apply
        def mock_apply(*args, **kwargs):
            result = original_apply(*args, **kwargs)
            original_get = result.get
            def mock_get(*a, **k):
                get_called["n"] += 1
                return original_get(*a, **k)
            result.get = mock_get
            return result
        monkeypatch.setattr(humanize_chapter, "apply", mock_apply)

        humanize_project.apply(args=[str(project.id), "quick"]).get()

        # 不应调用 .get()（应直接调用函数体）
        assert get_called["n"] == 0, f"humanize_project 调用了 {get_called['n']} 次 .get()，应直接调用函数"

    def test_batch_empty_project(self, db_session):
        """空项目不应抛异常"""
        import uuid
        empty_pid = str(uuid.uuid4())
        # 不创建任何章节，应安全返回
        humanize_project.apply(args=[empty_pid, "quick"]).get()


class TestTaskResilience:
    """任务健壮性：不卡住、不堆积"""

    def test_nonexistent_chapter_id_safe(self, db_session):
        """不存在的章节 ID 应安全失败，不卡住"""
        import uuid
        fake_id = str(uuid.uuid4())
        # 应正常返回，不抛异常
        humanize_chapter.apply(args=[fake_id, "quick"]).get()


class TestQuickStrategyNoLLM:
    """quick 策略应避免 LLM 调用（用户反馈 quick 也要几分钟）。
    quick 是纯正则策略，评分应只用统计特征，不应调 LLM。
    """

    def test_quick_humanize_score_uses_statistical_only(self, db_session, project_with_chapters, monkeypatch):
        """quick 策略的 evaluate_ai_score 应只走统计评分，不调 LLM"""
        project, chapters = project_with_chapters
        ch1 = chapters[0]

        # 监控 ModelManager.call_llm，quick 不应调用它
        from app.services.model_manager import ModelManager
        call_count = {"n": 0}
        original_call = ModelManager.call_llm
        def mock_call(self, *args, **kwargs):
            call_count["n"] += 1
            return original_call(self, *args, **kwargs)
        monkeypatch.setattr(ModelManager, "call_llm", mock_call)

        # quick 策略跑完整流程
        humanize_chapter.apply(args=[str(ch1.id), "quick"]).get()

        # quick 应该几乎不调 LLM（统计评分不调 LLM）
        # 允许 0-1 次（一致性检查可能调 1 次，但评分不应调）
        assert call_count["n"] <= 1, f"quick 策略调用了 {call_count['n']} 次 LLM，应 <=1（统计评分不应调 LLM）"

    def test_quick_strategy_speed_under_10s(self, db_session, project_with_chapters, monkeypatch):
        """quick 策略应在 10 秒内完成（不卡住）"""
        import time
        project, chapters = project_with_chapters
        ch1 = chapters[0]

        # mock 掉所有 LLM 调用（quick 不应依赖 LLM）
        from app.services.model_manager import ModelManager
        monkeypatch.setattr(ModelManager, "call_llm", lambda *a, **k: "5")

        start = time.time()
        humanize_chapter.apply(args=[str(ch1.id), "quick"]).get()
        elapsed = time.time() - start

        assert elapsed < 10, f"quick 策略耗时 {elapsed:.1f}s，应 <10s（无 LLM 调用）"


class TestHumanizeStatusAPI:
    """任务状态查询 API（前端判断任务是否真在跑）"""

    def test_status_endpoint_returns_progress(self, client, project_with_chapters_via_api):
        """humanize-status 应返回 task_state + completed/total 进度。
        不依赖 Redis：直接同步跑任务，再用 fake task_id 查状态。
        """
        project_id, chapters = project_with_chapters_via_api
        from app.tasks.novel_tasks import humanize_project
        humanize_project.apply(args=[str(project_id), "quick"]).get()

        import uuid
        fake_task_id = str(uuid.uuid4())
        mock_async_result = MagicMock()
        mock_async_result.state = "SUCCESS"
        mock_async_result.ready.return_value = True
        mock_async_result.result = "done"
        with patch("app.config.celery_config.celery_app.AsyncResult", return_value=mock_async_result):
            res = client.get(
                f"/api/v1/projects/{project_id}/chapters/humanize-status?task_id={fake_task_id}"
            )
        assert res.status_code == 200
        data = res.json()
        assert data["total_chapters"] == 2
        assert data["completed"] == 2
        assert data["progress_pct"] == 100

    def test_status_endpoint_pending_task(self, client, project_with_chapters_via_api):
        """PENDING 任务（worker 不在线时）应返回 PENDING + 0%"""
        project_id, _ = project_with_chapters_via_api
        import uuid
        fake_task_id = str(uuid.uuid4())
        mock_async_result = MagicMock()
        mock_async_result.state = "PENDING"
        mock_async_result.ready.return_value = False
        mock_async_result.result = None
        with patch("app.config.celery_config.celery_app.AsyncResult", return_value=mock_async_result):
            res = client.get(
                f"/api/v1/projects/{project_id}/chapters/humanize-status?task_id={fake_task_id}"
            )
        assert res.status_code == 200
        data = res.json()
        assert data["task_state"] == "PENDING"
        assert data["progress_pct"] == 0
