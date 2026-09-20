import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, Float, Boolean, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.config.database import Base
from app.config.platforms import (
    DEFAULT_PLATFORM,
    PLATFORMS,
    channels_of,
    genres_of,
    is_valid_pair,
)
from app.config.types import GUID, JSONType


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    synopsis: Mapped[str] = mapped_column(Text, nullable=False)
    # 2026-09-14 平台化：作品投放的目标平台。它决定 gender/genre 的合法取值域，
    # 分类体系集中在 app/config/platforms.py，不在此处硬编码。
    platform: Mapped[str] = mapped_column(String(20), nullable=False, default=DEFAULT_PLATFORM)
    # spec v1.4.0：gender 为一级分类。平台化后沿用该列承载"频道"：
    #   百度 → 男性向/女性向/无性向；番茄 → 女频/男频
    gender: Mapped[str] = mapped_column(String(10), nullable=False, default="无性向")
    genre: Mapped[str] = mapped_column(String(20), nullable=False)
    target_word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    initial_chapters: Mapped[int] = mapped_column(Integer, default=10)
    total_chapters: Mapped[int] = mapped_column(Integer, default=30)
    daily_chapters: Mapped[int] = mapped_column(Integer, default=2)
    daily_publish_time: Mapped[str] = mapped_column(String(5), default="08:00")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    outline: Mapped[dict] = mapped_column(JSONType(), nullable=True)
    characters: Mapped[dict] = mapped_column(JSONType(), nullable=True)
    foreshadowing_plan: Mapped[dict] = mapped_column(JSONType(), nullable=True)
    cover_url: Mapped[str] = mapped_column(String(255), nullable=True)  # spec 6.1 字段11：封面URL
    titles: Mapped[dict] = mapped_column(JSONType(), nullable=True)  # 平台分发标题列表
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chapters: Mapped[list["Chapter"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    foreshadowings: Mapped[list["Foreshadowing"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    video_tasks: Mapped[list["VideoTask"]] = relationship(back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("target_word_count BETWEEN 10000 AND 300000", name="ck_project_word_count"),
        CheckConstraint("initial_chapters BETWEEN 1 AND 50", name="ck_project_initial_chapters"),
        CheckConstraint("total_chapters BETWEEN 10 AND 200", name="ck_project_total_chapters"),
        CheckConstraint("daily_chapters BETWEEN 1 AND 5", name="ck_project_daily_chapters"),
        CheckConstraint("status IN ('draft','generating','pending_review','reviewed','publishing','published')", name="ck_project_status"),
        # spec v1.4.0 + 2026-09-14 平台化：gender 取值域 = 百度频道 ∪ 番茄频道
        CheckConstraint(
            "gender IN ('男性向','女性向','无性向','女频','男频')",
            name="ck_project_gender",
        ),
        CheckConstraint("platform IN ('baidu','fanqie')", name="ck_project_platform"),
    )

    # ===== 平台化分类（2026-09-14）=====
    # 权威定义在 app/config/platforms.py；此处只做转发，避免两处硬编码漂移。
    DEFAULT_PLATFORM_KEY = DEFAULT_PLATFORM

    # 兼容旧引用的常量（等价于百度平台，历史测试与旧调用方依赖）
    VALID_GENDERS = PLATFORMS["baidu"]["channels"]
    VALID_GENRES_BY_GENDER = PLATFORMS["baidu"]["genres"]
    VALID_GENRES = [g for genres in VALID_GENRES_BY_GENDER.values() for g in genres]

    # spec v1.4.0：旧 genre → 新 gender+genre 映射（数据迁移用）
    GENRE_MIGRATION_MAP = {
        "悬疑推理": ("无性向", "恐怖推理"),
        "都市情感": ("男性向", "都市情感"),
        "重生逆袭": ("无性向", "复仇爽文"),
        "甜宠虐恋": ("女性向", "现代言情"),
        "古言宫斗": ("女性向", "古代言情"),
        "玄幻仙侠": ("男性向", "历史故事"),
        "科幻": ("男性向", "历史故事"),
        "其他": ("无性向", "见闻杂谈"),
    }

    @classmethod
    def get_channels(cls, platform: str | None = None) -> list[str]:
        """返回指定平台的合法频道（一级分类）"""
        return channels_of(platform)

    @classmethod
    def get_genres_for_gender(cls, gender: str, platform: str | None = None) -> list[str]:
        """返回指定平台/频道下的二级品类"""
        return genres_of(platform, gender)

    @classmethod
    def is_valid_gender_genre_pair(
        cls, gender: str, genre: str, platform: str | None = None
    ) -> bool:
        """校验「频道 + 品类」组合是否合法"""
        return is_valid_pair(platform, gender, genre)
