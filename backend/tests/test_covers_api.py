"""TDD 测试：封面 API 端点（spec 5.8 / design 2.2）"""
import uuid
import pytest
from unittest.mock import patch

from app.models.project import Project


@pytest.fixture
def sample_project(db_session):
    """创建测试项目"""
    project = Project(
        id=str(uuid.uuid4()),
        name="夜色微凉",
        synopsis="一个发生在雨夜的悬疑故事，主人公追寻真相...",
        genre="悬疑推理",
        target_word_count=20000,
        initial_chapters=10,
        daily_chapters=2,
        status="draft",
    )
    db_session.add(project)
    db_session.commit()
    return project


@pytest.fixture(autouse=True)
def clear_cover_cache():
    """每个测试前清理（避免状态污染）"""
    yield


class TestCoverGenerate:
    """POST /projects/{id}/cover/generate 测试"""

    def test_generate_success(self, client, db_session, sample_project):
        """成功生成封面（spec 5.8.1 规则 4）"""
        mock_result = {
            "cover_url": "/static/covers/test_123.png",
            "prompt_used": "A mystery book cover...",
            "model_used": "wanx2.1-t2i-plus",
        }
        with patch("app.api.covers.cover_service.generate_cover", return_value=mock_result):
            resp = client.post(
                f"/api/v1/projects/{sample_project.id}/cover/generate",
                json={"gender": "无性向", "genre": "悬疑"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["cover_url"] == "/static/covers/test_123.png"
        assert "prompt_used" in data
        assert data["model_used"] == "wanx2.1-t2i-plus"

        # 验证 Project.cover_url 已更新
        db_session.expire_all()
        proj = db_session.query(Project).filter(Project.id == sample_project.id).first()
        assert proj.cover_url == "/static/covers/test_123.png"

    def test_generate_project_not_found(self, client, db_session):
        """项目不存在返回 404"""
        fake_id = str(uuid.uuid4())
        resp = client.post(
            f"/api/v1/projects/{fake_id}/cover/generate",
            json={"gender": "无性向", "genre": "悬疑"},
        )
        assert resp.status_code == 404
        assert "项目不存在" in resp.json()["detail"]

    def test_generate_invalid_gender(self, client, db_session, sample_project):
        """gender 参数非法返回 422（spec 5.8.1 规则 2 枚举校验）"""
        resp = client.post(
            f"/api/v1/projects/{sample_project.id}/cover/generate",
            json={"gender": "未知性向", "genre": "悬疑"},
        )
        assert resp.status_code == 422

    def test_generate_service_unavailable(self, client, db_session, sample_project):
        """通义万相 API 不可达返回 503（spec 5.8.3 异常场景 1）"""
        from app.services.cover_service import CoverGenerationError
        with patch(
            "app.api.covers.cover_service.generate_cover",
            side_effect=CoverGenerationError("API 不可达"),
        ):
            resp = client.post(
                f"/api/v1/projects/{sample_project.id}/cover/generate",
                json={"gender": "无性向", "genre": "悬疑"},
            )
        assert resp.status_code == 503
        assert "不可用" in resp.json()["detail"]


class TestGetCover:
    """GET /projects/{id}/cover 测试"""

    def test_get_cover_with_url(self, client, db_session, sample_project):
        """有封面时返回 cover_url（spec 5.8.1 规则 6）"""
        sample_project.cover_url = "/static/covers/abc.png"
        db_session.commit()
        resp = client.get(f"/api/v1/projects/{sample_project.id}/cover")
        assert resp.status_code == 200
        assert resp.json()["cover_url"] == "/static/covers/abc.png"

    def test_get_cover_without_url(self, client, db_session, sample_project):
        """无封面时返回 null"""
        resp = client.get(f"/api/v1/projects/{sample_project.id}/cover")
        assert resp.status_code == 200
        assert resp.json()["cover_url"] is None

    def test_get_cover_project_not_found(self, client, db_session):
        """项目不存在返回 404"""
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/projects/{fake_id}/cover")
        assert resp.status_code == 404
