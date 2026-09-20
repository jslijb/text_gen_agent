"""多平台配置注册表

把"平台差异"集中到一处，避免散落在 API / 模型 / 前端里各写一份硬编码。

- baidu  : 百度作家平台（原有链路，配置原样保留，保证兼容）
- fanqie : 番茄小说（2026-09-14 新增）

新增平台只需在此登记一条，各层按本表数据渲染。

字段说明
--------
label          平台展示名
channels       一级频道（沿用项目既有的 gender 字段存储，不改列名）
genres         二级品类，按频道分组
title_prompt   书名/标题生成用的 prompt 模板（含 {name}/{channel}/{genre}/{synopsis} 占位）
title_len      标题有效字数区间（用于生成后的过滤）
humanizer_profile  交给 humanizer 的节奏档位（见 services/humanizer.py）
publish_host   发布通道域名；None 表示自动发布尚未实现
"""

from __future__ import annotations

DEFAULT_PLATFORM = "baidu"


# ============================================================
# 百度作家平台（原有链路，保持原样）
# ============================================================
BAIDU_TITLE_PROMPT = """你是一位资深网文运营编辑，精通百度作家平台的标题分发规则。请根据以下小说信息，生成5个适合在百度App小说书城、信息流、贴吧等场景分发的标题。

## 小说信息
- 书名：{name}
- 性向：{channel}
- 题材：{genre}
- 梗概：{synopsis}

## 标题规则（必须严格遵守，违反任何一条即不合格）
1. 每个标题以"故事："开头（"故事："3个字计入总字数）
2. 【最重要】每个标题总字数必须17-30字，含"故事："前缀，标点符号不计入字数
3. 语句完整，语言通俗易懂，有故事性
4. 能概括正文内容，吸引人点击阅读
5. 巧用数字，让标题更清晰有重点
6. 恰当设置悬念点，凸显戏剧性，但不要标题党
7. 展现情节冲突性，但不要恶意夸张
8. 引起读者情感共鸣

## 字数示例
✅ "故事：离婚前他匿名写下心声，树洞那头的回复让他泪崩"（18字，合格）
✅ "故事：情感咨询师接离婚委托，发现夫妻匿名互写挽留"（18字，合格）
❌ "故事：接1对离婚夫妻委托，咨询师发现双方在树洞互写挽留信"（22字含数字，但纯汉字超30，不合格）

## 禁止事项
- 禁止：震惊体（震惊/惊呆了/惊了）
- 禁止：竟然体（竟/竟然）
- 禁止：低俗（性暗示、吃药）
- 禁止：故弄玄虚（话说一半加省略号）
- 禁止：语句不通顺、错别字、主语缺失
- 禁止：题文不符
- 禁止：虚构作品取名像社会新闻
- 禁止：敏感词（毒品、涉政、涉黄、血腥暴力等）
- 禁止：超过30字或不足17字

## 输出格式
严格输出JSON数组，不要任何其他文字：
["故事：...", "故事：...", "故事：...", "故事：...", "故事：..."]

生成前先数每个标题的字数，确保17-30字之间！"""


# ============================================================
# 番茄小说
# ============================================================
# 品类依据：番茄官方短故事「IP金品共创计划」公告聚焦的 14 种品类
#   （男频脑洞、女频脑洞、悬疑惊悚、玄幻仙侠、青春虐恋、古言虐恋、历史古代、
#     都市日常、宫斗宅斗、现言甜宠、古言甜宠、民国旧影、年代、女性成长）
# 频道归属按品类名的频道语义整理；悬疑惊悚为跨频道品类，两个频道都开放。
# 若后台实际分类调整，只改本表即可，无需动业务代码。
FANQIE_TITLE_PROMPT = """你是一位番茄小说的资深签约作者，擅长起"一眼就点开"的书名。请根据以下小说信息，生成5个番茄风格的书名。

## 小说信息
- 现用书名：{name}
- 频道：{channel}
- 品类：{genre}
- 梗概：{synopsis}

## 番茄书名规则（必须严格遵守）
1. 【不得带"故事："之类的前缀】，书名就是书名
2. 有效字数 5-20 字，标点不计
3. 大白话，说人话。读者扫一眼就知道"谁、干了什么、出了什么事"
4. 最有效的结构是"设定 + 冲突"两段式，中间逗号断开：
   - 前半句交代身份或处境，后半句给反转或反差
   - 参考：《闪婚禁欲上司，人前不熟人后猛亲》《我替人扫墓，守着一块无字碑》
5. 允许第一人称"我"开头，番茄读者对第一人称代入感接受度高
6. 口语词可用：闪婚、老板、前夫、婆婆、闺蜜、重生、穿书、系统、退婚
7. 给出具体信息，不写抽象概念。不要"救赎""宿命""时光""岁月"这类虚词

## 禁止事项
- 禁用虚词/文艺腔：救赎、宿命、时光、岁月、流年、旧梦、呢喃、缱绻
- 禁止标题党：震惊、竟然、惊呆、万万没想到
- 禁止故弄玄虚：话说一半加省略号
- 禁止低俗、涉黄、涉政、血腥暴力、涉毒
- 禁止题文不符，禁止超 20 字
- 禁止疑问句式凑字数

## 输出格式
严格输出JSON数组，不要任何其他文字：
["书名1", "书名2", "书名3", "书名4", "书名5"]

生成后逐个数字数，确保 5-20 字。"""


# ============================================================
# 番茄小说：正文写作规范（2026-09-15 新增，注入 writer 的 system prompt）
# 依据番茄平台发文规范：单章最低 1000 字、上限 5w 字；黄金区间 2000-2200；
# 低于 1800 易被判"水文"降权，超过 4000 中途流失率升高。
# 短故事分档口径：超短篇 8k-2.49w 字，中短篇 2.5w-8w 字（番茄短故事激励计划原文）。
# ============================================================
FANQIE_WRITER_RULES = """
## 番茄平台正文规范（必须严格遵守）
1. 【硬指标】本章正文字数控制在 1800-2200 字（不含章节标题），目标 2000 字。
   低于 1800 会被平台判为"水文"降权，超过 2200 会拉低完读率。
   字数口径：去掉空格和换行后的字符数，中文标点计算在内。
2. 单章必须闭环一个小情节，章末留一个明确钩子（悬念 / 反转 / 危机）。
3. 第一段就进动作或对话，禁止景物铺陈、禁止背景百科式介绍。
4. 以对话和动作推进剧情，减少心理独白与旁白；单段不超过 4 行。
5. 说大白话。短句为主，长短句交替，不要书面语和文艺腔。
6. 人物、地点、时间必须与前文严格一致，禁止凭空新增设定。"""


FANQIE_PLANNER_RULES = """
## 番茄短篇结构要求（必须遵守）
1. 全篇 {chapters} 章构成一个完整故事，必须有明确结局，不要开放式收尾。
2. 【黄金三章】前 3 章必须完成：主角困境 → 关键设定/能力登场 → 第一个爽点或反转 → 悬念留尾。
3. 情绪闭环：憋屈剧情不得超过 2 章，第 3 章务必给出反击或转机。
4. 每章承载一个具体事件，章末留钩子；每 3-4 章安排一次大反转。
5. 主角必须有明确目标与对手，冲突要具体（具体的人、具体的利害关系）。
6. 每章 summary 写 60-120 字，必须写清"谁做了什么、推进到什么状态、留下什么钩子"。"""


PLATFORMS: dict[str, dict] = {
    "baidu": {
        "label": "百度作家平台",
        "channels": ["男性向", "女性向", "无性向"],
        "genres": {
            "男性向": ["都市情感", "历史故事"],
            "女性向": ["现代言情", "古代言情", "青春校园", "婚姻家庭"],
            "无性向": ["恐怖推理", "乡村故事", "真实故事", "见闻杂谈", "复仇爽文", "特殊职业"],
        },
        "title_prompt": BAIDU_TITLE_PROMPT,
        "title_prefix": "故事：",
        "title_len": (17, 30),
        # 单章正文字数区间：与原 writer 硬编码的 2000-3000 保持一致，行为不变
        "chapter_words": (2000, 3000),
        # 官方字数分档（仅用于提示与校验，百度作家平台无短篇分档规则）
        "total_words": (10000, 300000),
        # 百度侧不注入额外结构规则，保持原有生成表现
        "writer_rules": "",
        "planner_rules": "",
        "humanizer_profile": "baidu",
        "publish_host": "zuojia.baidu.com",
    },
    "fanqie": {
        "label": "番茄小说",
        "channels": ["女频", "男频"],
        "genres": {
            "女频": [
                "女频脑洞", "现言甜宠", "青春虐恋", "古言甜宠", "古言虐恋",
                "宫斗宅斗", "民国旧影", "年代", "女性成长", "都市日常", "悬疑惊悚",
            ],
            "男频": [
                "男频脑洞", "玄幻仙侠", "历史古代", "都市日常", "悬疑惊悚",
            ],
        },
        "title_prompt": FANQIE_TITLE_PROMPT,
        "title_prefix": "",
        "title_len": (5, 20),
        # 单章正文字数区间：番茄黄金区间 2000-2200，取 1800-2200（下限对齐"防水文"红线）
        "chapter_words": (1800, 2200),
        # 短故事官方分档：超短篇 8k-2.49w 字 / 中短篇 2.5w-8w 字
        "total_words": (8000, 24900),
        "writer_rules": FANQIE_WRITER_RULES,
        "planner_rules": FANQIE_PLANNER_RULES,
        "humanizer_profile": "fanqie",
        "publish_host": None,  # 番茄自动发布尚未实现（需账号 + 风控评估）
    },
}


def get_platform(key: str | None) -> dict:
    """取平台配置；未知 key 回落到默认平台"""
    return PLATFORMS.get(key or DEFAULT_PLATFORM, PLATFORMS[DEFAULT_PLATFORM])


def platform_key(key: str | None) -> str:
    """归一化平台 key"""
    return key if key in PLATFORMS else DEFAULT_PLATFORM


def list_platforms() -> list[dict]:
    """列出全部平台（供前端渲染选择器）

    只吐出前端渲染需要的字段；title_prompt / writer_rules / planner_rules
    都是后端生成用的大段提示词，不外发。
    """
    allow = (
        "label", "channels", "genres", "title_len", "title_prefix",
        "chapter_words", "total_words",
    )
    return [
        {"key": k, **{f: v[f] for f in allow if f in v}}
        for k, v in PLATFORMS.items()
    ]


def channels_of(key: str | None) -> list[str]:
    return get_platform(key)["channels"]


def genres_of(key: str | None, channel: str) -> list[str]:
    return get_platform(key)["genres"].get(channel, [])


def is_valid_pair(key: str | None, channel: str, genre: str) -> bool:
    """校验 平台 + 频道 + 品类 组合是否合法"""
    return genre in genres_of(key, channel)


def publish_host_of(key: str | None) -> str | None:
    """平台自动发布的通道域名；None 表示该平台自动发布尚未实现。"""
    return get_platform(key).get("publish_host")


def supports_auto_publish(key: str | None) -> bool:
    """该平台是否支持自动发布。

    2026-09-15：日更调度原先不看平台，番茄项目一旦出现 approved+unpublished 的章节，
    就会被丢给百度发布器（Publisher 走 zuojia.baidu.com 的 Playwright 流程），
    必然失败并刷出一串重试和 PublishQueue 失败记录。此处给出统一判定，供调度侧前置拦截。
    """
    return bool(publish_host_of(key))


def is_valid_channel(key: str | None, channel: str) -> bool:
    return channel in channels_of(key)


def label_of(key: str | None) -> str:
    return get_platform(key)["label"]


def title_len_of(key: str | None) -> tuple[int, int]:
    return get_platform(key)["title_len"]


def chapter_words_of(key: str | None) -> tuple[int, int]:
    """单章正文字数区间 (下限, 上限)"""
    return get_platform(key)["chapter_words"]


def writer_rules_of(key: str | None) -> str:
    """注入 writer system prompt 的平台正文规范；无配置返回空串（保持原行为）"""
    return get_platform(key).get("writer_rules", "") or ""


def planner_rules_of(key: str | None, chapters: int | None = None) -> str:
    """注入 planner 的平台结构要求；已渲染 {chapters} 占位符"""
    tpl = get_platform(key).get("planner_rules", "") or ""
    if not tpl:
        return ""
    try:
        return tpl.format(chapters=chapters if chapters is not None else "")
    except (KeyError, IndexError, ValueError):
        # 模板里出现非预期占位符时原样返回，不让它把生成流程打断
        return tpl
