"""
TDD 测试：去AI化任务的暂停/停止/恢复控制。
用户需求：
- 暂停：下次启动按当前进度继续（跳过已处理章节）
- 停止：下次启动从头开始（清除所有进度）
"""
import pytest
from unittest.mock import patch
from app.tasks.novel_tasks import humanize_project, humanize_chapter
from app.models.project import Project
from app.models.chapter import Chapter


@pytest.fixture
def project_with_chapters(db_session):
    import uuid
    project = Project(
        id=str(uuid.uuid4()),
        name="控制测试项目",
        synopsis="测试",
        genre="悬疑",
        target_word_count=10000,
        initial_chapters=2,
        daily_chapters=1,
        status="pending_review",
    )
    db_session.add(project)
    db_session.commit()
    chapters = []
    for i in range(1, 4):  # 3 章
        ch = Chapter(
            id=str(uuid.uuid4()),
            project_id=project.id,
            chapter_number=i,
            title=f"第{i}章",
            content=f"值得注意的是，他感到非常震惊。第{i}章内容。",
            original_content="",
            review_status="pending",
            publish_status="unpublished",
        )
        db_session.add(ch)
        chapters.append(ch)
    db_session.commit()
    return project, chapters


class TestHumanizePauseStop:
    """暂停/停止/恢复功能测试"""

    def test_skip_already_humanized_chapters(self, db_session, project_with_chapters):
        """断点续跑：恢复时应跳过已有 ai_score_after 的章节"""
        project, chapters = project_with_chapters
        # 模拟第1章已处理完
        chapters[0].ai_score_before = 30.0
        chapters[0].ai_score_after = 25.0
        chapters[0].original_content = chapters[0].content
        db_session.commit()

        # 跑 humanize_project，应跳过第1章，只处理第2、3章
        humanize_project.apply(args=[str(project.id), "quick"]).get()

        db_session.expire_all()
        all_chs = db_session.query(Chapter).filter(Chapter.project_id == project.id).order_by(Chapter.chapter_number).all()
        # 第1章保持原值（未被重新处理）
        assert all_chs[0].ai_score_after == 25.0
        # 第2、3章应被处理
        assert all_chs[1].ai_score_after is not None
        assert all_chs[2].ai_score_after is not None

    def test_pause_stops_processing(self, db_session, project_with_chapters, monkeypatch):
        """暂停标志应让任务停止处理后续章节"""
        project, chapters = project_with_chapters

        # mock Redis 检查：第1章处理后返回暂停标志
        call_count = {"n": 0}
        import app.tasks.novel_tasks as novel_tasks_mod
        original_check = getattr(novel_tasks_mod, "_is_paused", None)
        def mock_is_paused(pid):
            call_count["n"] += 1
            return call_count["n"] > 1  # 第2次检查开始返回 True（暂停）
        if original_check:
            monkeypatch.setattr(novel_tasks_mod, "_is_paused", mock_is_paused)

        humanize_project.apply(args=[str(project.id), "quick"]).get()

        db_session.expire_all()
        all_chs = db_session.query(Chapter).filter(Chapter.project_id == project.id).order_by(Chapter.chapter_number).all()
        # 第1章应处理了
        assert all_chs[0].ai_score_after is not None
        # 第2、3章不应处理（因为暂停了）
        assert all_chs[1].ai_score_after is None
        assert all_chs[2].ai_score_after is None


class TestHumanizeStopReset:
    """停止后重置进度测试"""

    def test_stop_resets_all_progress(self, db_session, project_with_chapters):
        """停止应清除所有章节的 ai_score_before/after"""
        project, chapters = project_with_chapters
        # 先处理所有章节
        humanize_project.apply(args=[str(project.id), "quick"]).get()
        db_session.expire_all()
        all_chs = db_session.query(Chapter).filter(Chapter.project_id == project.id).all()
        assert all(c.ai_score_after is not None for c in all_chs)

        # 停止：重置进度
        import app.tasks.novel_tasks as novel_tasks_mod
        novel_tasks_mod.reset_humanize_progress(str(project.id))

        db_session.expire_all()
        all_chs = db_session.query(Chapter).filter(Chapter.project_id == project.id).all()
        for c in all_chs:
            assert c.ai_score_before is None, f"第{c.chapter_number}章 ai_score_before 未清除"
            assert c.ai_score_after is None, f"第{c.chapter_number}章 ai_score_after 未清除"
