import pytest
from unittest.mock import patch, MagicMock
from app.agents.planner import PlannerAgent
from app.agents.writer import WriterAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.reviser import ReviserAgent


class TestPlannerAgent:
    @patch.object(PlannerAgent, 'execute')
    def test_plan_returns_string(self, mock_execute):
        mock_execute.return_value = '{"title": "测试小说", "chapters": []}'
        agent = PlannerAgent()
        result = agent.plan("一个测试梗概", "都市情感", 10)
        assert isinstance(result, str)
        assert "测试小说" in result

    @patch.object(PlannerAgent, 'execute')
    def test_plan_with_trending_features(self, mock_execute):
        mock_execute.return_value = '{"title": "测试", "chapters": []}'
        agent = PlannerAgent()
        result = agent.plan("梗概", "悬疑", 5, trending_features="开头设钩子")
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args
        assert "悬疑" in call_args.kwargs.get("prompt", call_args[1].get("prompt", ""))


class TestWriterAgent:
    @patch.object(WriterAgent, 'execute')
    def test_write_chapter(self, mock_execute):
        mock_execute.return_value = "这是章节正文内容..."
        agent = WriterAgent()
        result = agent.write_chapter("第1章规划", "前文摘要", "角色状态")
        assert isinstance(result, str)
        assert len(result) > 0


class TestReviewerAgent:
    @patch.object(ReviewerAgent, 'execute')
    def test_review(self, mock_execute):
        mock_execute.return_value = '{"score": 85, "issues": []}'
        agent = ReviewerAgent()
        result = agent.review("章节内容", "章节规划")
        assert isinstance(result, str)


class TestReviserAgent:
    @patch.object(ReviserAgent, 'execute')
    def test_revise(self, mock_execute):
        mock_execute.return_value = "修订后的内容..."
        agent = ReviserAgent()
        result = agent.revise("原始内容", "审稿意见")
        assert isinstance(result, str)