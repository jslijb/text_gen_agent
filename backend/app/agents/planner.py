from app.agents.base import BaseAgent
from app.config import platforms as pf


class PlannerAgent(BaseAgent):
    def __init__(self):
        super().__init__(role="planner", temperature=0.7)

    SYSTEM_PROMPT = """你是一位经验丰富的小说策划编辑。你的任务是根据用户提供的故事梗概和爆款特征，生成完整的小说大纲。

请输出以下内容（JSON格式）：
{
    "title": "小说标题",
    "chapters": [
        {"number": 1, "title": "章节标题", "summary": "章节概要", "key_events": ["关键事件1", "关键事件2"]}
    ],
    "characters": [
        {"name": "角色名", "description": "角色描述", "arc": "角色弧线"}
    ],
    "foreshadowing": [
        {"description": "伏笔描述", "planted_chapter": 1, "resolved_chapter": 5}
    ],
    "world_setting": "世界观设定"
}"""

    def plan(self, synopsis: str, genre: str, target_chapters: int, trending_features: str = "", platform: str | None = None) -> str:
        """生成大纲。

        platform 决定额外注入的结构规范（如番茄的"黄金三章""情绪闭环不超 3 章"），
        规则文本统一维护在 app/config/platforms.py，此处不硬编码。
        """
        platform_rules = pf.planner_rules_of(platform, target_chapters)
        prompt = f"""请为以下故事梗概生成小说大纲：

故事梗概：{synopsis}
题材：{genre}
目标章节数：{target_chapters}
{"爆款特征参考：" + trending_features if trending_features else ""}
{platform_rules}

请生成包含{target_chapters}章的完整大纲。"""
        return self.execute(prompt=prompt, system_prompt=self.SYSTEM_PROMPT, max_tokens=8192)