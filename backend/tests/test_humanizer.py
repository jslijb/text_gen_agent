import pytest
from unittest.mock import patch, MagicMock
from app.services.humanizer import Humanizer, NOVEL_FORBIDDEN_PATTERNS


class TestHumanizerQuick:
    def test_replace_forbidden_patterns(self):
        humanizer = Humanizer()
        text = "值得注意的是，他感到非常震惊。不仅如此，总而言之，毫无疑问。"
        result, count = humanizer.replace_forbidden_patterns(text)
        assert "值得注意的是" not in result
        assert "他感到非常震惊" not in result
        assert "不仅如此" not in result
        assert "总而言之" not in result
        assert "毫无疑问" not in result
        assert count >= 4

    def test_quick_humanize(self):
        humanizer = Humanizer()
        text = "值得注意的是，这个发现具有重要意义。不仅如此，它产生了深远影响。"
        result = humanizer.humanize_quick(text)
        assert result["strategy"] == "quick"
        assert result["patterns_replaced"] >= 2
        assert "值得注意的是" not in result["text"]

    def test_no_forbidden_patterns(self):
        humanizer = Humanizer()
        text = "他推开门，走了进去。屋里很暗。"
        result, count = humanizer.replace_forbidden_patterns(text)
        assert count == 0
        assert result == text


class TestHumanizerAIScore:
    def test_high_ai_score(self):
        humanizer = Humanizer()
        text = "值得注意的是，这个发现具有重要意义。不仅如此，它产生了深远影响。毫无疑问，这引起了广泛关注。"
        score = humanizer.evaluate_ai_score(text)
        assert score > 40

    def test_low_ai_score(self):
        humanizer = Humanizer()
        text = "他推开门，走了进去。屋里很暗，他摸索着找到灯的开关。"
        score = humanizer.evaluate_ai_score(text)
        assert score < 60

    def test_score_range(self):
        humanizer = Humanizer()
        text = "普通的文本内容。"
        score = humanizer.evaluate_ai_score(text)
        assert 0 <= score <= 100


class TestForbiddenPatterns:
    def test_pattern_count(self):
        assert len(NOVEL_FORBIDDEN_PATTERNS) >= 23

    def test_all_patterns_are_tuples(self):
        for pattern in NOVEL_FORBIDDEN_PATTERNS:
            assert isinstance(pattern, tuple)
            assert len(pattern) == 2

    def test_patterns_compile(self):
        import re
        for pattern, replacement in NOVEL_FORBIDDEN_PATTERNS:
            compiled = re.compile(pattern)
            assert compiled is not None