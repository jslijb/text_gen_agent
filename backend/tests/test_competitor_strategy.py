"""
对标账号策略应用单元测试

测试内容:
1. 对标账号分析测试
2. 新号起步策略测试
3. 标题优化测试
4. 文案优化测试
5. 系列化管理测试
"""

import pytest
from datetime import datetime


class TestCompetitorStrategy:
    """对标账号策略测试"""
    
    def test_get_competitor_analysis(self):
        """测试获取对标账号分析"""
        from app.services.competitor_strategy import CompetitorStrategy
        
        strategy = CompetitorStrategy()
        
        # 获取所有对标账号
        competitors = strategy.get_competitor_analysis()
        
        assert len(competitors) > 0
        assert "漫剧工厂" in competitors
        assert "短剧研究所" in competitors
    
    def test_get_competitor_analysis_by_genre(self):
        """测试按题材筛选对标账号"""
        from app.services.competitor_strategy import CompetitorStrategy
        
        strategy = CompetitorStrategy()
        
        # 获取都市言情类对标账号
        competitors = strategy.get_competitor_analysis("都市言情")
        
        assert len(competitors) > 0
    
    def test_get_success_factors(self):
        """测试获取成功要素"""
        from app.services.competitor_strategy import CompetitorStrategy
        
        strategy = CompetitorStrategy()
        
        factors = strategy.get_success_factors()
        
        assert len(factors) > 0
        assert "强情节、快节奏、高反转" in factors
    
    def test_get_new_account_strategy(self):
        """测试获取新号起步策略"""
        from app.services.competitor_strategy import CompetitorStrategy
        
        strategy = CompetitorStrategy()
        
        strategy_info = strategy.get_new_account_strategy()
        
        assert "phase_1" in strategy_info
        assert "phase_2" in strategy_info
        assert "phase_3" in strategy_info
    
    def test_optimize_title(self):
        """测试优化标题"""
        from app.services.competitor_strategy import CompetitorStrategy
        
        strategy = CompetitorStrategy()
        
        # 测试短标题
        short_title = "测试标题"
        optimized = strategy.optimize_title(short_title, "都市言情")
        
        assert len(optimized) > len(short_title)
        
        # 测试无标签标题
        no_tag_title = "重生回19岁,她做了一个让所有人震惊的决定"
        optimized = strategy.optimize_title(no_tag_title, "都市言情")
        
        assert "#" in optimized
    
    def test_optimize_script(self):
        """测试优化文案"""
        from app.services.competitor_strategy import CompetitorStrategy
        
        strategy = CompetitorStrategy()
        
        script = {
            "title": "测试文案",
            "shots": [
                {
                    "sequence": 1,
                    "description": "第一个镜头",
                    "narration": "重生回19岁"
                },
                {
                    "sequence": 2,
                    "description": "第二个镜头",
                    "narration": "她做了一个决定"
                }
            ]
        }
        
        optimized = strategy.optimize_script(script, "都市言情")
        
        assert optimized is not None
    
    def test_get_best_publish_time(self):
        """测试获取最佳发布时间"""
        from app.services.competitor_strategy import CompetitorStrategy
        
        strategy = CompetitorStrategy()
        
        # 测试工作日
        times = strategy.get_best_publish_time()
        
        assert len(times) > 0
        
        # 测试周末
        weekend_times = strategy.get_best_publish_time("周末")
        
        assert len(weekend_times) > 0
    
    def test_get_content_plan(self):
        """测试获取内容计划"""
        from app.services.competitor_strategy import CompetitorStrategy
        
        strategy = CompetitorStrategy()
        
        plan = strategy.get_content_plan(7)
        
        assert len(plan) == 7
        assert all("day" in day for day in plan)


class TestSeriesManager:
    """系列化管理测试"""
    
    def test_create_series(self):
        """测试创建系列"""
        from app.services.competitor_strategy import SeriesManager
        
        manager = SeriesManager()
        
        series = manager.create_series("重生回19岁", "都市言情", 30)
        
        assert series is not None
        assert "id" in series
        assert series["name"] == "重生回19岁"
        assert series["total_episodes"] == 30
    
    def test_add_episode(self):
        """测试添加剧集"""
        from app.services.competitor_strategy import SeriesManager
        
        manager = SeriesManager()
        
        series = manager.create_series("测试系列", "都市言情", 10)
        series_id = series["id"]
        
        episode = {
            "episode": 1,
            "title": "第一集",
            "content": "测试内容"
        }
        
        updated_series = manager.add_episode(series_id, episode)
        
        assert updated_series is not None
        assert updated_series["current_episode"] == 1
    
    def test_get_series(self):
        """测试获取系列"""
        from app.services.competitor_strategy import SeriesManager
        
        manager = SeriesManager()
        
        series = manager.create_series("测试系列", "都市言情", 10)
        series_id = series["id"]
        
        retrieved = manager.get_series(series_id)
        
        assert retrieved is not None
        assert retrieved["id"] == series_id
    
    def test_get_series_progress(self):
        """测试获取系列进度"""
        from app.services.competitor_strategy import SeriesManager
        
        manager = SeriesManager()
        
        series = manager.create_series("测试系列", "都市言情", 10)
        series_id = series["id"]
        
        # 添加几集
        for i in range(3):
            manager.add_episode(series_id, {"episode": i + 1})
        
        progress = manager.get_series_progress(series_id)
        
        assert progress is not None
        assert progress["current_episode"] == 3
        assert progress["total_episodes"] == 10
        assert "progress" in progress


class TestInteractiveGuide:
    """互动引导测试"""
    
    def test_generate_call_to_action(self):
        """测试生成行动号召"""
        from app.services.competitor_strategy import InteractiveGuide
        
        # 测试未完结
        cta = InteractiveGuide.generate_call_to_action(5, 10)
        
        assert "关注" in cta
        assert "下集" in cta
        
        # 测试已完结
        cta = InteractiveGuide.generate_call_to_action(10, 10)
        
        assert "感谢" in cta
    
    def test_generate_comment_prompt(self):
        """测试生成评论引导"""
        from app.services.competitor_strategy import InteractiveGuide
        
        # 测试不同题材
        prompts = {
            "都市言情": "女主角",
            "悬疑反转": "结局",
            "家庭伦理": "你",
            "玄幻修真": "主角"
        }
        
        for genre, keyword in prompts.items():
            prompt = InteractiveGuide.generate_comment_prompt(genre)
            assert keyword in prompt
    
    def test_generate_hashtags(self):
        """测试生成话题标签"""
        from app.services.competitor_strategy import InteractiveGuide
        
        # 测试不同题材
        genres = ["都市言情", "悬疑反转", "家庭伦理", "玄幻修真"]
        
        for genre in genres:
            hashtags = InteractiveGuide.generate_hashtags(genre)
            
            assert len(hashtags) > 0
            assert all("#" in tag for tag in hashtags)


# ============ 集成测试 ============

class TestCompetitorStrategyIntegration:
    """对标账号策略集成测试"""
    
    @pytest.mark.integration
    def test_full_strategy_application(self):
        """测试完整策略应用"""
        from app.services.competitor_strategy import CompetitorStrategy, SeriesManager
        
        strategy = CompetitorStrategy()
        manager = SeriesManager()
        
        # 1. 获取对标账号分析
        competitors = strategy.get_competitor_analysis("都市言情")
        assert len(competitors) > 0
        
        # 2. 获取新号起步策略
        new_account_strategy = strategy.get_new_account_strategy()
        assert "phase_1" in new_account_strategy
        
        # 3. 创建系列
        series = manager.create_series("测试系列", "都市言情", 30)
        assert series is not None
        
        # 4. 优化标题
        title = strategy.optimize_title("重生回19岁", "都市言情")
        assert len(title) >= 17
        
        # 5. 获取最佳发布时间
        publish_times = strategy.get_best_publish_time()
        assert len(publish_times) > 0


# ============ 性能测试 ============

class TestCompetitorStrategyPerformance:
    """对标账号策略性能测试"""
    
    @pytest.mark.performance
    def test_get_competitor_analysis_performance(self):
        """测试获取对标账号分析性能"""
        import time
        from app.services.competitor_strategy import CompetitorStrategy
        
        strategy = CompetitorStrategy()
        
        start_time = time.time()
        
        for _ in range(100):
            strategy.get_competitor_analysis()
        
        elapsed = time.time() - start_time
        
        # 验证性能(100次应该在1秒内完成)
        assert elapsed < 1.0
    
    @pytest.mark.performance
    def test_optimize_title_performance(self):
        """测试优化标题性能"""
        import time
        from app.services.competitor_strategy import CompetitorStrategy
        
        strategy = CompetitorStrategy()
        
        start_time = time.time()
        
        for _ in range(100):
            strategy.optimize_title("测试标题", "都市言情")
        
        elapsed = time.time() - start_time
        
        # 验证性能(100次应该在1秒内完成)
        assert elapsed < 1.0