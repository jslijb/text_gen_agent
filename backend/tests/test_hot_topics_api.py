"""
TDD Red 阶段：热点创意生成 API 测试。
对应 design.md 热点数据与创意生成 API。
"""
import pytest
from unittest.mock import patch, MagicMock


BAIDU_HOT_NOVEL_HTML = """
<html><body>
<div id="sanRoot" theme="novel">
<!--s-data:{"data":{"cards":[{"component":"textImgListVerticalNormal","content":[{"appUrl":"https://www.baidu.com/s?wd=儒道至圣","desc":"读书人掌握天地之力的世界。","hotChange":"up","hotScore":"185376","index":0,"query":"儒道至圣 小说","show":["作者：永恒之火","类型：玄幻"],"word":"儒道至圣"}],"more":0,"text":"小说榜","typeName":"novel"}],"curBoardName":"小说榜","platform":"pc","tab":"novel"}}-->
  <div class="category-wrap_iQLoo">
    <a class="img-wrapper_29V76"><div class="index_1Ew5p c-index-bg1"> 1 </div></a>
    <a class="trend_2RttY"><div class="hot-index_1Bl1a"> 185376 </div></a>
    <div class="content_1YWBm">
      <a class="title_dIF3B"><div class="c-single-text-ellipsis"> 儒道至圣 </div></a>
      <div class="intro_1l0wp"> 作者：永恒之火 </div>
      <div class="intro_1l0wp"> 类型：玄幻 </div>
      <div class="c-single-text-ellipsis desc_3CTjT"> 读书人掌握天地之力的世界。 <a class="look-more_3oNWC">查看更多&gt;</a></div>
    </div>
  </div>
</div>
</body></html>
"""


@pytest.fixture(autouse=True)
def clear_fetcher_cache():
    """每个测试前清空 HotTopicFetcher 单例缓存，避免跨测试污染"""
    from app.services.hot_topic_fetcher import HotTopicFetcher
    HotTopicFetcher().clear_cache()
    yield


class TestHotTopicsNovelAPI:
    """GET /api/v1/hot-topics/novel"""

    def test_returns_topics_and_distribution(self, client):
        """返回榜单+题材分布"""
        mock_resp = MagicMock()
        mock_resp.text = BAIDU_HOT_NOVEL_HTML
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        with patch("app.services.hot_topic_fetcher.requests.get", return_value=mock_resp):
            r = client.get("/api/v1/hot-topics/novel")

        assert r.status_code == 200
        data = r.json()
        assert data["source"] == "baidu_hot_search"
        assert data["degraded"] is False
        assert len(data["topics"]) >= 1
        assert "genre_distribution" in data
        assert "fetched_at" in data

    def test_force_refresh_query_param(self, client):
        """force_refresh=true 应绕过缓存"""
        mock_resp = MagicMock()
        mock_resp.text = BAIDU_HOT_NOVEL_HTML
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        with patch("app.services.hot_topic_fetcher.requests.get", return_value=mock_resp) as mock_get:
            client.get("/api/v1/hot-topics/novel")
            client.get("/api/v1/hot-topics/novel?force_refresh=true")

        assert mock_get.call_count == 2

    def test_degraded_mode_marked(self, client):
        """降级模式应标注 degraded=true"""
        with patch("app.services.hot_topic_fetcher.requests.get", side_effect=Exception("网络不可达")):
            mock_kb = MagicMock()
            mock_kb.search_trending_features.return_value = [
                {"topic": "玄幻", "opening_pattern": "金手指", "content": "爆款特征"},
            ]
            with patch("app.services.hot_topic_fetcher.KnowledgeBaseManager", return_value=mock_kb):
                r = client.get("/api/v1/hot-topics/novel")

        assert r.status_code == 200
        data = r.json()
        assert data["degraded"] is True


class TestGenerateSynopsisAPI:
    """POST /api/v1/hot-topics/generate-synopsis"""

    def test_returns_three_synopses(self, client):
        """返回 3 个候选梗概，每个 200-300 字"""
        synopses = ["梗概一" * 50, "梗概二" * 50, "梗概三" * 50]
        with patch("app.services.hot_topic_fetcher.ModelManager") as MockMgr, \
             patch("app.services.hot_topic_fetcher.HotTopicFetcher") as MockFetcher:
            MockMgr.return_value.call_llm.return_value = "\n\n".join(synopses)
            MockFetcher.return_value.fetch_hot_novels.return_value = {
                "topics": [{"title": "儒道至圣"}], "source": "baidu", "degraded": False,
                "fetched_at": "2026-01-01", "cache_ttl_seconds": 300, "genre_distribution": [],
            }
            r = client.post("/api/v1/hot-topics/generate-synopsis", json={
                "genre": "恐怖推理",
                "reference_topics": ["儒道至圣"],
                "count": 3,
            })

        assert r.status_code == 200
        data = r.json()
        assert "synopses" in data
        assert len(data["synopses"]) == 3
        assert "model_used" in data

    def test_invalid_genre_returns_422(self, client):
        """非法题材应返回 422"""
        r = client.post("/api/v1/hot-topics/generate-synopsis", json={
            "genre": "不存在的题材",
            "reference_topics": [],
            "count": 3,
        })
        assert r.status_code == 422

    def test_invalid_genre_literal_returns_422(self, client):
        """不在 GenreLiteral 枚举中的题材应返回 422"""
        r = client.post("/api/v1/hot-topics/generate-synopsis", json={
            "genre": "悬疑推理",
            "reference_topics": [],
            "count": 3,
        })
        assert r.status_code == 422


class TestGenerateTitleAPI:
    """POST /api/v1/hot-topics/generate-title"""

    def test_returns_five_titles(self, client):
        """返回 5 个候选标题"""
        titles = ["深夜古宅的钟声", "迷雾中的真相", "第七个嫌疑人", "消失的指纹", "午夜来信之谜"]
        with patch("app.services.hot_topic_fetcher.ModelManager") as MockMgr:
            MockMgr.return_value.call_llm.return_value = "\n".join(titles)
            r = client.post("/api/v1/hot-topics/generate-title", json={
                "synopsis": "一个悬疑故事梗概，讲述深夜古宅里发生的离奇事件",
                "genre": "恐怖推理",
                "count": 5,
            })

        assert r.status_code == 200
        data = r.json()
        assert "titles" in data
        assert len(data["titles"]) == 5

    def test_missing_synopsis_returns_422(self, client):
        """缺少 synopsis 应返回 422"""
        r = client.post("/api/v1/hot-topics/generate-title", json={
            "genre": "恐怖推理",
            "count": 5,
        })
        assert r.status_code == 422
