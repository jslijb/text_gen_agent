from app.agents.base import BaseAgent
from app.config import platforms as pf


WRITER_SYSTEM_TEMPLATE = """你是一位才华横溢的小说作家。你的任务是根据大纲和上下文写出精彩的章节正文。

写作要求：
1. 使用生动、具体的语言，避免抽象和模板化表达
2. 多用对话和动作推进剧情，减少大段心理描写
3. 【硬指标】每章正文 {lo}-{hi} 字，**目标值取区间中值 {mid} 字**。
   字数口径 = 去掉空格与换行后的字符数（中文标点计入）。
   按 1800 字的下限交稿会踩平台"水文"线，按 {hi} 字写又容易超出，
   所以冲着 {mid} 字去、上下浮动 10% 最稳。
4. 开头要有吸引力，结尾要留悬念
5. 保持角色性格一致性
6. 注意伏笔的埋设和推进"""


def build_writer_system_prompt(platform: str | None = None) -> str:
    """按平台渲染 writer 的 system prompt。

    字数区间与正文规范全部取自 app/config/platforms.py，
    不再在 agent 里硬编码（百度与番茄的单章字数要求并不相同）。
    """
    lo, hi = pf.chapter_words_of(platform)
    prompt = WRITER_SYSTEM_TEMPLATE.format(lo=lo, hi=hi, mid=(lo + hi) // 2)
    rules = pf.writer_rules_of(platform)
    return f"{prompt}\n{rules}" if rules else prompt


class WriterAgent(BaseAgent):
    def __init__(self):
        super().__init__(role="writer", temperature=0.9)

    # 兼容旧引用（默认平台渲染结果）；实际生成请走 write_chapter(platform=...)
    SYSTEM_PROMPT = build_writer_system_prompt(None)

    def write_chapter(
        self,
        chapter_plan: str,
        previous_summary: str = "",
        character_states: str = "",
        foreshadowing_list: str = "",
        previous_tail: str = "",
        platform: str | None = None,
    ) -> str:
        parts = [f"请写出以下章节的正文：\n\n章节规划：{chapter_plan}"]
        if previous_summary:
            parts.append(f"前文脉络（已发生的情节，切勿重复叙述）：\n{previous_summary}")
        if previous_tail:
            # 上一章正文结尾是衔接续写最关键的信息：
            # 它决定了本章从哪个场景、什么动作、谁在场开始，光给标题会写脱节。
            parts.append(
                f"上一章结尾原文（本章必须严丝合缝接上，承接场景、人物在场状态和未完成的动作，"
                f"不要重述这段内容）：\n……{previous_tail}"
            )
        if character_states:
            parts.append(f"角色当前状态：{character_states}")
        if foreshadowing_list:
            parts.append(f"待推进的伏笔：{foreshadowing_list}")
        return self.execute(
            prompt="\n\n".join(parts),
            system_prompt=build_writer_system_prompt(platform),
            max_tokens=8192,
        )
