"""
对标账号策略应用模块

功能:
- 将对标账号调研结果应用到选题、文案、分镜生成
- 提供新号起步策略建议
- 优化更新频率和发布时间
- 系列化运营建议
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CompetitorStrategy:
    """对标账号策略应用"""
    
    def __init__(self):
        # 基于调研结果的对标账号数据
        self.competitors = {
            "漫剧工厂": {
                "followers": "50-100万+",
                "genres": ["都市言情", "玄幻修真"],
                "style": "动态漫",
                "update_frequency": "日更1-2条",
                "features": ["系列化内容", "标题吸引", "封面统一"]
            },
            "短剧研究所": {
                "followers": "30-80万+",
                "genres": ["悬疑反转", "家庭伦理"],
                "style": "写实+AI",
                "update_frequency": "日更",
                "features": ["强钩子开头", "悬念结尾", "引导关注"]
            },
            "可灵AI创作营": {
                "followers": "20-50万+",
                "genres": ["科幻", "奇幻"],
                "style": "纯AI生成",
                "update_frequency": "每周3-5条",
                "features": ["特效丰富", "画面精美", "技术向"]
            },
            "AI小说推文": {
                "followers": "10-30万+",
                "genres": ["霸总", "甜宠"],
                "style": "图文轮播",
                "update_frequency": "日更3-5条",
                "features": ["低成本", "批量生产", "引流转化"]
            }
        }
        
        # 新号起步推荐
        self.new_account_recommendations = {
            "genres": ["都市言情", "悬疑反转", "家庭伦理"],
            "update_frequency": "日更1-2条",
            "best_times": ["12:00-13:00", "18:00-20:00", "21:00-22:00"],
            "test_period": "1-2周",
            "growth_period": "1-2个月"
        }
        
        # 成功要素
        self.success_factors = [
            "强情节、快节奏、高反转",
            "开头3秒抓眼球",
            "标题15-25字,包含悬念词和情绪词",
            "结尾留悬念引导追更",
            "稳定更新频率",
            "系列化内容规划",
            "互动引导提升数据"
        ]
    
    def get_competitor_analysis(self, genre: Optional[str] = None) -> Dict[str, Any]:
        """获取对标账号分析"""
        if genre:
            # 根据题材筛选对标账号
            filtered = {
                name: data for name, data in self.competitors.items()
                if genre in data["genres"]
            }
            return filtered
        
        return self.competitors
    
    def get_success_factors(self) -> List[str]:
        """获取成功要素"""
        return self.success_factors
    
    def get_new_account_strategy(self) -> Dict[str, Any]:
        """获取新号起步策略"""
        return {
            "phase_1": {
                "name": "测试期(1-2周)",
                "goal": "验证题材选择,测试市场反应",
                "content": "选择1-2个题材,制作10-20条测试内容",
                "frequency": "日更2-3条",
                "focus": "观察数据,找到爆款方向"
            },
            "phase_2": {
                "name": "成长期(1-2个月)",
                "goal": "积累首批粉丝,建立账号定位",
                "content": "聚焦爆款题材,系列化运营",
                "frequency": "日更1-2条",
                "focus": "优化内容,提升互动"
            },
            "phase_3": {
                "name": "成熟期(2个月后)",
                "goal": "稳定粉丝增长,探索变现",
                "content": "扩大题材范围,打造IP",
                "frequency": "日更2-3条",
                "focus": "多维度变现,品牌建设"
            }
        }
    
    def optimize_title(self, title: str, genre: str) -> str:
        """优化标题"""
        # 确保标题符合规范
        if len(title) < 17:
            logger.warning(f"标题过短: {len(title)} 字,建议17-30字")
        
        if len(title) > 30:
            logger.warning(f"标题过长: {len(title)} 字,建议17-30字")
        
        # 检查是否包含悬念词
        suspense_words = ["真相揭晓", "意外发现", "结局反转", "竟然", "原来"]
        if not any(word in title for word in suspense_words):
            logger.info("建议添加悬念词提升吸引力")
        
        # 检查是否包含情绪词
        emotion_words = ["虐心", "高甜", "泪目", "震惊", "可怕"]
        if not any(word in title for word in emotion_words):
            logger.info("建议添加情绪词提升共鸣")
        
        # 检查是否包含话题标签
        if "#" not in title:
            # 添加话题标签
            genre_tags = {
                "都市言情": "#短剧#",
                "悬疑反转": "#悬疑#",
                "家庭伦理": "#家庭#",
                "玄幻修真": "#玄幻#"
            }
            tag = genre_tags.get(genre, "#短剧#")
            title = f"{title}{tag}"
        
        return title
    
    def optimize_script(self, script: Dict[str, Any], genre: str) -> Dict[str, Any]:
        """优化文案"""
        # 确保开头3秒有钩子
        if "shots" in script and script["shots"]:
            first_shot = script["shots"][0]
            if "narration" in first_shot:
                narration = first_shot["narration"]
                # 检查开头是否有钩子
                hook_words = ["震惊", "意外", "竟然", "真相", "原来"]
                if not any(word in narration[:20] for word in hook_words):
                    logger.info("建议在开头添加钩子,提升完播率")
        
        # 确保结尾有悬念
        if "shots" in script and script["shots"]:
            last_shot = script["shots"][-1]
            if "narration" in last_shot:
                narration = last_shot["narration"]
                # 检查结尾是否有悬念
                suspense_words = ["下集", "续集", "未完", "待续", "关注"]
                if not any(word in narration[-20:] for word in suspense_words):
                    logger.info("建议在结尾添加悬念,引导追更")
        
        return script
    
    def get_best_publish_time(self, day_of_week: Optional[str] = None) -> List[str]:
        """获取最佳发布时间"""
        # 基于调研结果的最佳发布时间
        best_times = ["12:00-13:00", "18:00-20:00", "21:00-22:00"]
        
        if day_of_week == "周末":
            # 周末可以稍晚
            return ["10:00-12:00", "15:00-17:00", "20:00-22:00"]
        
        return best_times
    
    def get_content_plan(self, days: int = 7) -> List[Dict[str, Any]]:
        """获取内容计划"""
        plan = []
        
        for day in range(1, days + 1):
            # 每天1-2条内容
            plan.append({
                "day": day,
                "content_count": 2,
                "genres": ["都市言情", "悬疑反转"],
                "publish_times": ["12:00", "19:00"],
                "notes": "系列化内容,保持连贯性"
            })
        
        return plan


class SeriesManager:
    """系列化管理"""
    
    def __init__(self):
        self.series = []
    
    def create_series(self, name: str, genre: str, total_episodes: int) -> Dict[str, Any]:
        """创建系列"""
        series = {
            "id": f"series_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "name": name,
            "genre": genre,
            "total_episodes": total_episodes,
            "current_episode": 0,
            "episodes": [],
            "created_at": datetime.utcnow().isoformat()
        }
        
        self.series.append(series)
        
        return series
    
    def add_episode(self, series_id: str, episode: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """添加剧集"""
        for series in self.series:
            if series["id"] == series_id:
                series["episodes"].append(episode)
                series["current_episode"] = len(series["episodes"])
                return series
        
        return None
    
    def get_series(self, series_id: str) -> Optional[Dict[str, Any]]:
        """获取系列"""
        for series in self.series:
            if series["id"] == series_id:
                return series
        
        return None
    
    def get_series_progress(self, series_id: str) -> Dict[str, Any]:
        """获取系列进度"""
        series = self.get_series(series_id)
        
        if not series:
            return {"error": "系列不存在"}
        
        progress = series["current_episode"] / series["total_episodes"]
        
        return {
            "series_id": series_id,
            "name": series["name"],
            "current_episode": series["current_episode"],
            "total_episodes": series["total_episodes"],
            "progress": f"{progress:.1%}",
            "remaining": series["total_episodes"] - series["current_episode"]
        }


class InteractiveGuide:
    """互动引导"""
    
    @staticmethod
    def generate_call_to_action(episode: int, total_episodes: int) -> str:
        """生成行动号召"""
        if episode < total_episodes:
            return f"关注我,下集更精彩!第{episode}/{total_episodes}集"
        else:
            return "感谢观看!关注我,获取更多精彩内容"
    
    @staticmethod
    def generate_comment_prompt(genre: str) -> str:
        """生成评论引导"""
        prompts = {
            "都市言情": "你觉得女主角的选择对吗?评论区聊聊!",
            "悬疑反转": "你猜到结局了吗?评论区告诉我!",
            "家庭伦理": "如果是你,你会怎么做?评论区分享你的看法!",
            "玄幻修真": "你觉得主角能突破吗?评论区预测一下!"
        }
        
        return prompts.get(genre, "你觉得这个故事怎么样?评论区聊聊!")
    
    @staticmethod
    def generate_hashtags(genre: str) -> List[str]:
        """生成话题标签"""
        hashtags = {
            "都市言情": ["#短剧#", "#都市言情#", "#甜宠#"],
            "悬疑反转": ["#悬疑#", "#反转#", "#推理#"],
            "家庭伦理": ["#家庭#", "#伦理#", "#情感#"],
            "玄幻修真": ["#玄幻#", "#修真#", "#仙侠#"]
        }
        
        return hashtags.get(genre, ["#短剧#", "#AI漫剧#"])