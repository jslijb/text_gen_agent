from app.agents.base import BaseAgent


class ReviewerAgent(BaseAgent):
    def __init__(self):
        super().__init__(role="reviewer", temperature=0.3)

    SYSTEM_PROMPT = """你是一位严格的小说审稿编辑。你的任务是审核章节质量，检查逻辑一致性。

请输出以下内容（JSON格式）：
{
    "score": 85,
    "issues": [
        {"type": "logic|character|pacing|style", "description": "问题描述", "suggestion": "修改建议"}
    ],
    "consistency_check": {
        "character_consistent": true,
        "foreshadowing_progressed": true,
        "plot_logical": true
    }
}"""

    def review(self, chapter_content: str, chapter_plan: str, character_states: str = "") -> str:
        prompt = f"""请审核以下章节：

章节正文：{chapter_content}
章节规划：{chapter_plan}
{f"角色状态：{character_states}" if character_states else ""}"""
        return self.execute(prompt=prompt, system_prompt=self.SYSTEM_PROMPT, max_tokens=4096)