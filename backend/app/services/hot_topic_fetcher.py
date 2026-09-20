"""
热点数据获取服务。
对应 spec 5.4：从百度热搜小说榜单抓取数据，缓存并提供给上层生成梗概/标题。

数据源：https://top.baidu.com/board?tab=novel
- requests + UA 伪装（轻量级，不用 Playwright）
- BeautifulSoup 解析榜单
- 进程内单例缓存，TTL 30 分钟
- 失败降级到 KnowledgeBaseManager
"""
import logging
import re
import time
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

# 模块级导入（便于测试 mock，spec 5.4.1 规则 7 降级 + 创意生成复用 LLM）
from app.services.knowledge_base import KnowledgeBaseManager
from app.services.model_manager import ModelManager

logger = logging.getLogger(__name__)


# UA 轮换池（合规反爬：伪装真实浏览器）
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

BAIDU_HOT_NOVEL_URL = "https://top.baidu.com/board?tab=novel"
CACHE_TTL_SECONDS = 1800  # 30 分钟

# spec v1.4.1：百度热搜 genre → 百度作家平台性向映射
# 男性向偏热血/历史/都市；女性向偏言情/青春/情感；无性向偏悬疑/现实/杂谈
BAIDU_GENRE_TO_GENDER = {
    # 男性向
    "都市": "男性向", "历史": "男性向", "军事": "男性向",
    "玄幻": "男性向", "奇幻": "男性向", "武侠": "男性向",
    "仙侠": "男性向", "科幻": "男性向", "游戏": "男性向", "体育": "男性向",
    # 女性向
    "言情": "女性向", "古代言情": "女性向", "现代言情": "女性向",
    "青春校园": "女性向", "婚姻": "女性向", "女生": "女性向",
    # 无性向
    "悬疑": "无性向", "灵异": "无性向", "推理": "无性向",
    "乡村": "无性向", "纪实": "无性向", "杂谈": "无性向",
    "重生": "无性向", "职场": "无性向",
}


class HotTopicUnavailable(Exception):
    """百度热搜不可达且本地知识库也为空"""
    pass


class HotTopicFetcher:
    """百度热搜小说榜单抓取器（单例缓存）"""

    _instance: Optional["HotTopicFetcher"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache = None
            cls._instance._cache_ts = 0
        return cls._instance

    def clear_cache(self):
        """清空缓存（测试用）"""
        self._cache = None
        self._cache_ts = 0

    def fetch_hot_novels(self, force_refresh: bool = False, top_n: int = 20, gender: Optional[str] = None) -> dict:
        """抓取百度热搜小说榜单。

        Args:
            force_refresh: True 绕过缓存
            top_n: 返回条数上限
            gender: 按性向筛选（男性向/女性向/无性向），None 返回全部

        Returns:
            {
                source: "baidu_hot_search" | "knowledge_base_fallback",
                degraded: bool,
                fetched_at: ISO8601,
                cache_ttl_seconds: int,
                topics: [{rank, title, author, genre, gender, hot_index, description}, ...],
                genre_distribution: [{genre, count, percentage}, ...],
            }
        """
        # 1. 缓存命中检查
        if not force_refresh and self._cache is not None:
            age = time.time() - self._cache_ts
            if age < CACHE_TTL_SECONDS:
                logger.info(f"热点缓存命中（age={age:.0f}s, ttl={CACHE_TTL_SECONDS}s）")
                cached = self._cache
                topics = self._enrich_with_gender(cached["topics"])
                if gender:
                    topics = [t for t in topics if t["gender"] == gender]
                    logger.info(f"按性向[{gender}]筛选：{len(topics)} 条")
                return {**cached, "topics": topics[:top_n]}

        # 2. 抓取百度热搜
        try:
            topics = self._fetch_from_baidu()
            if topics:
                result = {
                    "source": "baidu_hot_search",
                    "degraded": False,
                    "fetched_at": datetime.now().isoformat(),
                    "cache_ttl_seconds": CACHE_TTL_SECONDS,
                    "topics": topics,
                    "genre_distribution": self._calc_genre_distribution(topics),
                }
                self._cache = result
                self._cache_ts = time.time()
                logger.info(f"百度热搜抓取成功：{len(topics)} 条")
                topics_enriched = self._enrich_with_gender(topics)
                if gender:
                    topics_enriched = [t for t in topics_enriched if t["gender"] == gender]
                    logger.info(f"按性向[{gender}]筛选：{len(topics_enriched)} 条")
                return {**result, "topics": topics_enriched[:top_n]}
            logger.warning("百度热搜 HTML 解析为空，尝试降级")
        except Exception as e:
            logger.warning(f"百度热搜抓取失败，尝试降级: {e}", exc_info=True)

        # 3. 降级到本地知识库
        return self._degrade_to_knowledge_base(top_n, gender=gender)

    @staticmethod
    def _map_genre_to_gender(genre: str) -> str:
        """将百度热搜 genre 映射到百度作家平台性向（spec v1.4.1）"""
        return BAIDU_GENRE_TO_GENDER.get(genre.strip(), "无性向")

    @staticmethod
    def _enrich_with_gender(topics: list) -> list:
        """为每条 topic 添加 gender 字段（不修改原始字典，spec v1.4.1）"""
        return [
            {**t, "gender": BAIDU_GENRE_TO_GENDER.get(t.get("genre", "").strip(), "无性向")}
            for t in topics
        ]

    def _fetch_from_baidu(self) -> list:
        """从百度热搜小说榜抓取（spec 5.4.1 规则 1/2/3）"""
        import random
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        resp = requests.get(BAIDU_HOT_NOVEL_URL, headers=headers, timeout=10)
        resp.raise_for_status()
        return self._parse_baidu_html(resp.text)

    def _parse_baidu_html(self, html: str) -> list:
        """解析百度热搜榜单 HTML。

        真实页面采用 Vue SSR，class 名带哈希后缀（如 category-wrap_iQLoo），
        最稳定的方案是从嵌入的 <!--s-data:{...}--> 注释中提取 JSON 数据；
        若 s-data 不存在或解析失败，回退到 DOM 模糊匹配解析。

        JSON 字段映射（spec 5.4.1 规则 2 五项必填字段）：
        - word      → title       书名
        - show[0]   → author      作者（"作者：xxx"）
        - show[1]   → genre       类型（"类型：xxx"）
        - hotScore  → hot_index   热搜指数（字符串，需转 int）
        - desc      → description 简介
        - index+1   → rank        排名（0-based → 1-based）
        """
        # 优先方案：从 s-data 注释提取 JSON（最稳定，不受 class 哈希变化影响）
        topics = self._parse_from_s_data(html)
        if topics:
            logger.info(f"s-data JSON 解析成功：{len(topics)} 条")
            return topics

        # 回退方案：DOM 模糊匹配（class 名带哈希后缀，用 [class*='prefix'] 匹配）
        topics = self._parse_from_dom(html)
        if topics:
            logger.info(f"DOM 模糊解析成功：{len(topics)} 条")
        return topics

    def _parse_from_s_data(self, html: str) -> list:
        """从 <!--s-data:{...}--> 注释中提取 JSON 数据。

        百度热搜页面将榜单数据以 JSON 形式嵌入在 HTML 注释中，
        供 Vue SSR hydration 使用，结构稳定。
        """
        import json
        # 注释格式：<!--s-data:{...}-->，JSON 中不含 --> 序列
        match = re.search(r"<!--s-data:(\{.*?\})-->", html, re.DOTALL)
        if not match:
            logger.debug("未找到 s-data 注释")
            return []
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError as e:
            logger.warning(f"s-data JSON 解析失败: {e}")
            return []

        cards = data.get("data", {}).get("cards", [])
        topics = []
        for card in cards:
            content = card.get("content", [])
            if not isinstance(content, list):
                continue
            for item in content:
                try:
                    topic = self._build_topic_from_s_data_item(item)
                    if topic:
                        topics.append(topic)
                except Exception as e:
                    logger.debug(f"解析 s-data 条目失败: {e}")
                    continue
        # 按 rank 升序
        topics.sort(key=lambda t: t["rank"])
        return topics

    @staticmethod
    def _build_topic_from_s_data_item(item: dict) -> Optional[dict]:
        """从 s-data 单条 item 构造 topic 字典。

        五项必填字段任一缺失返回 None（spec 5.4.1 规则 2）。
        """
        word = (item.get("word") or "").strip()
        desc = (item.get("desc") or "").strip()
        hot_score = item.get("hotScore") or "0"
        show = item.get("show") or []
        index = item.get("index", 0)

        if not word:
            return None

        # 解析作者和类型
        author = ""
        genre = ""
        for s in show:
            if not isinstance(s, str):
                continue
            if s.startswith("作者：") or s.startswith("作者:"):
                author = s.split("：", 1)[-1] if "：" in s else s.split(":", 1)[-1]
                author = author.strip()
            elif s.startswith("类型：") or s.startswith("类型:"):
                genre = s.split("：", 1)[-1] if "：" in s else s.split(":", 1)[-1]
                genre = genre.strip()

        # 热搜指数
        try:
            hot_index = int(str(hot_score).replace(",", ""))
        except (ValueError, TypeError):
            hot_index = 0

        # 五项必填字段校验
        if not (author and genre and hot_index > 0 and desc):
            return None

        return {
            "rank": int(index) + 1,
            "title": word,
            "author": author,
            "genre": genre,
            "hot_index": hot_index,
            "description": desc,
        }

    def _parse_from_dom(self, html: str) -> list:
        """DOM 模糊解析兜底：用 [class*='prefix'] 匹配带哈希后缀的 class。

        真实页面结构（class 名带哈希后缀，会随构建变化）：
        <div class="category-wrap_iQLoo">
          <a class="img-wrapper_29V76">
            <div class="index_1Ew5p c-index-bg1"> 1 </div>
          </a>
          <a class="trend_2RttY">
            <div class="hot-index_1Bl1a"> 185376 </div>
          </a>
          <div class="content_1YWBm">
            <a class="title_dIF3B"><div class="c-single-text-ellipsis">儒道至圣</div></a>
            <div class="intro_1l0wp">作者：永恒之火</div>
            <div class="intro_1l0wp">类型：玄幻</div>
            <div class="c-single-text-ellipsis desc_3CTjT">简介...</div>
          </div>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        topics = []
        items = soup.select("[class*='category-wrap']")
        for item in items:
            try:
                topic = self._build_topic_from_dom_item(item, len(topics) + 1)
                if topic:
                    topics.append(topic)
            except Exception as e:
                logger.debug(f"解析 DOM 条目失败: {e}")
                continue
        return topics

    def _build_topic_from_dom_item(self, item, fallback_rank: int) -> Optional[dict]:
        """从 DOM 单条 item 构造 topic 字典。"""
        # 书名：[class*='title_'] 下的 .c-single-text-ellipsis
        title_el = item.select_one("[class*='title_'] .c-single-text-ellipsis") or item.select_one("[class*='title_']")
        if not title_el:
            return None
        title = title_el.get_text(strip=True)
        if not title:
            return None

        # 作者/类型：[class*='intro_'] 多个
        author = ""
        genre = ""
        for intro in item.select("[class*='intro_']"):
            text = intro.get_text(strip=True)
            if text.startswith("作者：") or text.startswith("作者:"):
                author = self._clean_field(text)
            elif text.startswith("类型：") or text.startswith("类型:"):
                genre = self._clean_field(text)

        # 热搜指数：[class*='hot-index_']
        hot_el = item.select_one("[class*='hot-index_']")
        hot_text = hot_el.get_text(strip=True) if hot_el else ""
        hot_match = re.search(r"\d+", hot_text)
        hot_index = int(hot_match.group()) if hot_match else 0

        # 简介：[class*='desc_']
        desc_el = item.select_one("[class*='desc_']")
        description = ""
        if desc_el:
            # 移除 "查看更多>" 等链接文本
            for a in desc_el.select("a"):
                a.decompose()
            description = desc_el.get_text(strip=True)

        # 排名：[class*='index_']（注意 hot-index 也含 index，需排除）
        rank = fallback_rank
        for idx_el in item.select("[class*='index_']"):
            cls = idx_el.get("class", [])
            # 排除 hot-index_1Bl1a / text-index_39kSZ
            if any(c.startswith("hot-index") or c.startswith("text-index") for c in cls):
                continue
            text = idx_el.get_text(strip=True)
            if text.isdigit():
                rank = int(text)
                break

        # 五项必填字段校验
        if not (author and genre and hot_index > 0 and description):
            return None

        return {
            "rank": rank,
            "title": title,
            "author": author,
            "genre": genre,
            "hot_index": hot_index,
            "description": description,
        }

    @staticmethod
    def _clean_field(text: str) -> str:
        """清洗 '作者：xxx' → 'xxx'"""
        if not text:
            return ""
        for sep in ["：", ":"]:
            if sep in text:
                return text.split(sep, 1)[-1].strip()
        return text

    @staticmethod
    def _calc_genre_distribution(topics: list) -> list:
        """按题材聚合统计占比（spec 5.4.1 规则 4）"""
        from collections import Counter
        counter = Counter(t["genre"] for t in topics)
        total = sum(counter.values())
        return [
            {"genre": g, "count": c, "percentage": round(c / total * 100, 2)}
            for g, c in counter.most_common()
        ]

    def _degrade_to_knowledge_base(self, top_n: int, gender: Optional[str] = None) -> dict:
        """降级：回退到本地爆款知识库（spec 5.4.1 规则 7）"""
        try:
            kb = KnowledgeBaseManager()
            entries = kb.search_trending_features("")  # 取全部
            if not entries:
                logger.error("本地知识库也为空，无法降级")
                raise HotTopicUnavailable("百度热搜不可达且本地知识库为空，请先到知识库页面抓取爆款")
            topics = []
            for i, e in enumerate(entries[:top_n], 1):
                topics.append({
                    "rank": i,
                    "title": e.get("topic", "未知") + "·爆款特征",
                    "author": e.get("source", "本地知识库"),
                    "genre": e.get("topic", "其他"),
                    "hot_index": int(e.get("heat_score", 50)),
                    "description": e.get("opening_pattern", "") + "；" + e.get("content", "")[:200],
                })
            # spec v1.4.1：降级数据也添加 gender 字段并筛选
            topics = self._enrich_with_gender(topics)
            if gender:
                topics = [t for t in topics if t["gender"] == gender]
            result = {
                "source": "knowledge_base_fallback",
                "degraded": True,
                "fetched_at": datetime.now().isoformat(),
                "cache_ttl_seconds": CACHE_TTL_SECONDS,
                "topics": topics,
                "genre_distribution": self._calc_genre_distribution(topics),
            }
            logger.warning(f"已降级到本地知识库：{len(topics)} 条")
            return result
        except HotTopicUnavailable:
            raise
        except Exception as e:
            logger.error(f"降级到知识库也失败: {e}", exc_info=True)
            raise HotTopicUnavailable(f"百度热搜和本地知识库均不可用: {e}")


# ========== 创意生成：复用 ModelManager 调用 LLM ==========

SYNOPSIS_PROMPT_TEMPLATE = """你是一位资深小说策划。请根据以下信息生成 {count} 个原创短篇小说故事梗概。

【用户选定题材】{genre}
【当前热门参考】（仅作风格参考，禁止抄袭剧情）：
{reference_text}
【爆款特征参考】
{trending_features}

【输出要求】
1. 生成 {count} 个独立的故事梗概
2. 每个梗概 200-300 字
3. 必须围绕【用户选定题材】展开
4. 不得直接复制热门小说的剧情或角色
5. 必须符合百度作家平台合规要求（无敏感词、无违规内容）
6. 用 ===== 分隔每个梗概

【输出格式】
梗概1
=====
梗概2
=====
梗概3
"""

TITLE_PROMPT_TEMPLATE = """你是一位资深小说标题策划。请根据以下故事梗概生成 {count} 个候选小说标题。

【故事梗概】
{synopsis}

【题材】{genre}

【输出要求】
1. 生成 {count} 个候选标题
2. 每个标题 10-20 字
3. 符合百度作家平台爆款命名规律（吸睛、有悬念、与内容呼应）
4. 不得直接使用热门小说的书名
5. 每行一个标题，不要编号
"""


def generate_synopses(genre: str, reference_topics: list, count: int = 3) -> tuple:
    """调用 LLM 生成候选梗概。

    Returns: (synopses_list, model_used)
    """
    mm = ModelManager()

    reference_text = "\n".join(f"- {t}" for t in reference_topics) or "（无热点参考）"
    # 注入爆款特征（spec 5.4.1 规则 5）
    trending_features = ""
    try:
        kb = KnowledgeBaseManager()
        entries = kb.search_trending_features(genre)
        if entries:
            trending_features = "\n".join(
                f"- 题材={e.get('topic')}, 开头模式={e.get('opening_pattern')}, 情绪={e.get('emotion_type')}, 结局={e.get('ending_type')}"
                for e in entries[:3]
            )
    except Exception as e:
        logger.warning(f"获取爆款特征失败，跳过: {e}")

    prompt = SYNOPSIS_PROMPT_TEMPLATE.format(
        count=count, genre=genre, reference_text=reference_text, trending_features=trending_features or "（无爆款特征参考）"
    )
    logger.info(f"生成梗概: genre={genre}, count={count}, ref_topics={len(reference_topics)}")
    result = mm.call_llm(prompt, role="planner", temperature=0.8, max_tokens=4096)
    synopses = [s.strip() for s in result.split("=====") if s.strip()]
    # 容错：LLM 可能不按分隔符输出，按换行段切分兜底
    if len(synopses) < count:
        synopses = [p.strip() for p in result.split("\n\n") if len(p.strip()) > 50]
    return synopses[:count], _safe_model_name(mm)


def generate_titles(synopsis: str, genre: str, count: int = 5) -> tuple:
    """调用 LLM 生成候选标题。

    Returns: (titles_list, model_used)
    """
    mm = ModelManager()

    prompt = TITLE_PROMPT_TEMPLATE.format(count=count, synopsis=synopsis, genre=genre)
    logger.info(f"生成标题: genre={genre}, count={count}")
    result = mm.call_llm(prompt, role="planner", temperature=0.9, max_tokens=1024)
    titles = [t.strip() for t in result.split("\n") if t.strip() and not t.strip().startswith("【")]
    # 过滤过长或过短的
    titles = [t for t in titles if 5 <= len(t) <= 30]
    return titles[:count], _safe_model_name(mm)


def _safe_model_name(mm) -> str:
    """安全获取模型名（兼容 mock 对象）"""
    try:
        fn = getattr(mm, "get_current_model_name", None)
        if fn is None:
            return "unknown"
        name = fn() if callable(fn) else fn
        return name if isinstance(name, str) else "unknown"
    except Exception:
        return "unknown"
