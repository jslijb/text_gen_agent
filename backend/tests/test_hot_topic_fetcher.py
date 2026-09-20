"""
TDD Red 阶段：热点数据抓取服务测试。
对应 spec 5.4：热点数据获取与创意生成
- 百度热搜小说榜抓取
- 缓存命中
- 降级到本地知识库
- 题材分布统计
- 禁止抓取正文
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


# 百度热搜小说榜 HTML 样本（基于真实页面结构，含 s-data 注释 + DOM 哈希 class）
# 真实页面采用 Vue SSR，数据以 JSON 形式嵌入在 <!--s-data:{...}--> 注释中
BAIDU_HOT_NOVEL_HTML = """
<html><body>
<div id="sanRoot" theme="novel">
<!--s-data:{"data":{"cards":[{"component":"textImgListVerticalNormal","content":[{"appUrl":"https://www.baidu.com/s?wd=儒道至圣","desc":"这是一个读书人掌握天地之力的世界。才气在身，诗可杀敌。","hotChange":"up","hotScore":"185376","index":0,"query":"儒道至圣 小说","show":["作者：永恒之火","类型：玄幻"],"word":"儒道至圣"},{"appUrl":"https://www.baidu.com/s?wd=青山","desc":"都市青年的奋斗故事。","hotChange":"up","hotScore":"182956","index":1,"query":"青山 小说","show":["作者：小明","类型：都市"],"word":"青山"},{"appUrl":"https://www.baidu.com/s?wd=古宅迷踪","desc":"一座古宅里的连环谜案。","hotChange":"up","hotScore":"150000","index":2,"query":"古宅迷踪 小说","show":["作者：阿加莎","类型：悬疑"],"word":"古宅迷踪"}],"more":0,"text":"小说榜","typeName":"novel"}],"curBoardName":"小说榜","platform":"pc","tab":"novel"}}-->
  <div class="category-wrap_iQLoo">
    <a class="img-wrapper_29V76"><div class="index_1Ew5p c-index-bg1"> 1 </div></a>
    <a class="trend_2RttY"><div class="hot-index_1Bl1a"> 185376 </div></a>
    <div class="content_1YWBm">
      <a class="title_dIF3B"><div class="c-single-text-ellipsis"> 儒道至圣 </div></a>
      <div class="intro_1l0wp"> 作者：永恒之火 </div>
      <div class="intro_1l0wp"> 类型：玄幻 </div>
      <div class="c-single-text-ellipsis desc_3CTjT"> 这是一个读书人掌握天地之力的世界。才气在身，诗可杀敌。 <a class="look-more_3oNWC">查看更多&gt;</a></div>
    </div>
  </div>
  <div class="category-wrap_iQLoo">
    <a class="img-wrapper_29V76"><div class="index_1Ew5p c-index-bg2"> 2 </div></a>
    <a class="trend_2RttY"><div class="hot-index_1Bl1a"> 182956 </div></a>
    <div class="content_1YWBm">
      <a class="title_dIF3B"><div class="c-single-text-ellipsis"> 青山 </div></a>
      <div class="intro_1l0wp"> 作者：小明 </div>
      <div class="intro_1l0wp"> 类型：都市 </div>
      <div class="c-single-text-ellipsis desc_3CTjT"> 都市青年的奋斗故事。 <a class="look-more_3oNWC">查看更多&gt;</a></div>
    </div>
  </div>
  <div class="category-wrap_iQLoo">
    <a class="img-wrapper_29V76"><div class="index_1Ew5p c-index-bg3"> 3 </div></a>
    <a class="trend_2RttY"><div class="hot-index_1Bl1a"> 150000 </div></a>
    <div class="content_1YWBm">
      <a class="title_dIF3B"><div class="c-single-text-ellipsis"> 古宅迷踪 </div></a>
      <div class="intro_1l0wp"> 作者：阿加莎 </div>
      <div class="intro_1l0wp"> 类型：悬疑 </div>
      <div class="c-single-text-ellipsis desc_3CTjT"> 一座古宅里的连环谜案。 <a class="look-more_3oNWC">查看更多&gt;</a></div>
    </div>
  </div>
</div>
</body></html>
"""

# 仅 DOM 结构（无 s-data 注释）- 用于测试 DOM 兜底路径
BAIDU_HOT_NOVEL_HTML_DOM_ONLY = """
<html><body>
<div id="sanRoot" theme="novel">
  <div class="category-wrap_iQLoo">
    <a class="img-wrapper_29V76"><div class="index_1Ew5p c-index-bg1"> 1 </div></a>
    <a class="trend_2RttY"><div class="hot-index_1Bl1a"> 185376 </div></a>
    <div class="content_1YWBm">
      <a class="title_dIF3B"><div class="c-single-text-ellipsis"> 儒道至圣 </div></a>
      <div class="intro_1l0wp"> 作者：永恒之火 </div>
      <div class="intro_1l0wp"> 类型：玄幻 </div>
      <div class="c-single-text-ellipsis desc_3CTjT"> 这是一个读书人掌握天地之力的世界。才气在身，诗可杀敌。 <a class="look-more_3oNWC">查看更多&gt;</a></div>
    </div>
  </div>
  <div class="category-wrap_iQLoo">
    <a class="img-wrapper_29V76"><div class="index_1Ew5p c-index-bg2"> 2 </div></a>
    <a class="trend_2RttY"><div class="hot-index_1Bl1a"> 182956 </div></a>
    <div class="content_1YWBm">
      <a class="title_dIF3B"><div class="c-single-text-ellipsis"> 青山 </div></a>
      <div class="intro_1l0wp"> 作者：小明 </div>
      <div class="intro_1l0wp"> 类型：都市 </div>
      <div class="c-single-text-ellipsis desc_3CTjT"> 都市青年的奋斗故事。 <a class="look-more_3oNWC">查看更多&gt;</a></div>
    </div>
  </div>
</div>
</body></html>
"""


@pytest.fixture
def fetcher():
    """每个测试用独立实例，避免缓存污染"""
    from app.services.hot_topic_fetcher import HotTopicFetcher
    f = HotTopicFetcher()
    f.clear_cache()
    return f


class TestFetchHotNovels:
    """百度热搜抓取测试"""

    def test_fetch_success_returns_topics(self, fetcher):
        """抓取成功：返回榜单数据，每条包含 5 项必填字段"""
        mock_resp = MagicMock()
        mock_resp.text = BAIDU_HOT_NOVEL_HTML
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        with patch("app.services.hot_topic_fetcher.requests.get", return_value=mock_resp) as mock_get:
            result = fetcher.fetch_hot_novels()

        assert mock_get.called, "应调用 requests.get"
        assert result["source"] == "baidu_hot_search"
        assert result["degraded"] is False, "正常抓取不应降级"
        assert "fetched_at" in result
        assert "cache_ttl_seconds" in result
        topics = result["topics"]
        assert len(topics) == 3, "应解析出 3 条"
        # 每条必须有 5 项字段（spec 5.4.1 规则 2）
        for t in topics:
            assert t["title"], "书名不能为空"
            assert t["author"], "作者不能为空"
            assert t["genre"], "类型不能为空"
            assert isinstance(t["hot_index"], int) and t["hot_index"] > 0, "热搜指数必须是正整数"
            assert t["description"], "简介不能为空"
        # 第 1 条应是儒道至圣
        assert topics[0]["title"] == "儒道至圣"
        assert topics[0]["author"] == "永恒之火"
        assert topics[0]["genre"] == "玄幻"
        assert topics[0]["hot_index"] == 185376

    def test_cache_hit_no_second_request(self, fetcher):
        """缓存命中：连续两次调用，第二次不发请求"""
        mock_resp = MagicMock()
        mock_resp.text = BAIDU_HOT_NOVEL_HTML
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        with patch("app.services.hot_topic_fetcher.requests.get", return_value=mock_resp) as mock_get:
            fetcher.fetch_hot_novels()
            fetcher.fetch_hot_novels()  # 第二次应命中缓存

        assert mock_get.call_count == 1, "第二次应命中缓存不发请求"

    def test_force_refresh_bypasses_cache(self, fetcher):
        """force_refresh=True 应绕过缓存"""
        mock_resp = MagicMock()
        mock_resp.text = BAIDU_HOT_NOVEL_HTML
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        with patch("app.services.hot_topic_fetcher.requests.get", return_value=mock_resp) as mock_get:
            fetcher.fetch_hot_novels()
            fetcher.fetch_hot_novels(force_refresh=True)

        assert mock_get.call_count == 2, "force_refresh 应绕过缓存"

    def test_no_full_content_in_result(self, fetcher):
        """禁止项：返回数据不得包含小说正文"""
        mock_resp = MagicMock()
        mock_resp.text = BAIDU_HOT_NOVEL_HTML
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        with patch("app.services.hot_topic_fetcher.requests.get", return_value=mock_resp):
            result = fetcher.fetch_hot_novels()

        for t in result["topics"]:
            assert "content" not in t, "不得包含正文字段"
            assert "正文" not in t["description"], "简介不得包含正文标记"

    def test_dom_fallback_when_no_s_data(self, fetcher):
        """DOM 兜底：s-data 注释缺失时，应回退到 DOM 模糊解析"""
        mock_resp = MagicMock()
        mock_resp.text = BAIDU_HOT_NOVEL_HTML_DOM_ONLY
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        with patch("app.services.hot_topic_fetcher.requests.get", return_value=mock_resp):
            result = fetcher.fetch_hot_novels()

        assert result["source"] == "baidu_hot_search"
        topics = result["topics"]
        assert len(topics) == 2, "DOM 兜底应解析出 2 条"
        # 第 1 条数据应正确解析（含"查看更多>"链接被剥离）
        assert topics[0]["title"] == "儒道至圣"
        assert topics[0]["author"] == "永恒之火"
        assert topics[0]["genre"] == "玄幻"
        assert topics[0]["hot_index"] == 185376
        assert "查看更多" not in topics[0]["description"], "简介应剥离查看更多链接"
        assert topics[0]["rank"] == 1


class TestDegradeToKnowledgeBase:
    """降级到本地知识库测试"""

    def test_degrade_when_request_fails(self, fetcher):
        """requests 失败 → 回退到 KnowledgeBaseManager"""
        # mock requests.get 抛异常
        with patch("app.services.hot_topic_fetcher.requests.get", side_effect=Exception("网络不可达")):
            # mock KnowledgeBaseManager.search_trending_features
            mock_kb = MagicMock()
            mock_kb.search_trending_features.return_value = [
                {"topic": "玄幻", "opening_pattern": "金手指觉醒", "emotion_type": "thrill", "content": "爆款玄幻特征"},
            ]
            with patch("app.services.hot_topic_fetcher.KnowledgeBaseManager", return_value=mock_kb):
                result = fetcher.fetch_hot_novels()

        assert result["degraded"] is True, "应标注降级模式"
        assert result["source"] != "baidu_hot_search", "降级来源不应该是百度热搜"
        mock_kb.search_trending_features.assert_called_once()

    def test_degrade_when_html_empty(self, fetcher):
        """HTML 解析为空 → 降级"""
        mock_resp = MagicMock()
        mock_resp.text = "<html><body>无榜单数据</body></html>"
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        with patch("app.services.hot_topic_fetcher.requests.get", return_value=mock_resp):
            mock_kb = MagicMock()
            mock_kb.search_trending_features.return_value = [
                {"topic": "都市", "opening_pattern": "职场开局", "content": "都市爆款"},
            ]
            with patch("app.services.hot_topic_fetcher.KnowledgeBaseManager", return_value=mock_kb):
                result = fetcher.fetch_hot_novels()

        assert result["degraded"] is True
        assert len(result["topics"]) > 0, "降级后应至少有 1 条知识库数据"

    def test_raise_when_both_fail(self, fetcher):
        """百度不可达 + 本地知识库也为空 → 抛 HotTopicUnavailable"""
        with patch("app.services.hot_topic_fetcher.requests.get", side_effect=Exception("网络不可达")):
            mock_kb = MagicMock()
            mock_kb.search_trending_features.return_value = []
            with patch("app.services.hot_topic_fetcher.KnowledgeBaseManager", return_value=mock_kb):
                from app.services.hot_topic_fetcher import HotTopicUnavailable
                with pytest.raises(HotTopicUnavailable):
                    fetcher.fetch_hot_novels()


class TestGenreDistribution:
    """题材分布统计测试"""

    def test_genre_distribution_aggregation(self, fetcher):
        """按题材聚合统计热门占比"""
        mock_resp = MagicMock()
        mock_resp.text = BAIDU_HOT_NOVEL_HTML
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        with patch("app.services.hot_topic_fetcher.requests.get", return_value=mock_resp):
            result = fetcher.fetch_hot_novels()

        dist = result["genre_distribution"]
        assert isinstance(dist, list)
        assert len(dist) > 0
        # 每条分布必须有 genre、count、percentage
        for d in dist:
            assert "genre" in d
            assert "count" in d
            assert "percentage" in d
            assert 0 <= d["percentage"] <= 100
        # 玄幻 1 条 / 共 3 条 → 33%
        genres = {d["genre"]: d for d in dist}
        assert genres["玄幻"]["count"] == 1
        assert genres["玄幻"]["percentage"] == pytest.approx(33.33, rel=0.1)

    def test_top_n_limit(self, fetcher):
        """top_n 参数应限制返回条数"""
        mock_resp = MagicMock()
        mock_resp.text = BAIDU_HOT_NOVEL_HTML
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        with patch("app.services.hot_topic_fetcher.requests.get", return_value=mock_resp):
            result = fetcher.fetch_hot_novels(top_n=2)

        assert len(result["topics"]) == 2, "top_n=2 应只返回 2 条"


class TestGenderFilter:
    """spec v1.4.1: top 20 按性向筛选（百度 genre → gender 映射 + 筛选）"""

    def test_topic_has_gender_field(self, fetcher):
        """每条 topic 必须包含 gender 字段"""
        mock_resp = MagicMock()
        mock_resp.text = BAIDU_HOT_NOVEL_HTML
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        with patch("app.services.hot_topic_fetcher.requests.get", return_value=mock_resp):
            result = fetcher.fetch_hot_novels(top_n=10)

        for t in result["topics"]:
            assert "gender" in t, "每条 topic 必须包含 gender 字段"
            assert t["gender"] in ("男性向", "女性向", "无性向")

    def test_filter_male_returns_2(self, fetcher):
        """筛选男性向：mock 数据中玄幻+都市=2 条"""
        mock_resp = MagicMock()
        mock_resp.text = BAIDU_HOT_NOVEL_HTML
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        with patch("app.services.hot_topic_fetcher.requests.get", return_value=mock_resp):
            result = fetcher.fetch_hot_novels(gender="男性向", top_n=20)

        assert len(result["topics"]) == 2, "男性向应返回 2 条（玄幻+都市）"
        for t in result["topics"]:
            assert t["gender"] == "男性向"

    def test_filter_female_returns_0(self, fetcher):
        """筛选女性向：mock 数据无女性向，返回 0 条"""
        mock_resp = MagicMock()
        mock_resp.text = BAIDU_HOT_NOVEL_HTML
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        with patch("app.services.hot_topic_fetcher.requests.get", return_value=mock_resp):
            result = fetcher.fetch_hot_novels(gender="女性向", top_n=20)

        assert len(result["topics"]) == 0, "女性向应返回 0 条"

    def test_filter_none_gender_returns_all(self, fetcher):
        """不传 gender：返回全部 3 条"""
        mock_resp = MagicMock()
        mock_resp.text = BAIDU_HOT_NOVEL_HTML
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        with patch("app.services.hot_topic_fetcher.requests.get", return_value=mock_resp):
            result = fetcher.fetch_hot_novels(top_n=20)

        assert len(result["topics"]) == 3, "不筛选应返回全部 3 条"

    def test_genre_to_gender_mapping(self):
        """百度 genre → gender 映射验证"""
        from app.services.hot_topic_fetcher import HotTopicFetcher
        assert HotTopicFetcher._map_genre_to_gender("玄幻") == "男性向"
        assert HotTopicFetcher._map_genre_to_gender("都市") == "男性向"
        assert HotTopicFetcher._map_genre_to_gender("悬疑") == "无性向"
        assert HotTopicFetcher._map_genre_to_gender("言情") == "女性向"
        assert HotTopicFetcher._map_genre_to_gender("古代言情") == "女性向"
        assert HotTopicFetcher._map_genre_to_gender("现代言情") == "女性向"
        assert HotTopicFetcher._map_genre_to_gender("未知类型") == "无性向"
