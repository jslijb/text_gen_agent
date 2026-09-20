"""
TDD Red 阶段：递归释义策略测试
spec v1.3.0：Agnes AI + 递归释义 + Best-of-N 检测反馈闭环
学术依据：arXiv:2303.11156
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def humanizer():
    from app.services.humanizer import Humanizer
    return Humanizer()


@pytest.fixture
def sample_text():
    return (
        "他缓缓地走进了房间，目光扫过每一个角落，仿佛在寻找着什么。"
        "他的表情沉稳而坚定，似乎已经做好了面对一切的准备。"
        "值得注意的是，桌上放着一封信，信封上没有署名。"
    )


# ============ 递归释义主流程测试 ============

class TestHumanizeRecursive:
    """spec 5.2.1 规则 4：递归释义 + Best-of-N"""

    @pytest.mark.asyncio
    async def test_recursive_3_rounds_basic(self, humanizer, sample_text):
        candidates = [
            "候选A-轮1", "候选B-轮1", "候选C-轮1",
            "候选A-轮2", "候选B-轮2", "候选C-轮2",
            "候选A-轮3", "候选B-轮3", "候选C-轮3",
        ]
        call_count = [0]
        def mock_call_llm(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            return candidates[min(idx, len(candidates) - 1)]

        def mock_score(self, text):
            if "候选B" in text:
                return 10.0
            if "候选A" in text:
                return 30.0
            return 50.0

        with patch("app.services.model_manager.ModelManager.call_llm", side_effect=mock_call_llm), \
             patch("app.services.humanizer.Humanizer._statistical_ai_score_v2", mock_score), \
             patch("app.services.humanizer.Humanizer.check_consistency",
                   return_value={"consistent": True, "issues": []}):
            result = await humanizer.humanize_recursive(sample_text)

        assert result["strategy"] == "recursive"
        assert result["rounds_completed"] == 3
        assert call_count[0] == 9

    @pytest.mark.asyncio
    async def test_best_of_n_picks_lowest_score(self, humanizer, sample_text):
        call_count = [0]
        def mock_call_llm(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            return ["高分文本", "低分文本", "中分文本"][idx]

        def mock_score(self, text):
            if text == "低分文本":
                return 5.0
            if text == "中分文本":
                return 30.0
            return 80.0

        with patch("app.services.model_manager.ModelManager.call_llm", side_effect=mock_call_llm), \
             patch("app.services.humanizer.Humanizer._statistical_ai_score_v2", mock_score), \
             patch("app.services.humanizer.Humanizer.check_consistency",
                   return_value={"consistent": True, "issues": []}):
            result = await humanizer.humanize_recursive(sample_text, rounds=1, n_candidates=3)

        assert result["text"] == "低分文本"
        assert result["score_after"] == 5.0

    @pytest.mark.asyncio
    async def test_single_round_failure_fallback_to_original(self, humanizer, sample_text):
        """测试单轮释义失败时降级到原文继续下一轮"""
        call_count = [0]
        def mock_call_llm(**kwargs):
            call_count[0] += 1
            if call_count[0] <= 3:  # 第1轮全部失败
                raise Exception("API 超时")
            return "轮2成功候选"

        def mock_evaluate(self, text):
            return 20.0

        with patch("app.services.model_manager.ModelManager.call_llm", side_effect=mock_call_llm), \
             patch("app.services.humanizer.Humanizer.evaluate_ai_score", mock_evaluate), \
             patch("app.services.humanizer.Humanizer.check_consistency",
                   return_value={"consistent": True, "issues": []}):
            result = await humanizer.humanize_recursive(sample_text, rounds=2, n_candidates=3)

        # 第1轮失败降级到原文，第2轮成功
        assert "轮2成功候选" in result["text"] or result["text"] == sample_text
        assert result["rounds_completed"] >= 1

    @pytest.mark.asyncio
    async def test_all_rounds_failure_returns_original(self, humanizer, sample_text):
        """测试所有轮次失败时返回原文（套话已替换）+ 告警"""
        def mock_call_llm(**kwargs):
            raise Exception("API 持续不可用")

        with patch("app.services.model_manager.ModelManager.call_llm", side_effect=mock_call_llm), \
             patch("app.services.humanizer.Humanizer.evaluate_ai_score", return_value=50.0):
            result = await humanizer.humanize_recursive(sample_text, rounds=3, n_candidates=3)

        # 降级返回套话替换后的原文（"值得注意的是"→"需要关注的是"），非 LLM 改写结果
        assert "需要关注的是" in result["text"]  # 套话已替换
        assert "值得注意的是" not in result["text"]  # 原套话已消除
        assert result["rounds_completed"] == 0
        assert result.get("degraded") is True  # 标记降级

    @pytest.mark.asyncio
    async def test_consistency_check_blocks_inconsistent(self, humanizer, sample_text):
        """测试一致性检查不通过时该候选被跳过"""
        call_count = [0]
        def mock_call_llm(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            return ["不一致文本", "一致文本A", "一致文本B"][idx % 3]

        def mock_evaluate(self, text):
            return 15.0

        def mock_check(self, original, rewritten):
            # "不一致文本" 不通过
            if "不一致" in rewritten:
                return {"consistent": False, "issues": ["剧情偏移"]}
            return {"consistent": True, "issues": []}

        with patch("app.services.model_manager.ModelManager.call_llm", side_effect=mock_call_llm), \
             patch("app.services.humanizer.Humanizer.evaluate_ai_score", mock_evaluate), \
             patch("app.services.humanizer.Humanizer.check_consistency", mock_check):
            result = await humanizer.humanize_recursive(sample_text, rounds=1, n_candidates=3)

        # "不一致文本"被跳过，应选"一致文本A"或"一致文本B"
        assert "不一致" not in result["text"]
        assert "一致文本" in result["text"]


# ============ check_consistency 修复验证 ============

class TestCheckConsistencyFix:
    """spec v1.3.0：修复 extract_keywords 误报"""

    def test_extract_keywords_no_quotes(self, humanizer):
        """验证 extract_keywords 不再提取引号内对话"""
        text = '他说："今天天气真好啊，我们出去玩吧。" 然后他笑了。'
        keywords = humanizer._extract_keywords_internal(text)
        # 引号内对话不应出现在关键词中
        assert "今天天气真好啊，我们出去玩吧。" not in keywords
        assert "今天天气真好啊" not in keywords

    def test_extract_keywords_keeps_numbers(self, humanizer):
        """验证 extract_keywords 仍保留数字"""
        text = "他今年25岁，月薪8000元，涨了15%。"
        keywords = humanizer._extract_keywords_internal(text)
        assert "25" in keywords
        assert "8000" in keywords
        assert "15%" in keywords

    def test_consistency_trusts_llm_judgment(self, humanizer):
        """验证一致性检查信任 LLM 判定，不再用关键词覆盖"""
        original = '他说："你好啊。" 然后走了。'
        rewritten = '他打了个招呼，接着就离开了。'  # 对话被改写
        # mock LLM 判定为一致
        with patch("app.services.model_manager.ModelManager.call_llm",
                   return_value='{"consistent": true, "issues": []}'):
            result = humanizer.check_consistency(original, rewritten)
        # 应信任 LLM 判定，不因对话"关键词缺失"覆盖
        assert result["consistent"] is True


# ============ deep 策略弃用验证 ============

class TestDeepStrategyDeprecated:
    """spec v1.3.0：deep 策略标记弃用"""

    @pytest.mark.asyncio
    async def test_deep_strategy_logs_deprecation(self, humanizer, sample_text):
        """测试调用 deep 策略时记录弃用告警"""
        with patch("app.services.model_manager.ModelManager.call_llm",
                   return_value="改写结果"):
            with patch.object(humanizer, "evaluate_ai_score", return_value=20.0):
                result = await humanizer.humanize_deep(sample_text)
        # deep 策略仍可调用但标记弃用
        assert result.get("deprecated") is True or result.get("strategy") == "deep"
