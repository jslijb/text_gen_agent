"""
成本优化模块单元测试

测试内容:
1. 成本监控测试
2. 成本优化测试
3. 使用报告测试
4. 告警管理测试
"""

import pytest
import json
import tempfile
from datetime import datetime
from unittest.mock import patch


class TestCostMonitor:
    """成本监控器测试"""
    
    def test_record_usage(self):
        """测试记录使用量"""
        from app.services.cost_optimizer import CostMonitor
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"limits": {"daily": 1000, "monthly": 30000}}, f)
            config_path = f.name
        
        monitor = CostMonitor(config_path)
        
        monitor.record_usage("test-model", 10.0)
        
        today = datetime.utcnow().strftime("%Y-%m-%d")
        usage = monitor.get_daily_usage(today)
        
        assert usage["total"] == 10.0
    
    def test_get_daily_usage(self):
        """测试获取每日使用量"""
        from app.services.cost_optimizer import CostMonitor
        
        monitor = CostMonitor()
        
        usage = monitor.get_daily_usage()
        
        assert usage is not None
        assert "total" in usage
        assert "models" in usage
    
    def test_get_monthly_usage(self):
        """测试获取每月使用量"""
        from app.services.cost_optimizer import CostMonitor
        
        monitor = CostMonitor()
        
        usage = monitor.get_monthly_usage()
        
        assert usage is not None
        assert "total" in usage
        assert "models" in usage
    
    def test_check_limits(self):
        """测试检查限额"""
        from app.services.cost_optimizer import CostMonitor
        
        monitor = CostMonitor()
        
        result = monitor.check_limits()
        
        assert result is not None
        assert "daily" in result
        assert "monthly" in result
        assert "alerts" in result


class TestCostOptimizer:
    """成本优化器测试"""
    
    def test_optimize_model_selection(self):
        """测试优化模型选择"""
        from app.services.cost_optimizer import CostOptimizer
        
        optimizer = CostOptimizer()
        
        models = ["agnes-2.5-flash", "wan2.7-t2v-2026-06-12", "qwen-image-3.0"]
        
        optimized = optimizer.optimize_model_selection(models, 10)
        
        assert len(optimized) > 0
        assert "agnes-2.5-flash" in optimized  # 免费模型应该优先
    
    def test_estimate_cost(self):
        """测试估算成本"""
        from app.services.cost_optimizer import CostOptimizer
        
        optimizer = CostOptimizer()
        
        cost = optimizer.estimate_cost("agnes-2.5-flash", 5)
        
        assert cost > 0
    
    def test_get_cost_effective_model(self):
        """测试获取高性价比模型"""
        from app.services.cost_optimizer import CostOptimizer
        
        optimizer = CostOptimizer()
        
        model = optimizer.get_cost_effective_model("video")
        
        assert model is not None


class TestUsageReporter:
    """使用报告测试"""
    
    def test_generate_daily_report(self):
        """测试生成每日报告"""
        from app.services.cost_optimizer import CostMonitor, UsageReporter
        
        monitor = CostMonitor()
        reporter = UsageReporter(monitor)
        
        report = reporter.generate_daily_report()
        
        assert report is not None
        assert "date" in report
        assert "usage" in report
        assert "limits" in report
    
    def test_generate_monthly_report(self):
        """测试生成每月报告"""
        from app.services.cost_optimizer import CostMonitor, UsageReporter
        
        monitor = CostMonitor()
        reporter = UsageReporter(monitor)
        
        report = reporter.generate_monthly_report()
        
        assert report is not None
        assert "month" in report
        assert "usage" in report
        assert "limits" in report


class TestAlertManager:
    """告警管理器测试"""
    
    def test_add_alert(self):
        """测试添加告警"""
        from app.services.cost_optimizer import AlertManager
        
        manager = AlertManager()
        
        manager.add_alert("warning", "测试告警")
        
        alerts = manager.get_alerts()
        
        assert len(alerts) == 1
        assert alerts[0]["message"] == "测试告警"
    
    def test_get_alerts_by_level(self):
        """测试按级别获取告警"""
        from app.services.cost_optimizer import AlertManager
        
        manager = AlertManager()
        
        manager.add_alert("info", "信息告警")
        manager.add_alert("warning", "警告告警")
        manager.add_alert("critical", "严重告警")
        
        warnings = manager.get_alerts("warning")
        
        assert len(warnings) == 1
        assert warnings[0]["level"] == "warning"
    
    def test_clear_alerts(self):
        """测试清空告警"""
        from app.services.cost_optimizer import AlertManager
        
        manager = AlertManager()
        
        manager.add_alert("warning", "测试告警")
        manager.clear_alerts()
        
        alerts = manager.get_alerts()
        
        assert len(alerts) == 0


class TestCostSavingStrategy:
    """成本节省策略测试"""
    
    def test_get_strategy_low_usage(self):
        """测试低使用率策略"""
        from app.services.cost_optimizer import CostSavingStrategy
        
        strategy = CostSavingStrategy.get_strategy(30)
        
        assert strategy is not None
        assert "strategy" in strategy
        assert "recommendations" in strategy
    
    def test_get_strategy_medium_usage(self):
        """测试中等使用率策略"""
        from app.services.cost_optimizer import CostSavingStrategy
        
        strategy = CostSavingStrategy.get_strategy(60)
        
        assert strategy is not None
    
    def test_get_strategy_high_usage(self):
        """测试高使用率策略"""
        from app.services.cost_optimizer import CostSavingStrategy
        
        strategy = CostSavingStrategy.get_strategy(90)
        
        assert strategy is not None
    
    def test_get_strategy_over_limit(self):
        """测试超限策略"""
        from app.services.cost_optimizer import CostSavingStrategy
        
        strategy = CostSavingStrategy.get_strategy(110)
        
        assert strategy is not None


# ============ 集成测试 ============

class TestCostOptimizerIntegration:
    """成本优化集成测试"""
    
    @pytest.mark.integration
    def test_full_cost_management(self):
        """测试完整成本管理"""
        from app.services.cost_optimizer import CostMonitor, CostOptimizer, AlertManager
        
        monitor = CostMonitor()
        optimizer = CostOptimizer()
        alert_manager = AlertManager()
        
        # 记录使用量
        monitor.record_usage("agnes-2.5-flash", 10.0)
        
        # 检查限额
        limits = monitor.check_limits()
        assert limits is not None
        
        # 优化模型选择
        models = optimizer.optimize_model_selection(["agnes-2.5-flash"], 10)
        assert len(models) > 0
        
        # 添加告警
        alert_manager.add_alert("info", "测试完成")
        alerts = alert_manager.get_alerts()
        assert len(alerts) > 0


# ============ 性能测试 ============

class TestCostOptimizerPerformance:
    """成本优化性能测试"""
    
    @pytest.mark.performance
    def test_record_usage_performance(self):
        """测试记录使用量性能"""
        import time
        from app.services.cost_optimizer import CostMonitor
        
        monitor = CostMonitor()
        
        start_time = time.time()
        
        for i in range(100):
            monitor.record_usage("test-model", 1.0)
        
        elapsed = time.time() - start_time
        
        # 验证性能(100次应该在1秒内完成)
        assert elapsed < 1.0