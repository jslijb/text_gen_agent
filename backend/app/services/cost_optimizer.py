"""
成本优化模块

功能:
- 成本监控
- 限额管理
- 成本优化策略
- 使用统计
- 告警机制
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class CostMonitor:
    """成本监控器"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config/cost_config.json"
        self.usage_data: Dict[str, Any] = {}
        self.limits: Dict[str, Any] = {}
        
        # 加载配置
        self._load_config()
    
    def _load_config(self):
        """加载配置"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.limits = config.get("limits", {})
        except FileNotFoundError:
            # 默认配置
            self.limits = {
                "daily": 1000,  # 每日限额(元)
                "monthly": 30000,  # 每月限额(元)
                "per_video": 10  # 单视频限额(元)
            }
    
    def record_usage(self, model: str, cost: float, metadata: Optional[Dict[str, Any]] = None):
        """记录使用量"""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        month = datetime.utcnow().strftime("%Y-%m")
        
        # 初始化数据结构
        if today not in self.usage_data:
            self.usage_data[today] = {"total": 0, "models": {}}
        
        if model not in self.usage_data[today]["models"]:
            self.usage_data[today]["models"][model] = {"count": 0, "cost": 0}
        
        # 更新使用量
        self.usage_data[today]["total"] += cost
        self.usage_data[today]["models"][model]["count"] += 1
        self.usage_data[today]["models"][model]["cost"] += cost
        
        logger.info(f"记录使用量: model={model}, cost={cost}")
    
    def get_daily_usage(self, date: Optional[str] = None) -> Dict[str, Any]:
        """获取每日使用量"""
        if not date:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        
        return self.usage_data.get(date, {"total": 0, "models": {}})
    
    def get_monthly_usage(self, month: Optional[str] = None) -> Dict[str, Any]:
        """获取每月使用量"""
        if not month:
            month = datetime.utcnow().strftime("%Y-%m")
        
        monthly_data = {"total": 0, "models": {}}
        
        for date, data in self.usage_data.items():
            if date.startswith(month):
                monthly_data["total"] += data["total"]
                
                for model, model_data in data["models"].items():
                    if model not in monthly_data["models"]:
                        monthly_data["models"][model] = {"count": 0, "cost": 0}
                    
                    monthly_data["models"][model]["count"] += model_data["count"]
                    monthly_data["models"][model]["cost"] += model_data["cost"]
        
        return monthly_data
    
    def check_limits(self) -> Dict[str, Any]:
        """检查限额"""
        today = self.get_daily_usage()
        month = self.get_monthly_usage()
        
        daily_limit = self.limits.get("daily", 1000)
        monthly_limit = self.limits.get("monthly", 30000)
        
        daily_usage = today["total"]
        monthly_usage = month["total"]
        
        result = {
            "daily": {
                "usage": daily_usage,
                "limit": daily_limit,
                "remaining": daily_limit - daily_usage,
                "percentage": f"{daily_usage/daily_limit*100:.1f}%"
            },
            "monthly": {
                "usage": monthly_usage,
                "limit": monthly_limit,
                "remaining": monthly_limit - monthly_usage,
                "percentage": f"{monthly_usage/monthly_limit*100:.1f}%"
            },
            "alerts": []
        }
        
        # 检查是否超限
        if daily_usage >= daily_limit:
            result["alerts"].append("每日限额已用完")
        elif daily_usage >= daily_limit * 0.8:
            result["alerts"].append("每日限额接近上限")
        
        if monthly_usage >= monthly_limit:
            result["alerts"].append("每月限额已用完")
        elif monthly_usage >= monthly_limit * 0.8:
            result["alerts"].append("每月限额接近上限")
        
        return result


class CostOptimizer:
    """成本优化器"""
    
    def __init__(self):
        # 模型成本(相对值)
        self.model_costs = {
            "agnes-2.5-flash": 1,  # 免费
            "wan2.7-t2v-2026-06-12": 5,
            "wan2.7-r2v-2026-06-12": 5,
            "qwen-image-3.0": 3,
            "happyhorse-1.1-r2v": 4,
            "happyhorse-1.1-t2v": 4,
            "wan3.0-video": 6,
            "qwen-image-3.0-pro": 5,
            "happyhorse-1.1-i2v": 4,
            "qwen-image-2.0-pro-2026-06-22": 4
        }
    
    def optimize_model_selection(
        self, 
        available_models: List[str],
        budget: float
    ) -> List[str]:
        """
        优化模型选择
        
        Args:
            available_models: 可用模型列表
            budget: 预算
            
        Returns:
            优化后的模型列表(按成本排序)
        """
        # 按成本排序
        sorted_models = sorted(
            available_models,
            key=lambda m: self.model_costs.get(m, 10)
        )
        
        # 过滤超出预算的模型
        optimized = []
        total_cost = 0
        
        for model in sorted_models:
            cost = self.model_costs.get(model, 10)
            if total_cost + cost <= budget:
                optimized.append(model)
                total_cost += cost
        
        return optimized
    
    def estimate_cost(self, model: str, duration: int = 5) -> float:
        """估算成本"""
        base_cost = self.model_costs.get(model, 10)
        
        # 根据时长调整
        if duration > 5:
            base_cost *= (duration / 5)
        
        return base_cost
    
    def get_cost_effective_model(self, task_type: str) -> str:
        """获取高性价比模型"""
        # 根据任务类型推荐模型
        if task_type == "image":
            return "qwen-image-3.0"
        elif task_type == "video":
            return "agnes-2.5-flash"  # 免费
        else:
            return "agnes-2.5-flash"


class UsageReporter:
    """使用报告"""
    
    def __init__(self, monitor: CostMonitor):
        self.monitor = monitor
    
    def generate_daily_report(self, date: Optional[str] = None) -> Dict[str, Any]:
        """生成每日报告"""
        usage = self.monitor.get_daily_usage(date)
        limits = self.monitor.check_limits()
        
        report = {
            "date": date or datetime.utcnow().strftime("%Y-%m-%d"),
            "usage": usage,
            "limits": limits,
            "generated_at": datetime.utcnow().isoformat()
        }
        
        return report
    
    def generate_monthly_report(self, month: Optional[str] = None) -> Dict[str, Any]:
        """生成每月报告"""
        usage = self.monitor.get_monthly_usage(month)
        limits = self.monitor.check_limits()
        
        report = {
            "month": month or datetime.utcnow().strftime("%Y-%m"),
            "usage": usage,
            "limits": limits,
            "generated_at": datetime.utcnow().isoformat()
        }
        
        return report
    
    def export_report(self, filepath: str, report_type: str = "daily"):
        """导出报告"""
        if report_type == "daily":
            report = self.generate_daily_report()
        else:
            report = self.generate_monthly_report()
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"报告已导出: {filepath}")


class AlertManager:
    """告警管理器"""
    
    def __init__(self):
        self.alerts: List[Dict[str, Any]] = []
    
    def add_alert(self, level: str, message: str, metadata: Optional[Dict[str, Any]] = None):
        """添加告警"""
        alert = {
            "level": level,  # info, warning, critical
            "message": message,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.alerts.append(alert)
        
        logger.warning(f"告警 [{level}]: {message}")
    
    def get_alerts(self, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取告警"""
        if level:
            return [a for a in self.alerts if a["level"] == level]
        
        return self.alerts
    
    def clear_alerts(self):
        """清空告警"""
        self.alerts.clear()
        logger.info("告警已清空")


class CostSavingStrategy:
    """成本节省策略"""
    
    @staticmethod
    def get_strategy(usage_percentage: float) -> Dict[str, Any]:
        """获取成本节省策略"""
        if usage_percentage < 50:
            return {
                "strategy": "正常使用",
                "recommendations": [
                    "继续当前使用模式",
                    "定期监控成本"
                ]
            }
        elif usage_percentage < 80:
            return {
                "strategy": "适度优化",
                "recommendations": [
                    "优先使用免费模型",
                    "批量处理任务",
                    "优化视频时长"
                ]
            }
        elif usage_percentage < 100:
            return {
                "strategy": "紧急优化",
                "recommendations": [
                    "立即停止高成本模型",
                    "切换到免费模型",
                    "减少视频生成数量",
                    "优化分镜数量"
                ]
            }
        else:
            return {
                "strategy": "超限处理",
                "recommendations": [
                    "暂停所有任务",
                    "联系管理员增加限额",
                    "等待限额重置"
                ]
            }