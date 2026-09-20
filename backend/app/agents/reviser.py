from app.agents.base import BaseAgent
from app.config import platforms as pf


REVISER_SYSTEM_TEMPLATE = """你是一位小说修订编辑。你的任务是根据审稿意见修改章节，解决发现的问题。

修订要求：
1. 针对审稿意见逐条修改
2. 保持原文整体风格和节奏
3. 不要引入新的问题
4. 确保修改后的文本更加自然流畅
5. 【硬指标】修改后的正文必须保持在 {lo}-{hi} 字之间。
   注意：修订不是扩写 —— 只改该改的地方，不要新增情节、对话或描写。
   原文若已超出 {hi} 字，必须压缩回区间内。"""


def build_reviser_system_prompt(platform: str | None = None) -> str:
    """按平台渲染修订器 prompt。

    2026-09-15 修复：此前修订器 prompt 里没有任何字数约束，
    LLM 一修订就把正文撑大（实测 1860 字 → 3107 字），
    导致交付章节违反平台字数规范。字数区间统一取自 platforms.py。
    """
    lo, hi = pf.chapter_words_of(platform)
    return REVISER_SYSTEM_TEMPLATE.format(lo=lo, hi=hi)


class ReviserAgent(BaseAgent):
    def __init__(self):
        super().__init__(role="reviser", temperature=0.5)

    # 兼容旧引用（默认平台渲染结果）
    SYSTEM_PROMPT = build_reviser_system_prompt(None)

    def revise(self, chapter_content: str, review_feedback: str, platform: str | None = None) -> str:
        prompt = f"""请根据审稿意见修改以下章节：

章节正文：{chapter_content}

审稿意见：{review_feedback}"""
        return self.execute(
            prompt=prompt,
            system_prompt=build_reviser_system_prompt(platform),
            max_tokens=8192,
        )

    def trim_to_length(self, chapter_content: str, target_max: int, platform: str | None = None) -> str:
        """把超长正文压缩进字数上限（兜底手段）。

        仅靠 system prompt 约束 LLM 并不可靠，所以对超出上限的章节再做一次显式压缩。
        """
        prompt = f"""下面这章正文超出了平台字数上限（{target_max} 字），请压缩。

压缩要求：
1. 压缩到 {target_max} 字以内，情节链与章末钩子必须完整保留
2. 只删冗余描写、重复表达、可省的过渡句；不要删情节、对话要点和关键细节
3. 直接输出压缩后的正文，不要任何说明文字、不要加标题

正文：
{chapter_content}"""
        return self.execute(
            prompt=prompt,
            system_prompt=build_reviser_system_prompt(platform),
            max_tokens=8192,
        )

    def expand_to_length(
        self,
        chapter_content: str,
        target_min: int,
        platform: str | None = None,
        last_attempt_len: int | None = None,
    ) -> str:
        """把偏短的正文补写进字数区间（兜底手段）。

        2026-09-15 实测：收紧上限后正文普遍偏短（番茄首批 3 章里 2 章只有 1651/1764 字），
        而番茄对不足 1800 字的章节判"水文"降权 —— 所以下限必须像上限一样显式兜住。

        提示词里必须把差额算给模型看：只说"补到 1800-2200"时，模型从 1651 补到 1764
        就认为"差不多够"而收手；改成"还差 349 字，必须再多写这么多"才补得动。
        last_attempt_len 用于把上一轮的实际字数回喂给模型，避免它连续两轮原地打转。

        注意用专用的 system_prompt：通用修订器的 system prompt 里写着"修订不是扩写"，
        直接复用它会让模型拒绝扩写、原地返回原文。
        """
        lo, hi = pf.chapter_words_of(platform)
        mid = (lo + hi) // 2
        # 冲着中值去：目标是 mid，但硬底线是 lo，差额按 lo 算给模型看
        target = max(mid, target_min + 1)
        deficit = max(lo - target_min, 50)
        system_prompt = f"""你是一位小说编辑，负责把偏短的章节补写到平台要求的篇幅。

补写要求：
1. 【硬指标】补写后的正文不得少于 {lo} 字，落在 {lo}-{hi} 字之间，目标 {target} 字
2. 只做"同一场景内的加厚"：补感官细节、动作分解、对话往来、符合人设的心理活动
3. **严禁新增情节**：不许加新人物、新场景、新事件、新悬念，不许改变结局和章末钩子
4. 保持原文的人称、时态、语气、句长习惯，补写部分要和原文浑然一体
5. 直接输出补写后的完整正文，不要任何说明文字、不要加标题、不要分段标注
6. 交稿前自己数一遍字数（去掉空格换行后计数，标点计入），不足 {lo} 字就继续加厚"""

        retry_note = ""
        if last_attempt_len is not None:
            retry_note = (
                f"\n⚠️ 注意：上一轮补写后只有 {last_attempt_len} 字，**仍不达标**。"
                f"这次必须比上一轮再多写至少 {lo - last_attempt_len + 100} 字，不要停手。"
            )

        prompt = f"""下面这章正文只有约 {target_min} 字，不满足平台最低 {lo} 字的要求，请补写。

需要补足的字数：至少 {deficit} 字。
补写后的目标篇幅：{lo}-{hi} 字，建议 {target} 字左右。{retry_note}

正文：
{chapter_content}"""
        return self.execute(prompt=prompt, system_prompt=system_prompt, max_tokens=8192)
