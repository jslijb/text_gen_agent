from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from app.config.database import get_db
from app.config import platforms as pf
from app.models.chapter import Chapter
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse

router = APIRouter(prefix="/projects", tags=["项目管理"])


@router.get("/platforms")
async def list_platforms():
    """返回各平台的频道/品类/书名规则，供前端渲染选择器（2026-09-14 平台化）

    必须定义在 /{project_id} 之前，否则 "platforms" 会被当作 UUID 路径参数吞掉。
    """
    return {
        "default": pf.DEFAULT_PLATFORM,
        "platforms": [
            {
                "key": k,
                "label": v["label"],
                "channels": v["channels"],
                "genres": v["genres"],
                "title_len": list(v["title_len"]),
                "title_prefix": v["title_prefix"],
                "publish_ready": v["publish_host"] is not None,
            }
            for k, v in pf.PLATFORMS.items()
        ],
    }


def _validate_taxonomy(platform: str, gender: str, genre: str) -> None:
    """校验「平台 + 频道 + 品类」组合，非法则抛 400"""
    pkey = pf.platform_key(platform)
    channels = pf.channels_of(pkey)
    if gender not in channels:
        raise HTTPException(
            status_code=400,
            detail=f"[{pf.label_of(pkey)}] 无效的频道，可选值：{channels}",
        )
    if not pf.is_valid_pair(pkey, gender, genre):
        raise HTTPException(
            status_code=400,
            detail=(
                f"[{pf.label_of(pkey)}] 频道[{gender}]下不支持品类[{genre}]，"
                f"可选值：{pf.genres_of(pkey, gender)}"
            ),
        )


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    # 2026-09-14 平台化：校验 平台 + 频道 + 品类 组合
    _validate_taxonomy(data.platform, data.gender, data.genre)
    project = Project(**data.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    # spec v1.4.0 规则9：创建项目后自动投递封面生成异步任务
    try:
        from app.tasks.cover_tasks import generate_cover_task
        generate_cover_task.delay(str(project.id))
    except Exception as e:
        # 封面任务投递失败不影响项目创建，用户可后续手动生成
        import logging
        logging.getLogger(__name__).warning(f"自动投递封面任务失败（不影响项目创建）: {e}")
    return project


@router.get("", response_model=ProjectListResponse)
async def list_projects(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    total = db.query(Project).count()
    items = db.query(Project).offset(skip).limit(limit).all()
    return ProjectListResponse(total=total, items=items)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: UUID, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: UUID, data: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    update_data = data.model_dump(exclude_unset=True)
    # 2026-09-14 平台化：platform / gender / genre 任一变更都需联动校验
    new_platform = update_data.get("platform", project.platform)
    new_gender = update_data.get("gender", project.gender)
    new_genre = update_data.get("genre", project.genre)
    if {"platform", "gender", "genre"} & update_data.keys():
        _validate_taxonomy(new_platform, new_gender, new_genre)
    for key, value in update_data.items():
        setattr(project, key, value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: UUID, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    db.delete(project)
    db.commit()


@router.post("/{project_id}/generate", status_code=202)
async def trigger_generate(project_id: UUID, force: bool = False, db: Session = Depends(get_db)):
    """生成首批章节。

    force=false（默认）：项目已有章节时**不清空**，只把首批补齐到 initial_chapters。
    force=true：清空已有章节与伏笔后从头重写（危险动作，仅供明确需要重跑时使用）。
    """
    import logging
    logger = logging.getLogger(__name__)
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status == "generating":
        raise HTTPException(status_code=409, detail="项目正在生成中")
    project.status = "generating"
    db.commit()
    from app.tasks.novel_tasks import generate_novel
    try:
        generate_novel.delay(str(project_id), force)
    except Exception as e:
        # 任务投递失败（如 Redis 不可用）：回滚状态，避免项目永久卡在 generating
        logger.error(f"投递生成任务失败，回滚状态: project={project_id}, error={e}")
        project.status = "draft"
        db.commit()
        raise HTTPException(status_code=503, detail=f"生成任务投递失败，请检查服务后重试: {e}")
    logger.info(f"生成任务已投递: project={project_id}, force={force}")
    return {"message": "生成任务已提交", "project_id": str(project_id), "force": force}


@router.post("/{project_id}/generate/daily", status_code=202)
async def trigger_daily_generate(project_id: UUID, chapters: int | None = None, db: Session = Depends(get_db)):
    """续写下一批章节 —— 连载的手动入口。

    chapters: 本次续写几章；不传则用项目配置的 daily_chapters。
    与定时日更走同一个任务，任务内自带 Redis 互斥锁，重复点击不会重复写章节。
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status == "generating":
        raise HTTPException(status_code=409, detail="项目正在生成中，请稍候再续写")
    existing_count = db.query(Chapter).filter(Chapter.project_id == project_id).count()
    total_target = project.total_chapters or 30
    if existing_count >= total_target:
        raise HTTPException(status_code=409, detail=f"项目已达目标章节数 {total_target}，无需续写")
    from app.tasks.novel_tasks import generate_daily_chapters
    generate_daily_chapters.delay(str(project_id), None, chapters)
    return {
        "message": "续写任务已提交",
        "project_id": str(project_id),
        "existing_chapters": existing_count,
        "total_chapters": total_target,
        "batch_size": chapters or project.daily_chapters,
    }


# 书名/标题 prompt 已上移到 app/config/platforms.py（2026-09-14 平台化），
# 百度与番茄各一份，此处不再保留副本。


@router.post("/{project_id}/generate-titles")
async def generate_titles(project_id: UUID, db: Session = Depends(get_db)):
    """按项目所属平台的书名规则生成标题（2026-09-14 平台化）

    - 百度：带"故事："前缀，17-30 字，供信息流分发
    - 番茄：不带前缀，5-20 字，大白话 +「设定/冲突」两段式
    """
    import re as _re
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    from app.services.model_manager import ModelManager
    from app.services.novel_engine import _robust_json_parse

    pkey = pf.platform_key(project.platform)
    pconf = pf.get_platform(pkey)
    prompt_tpl: str = pconf["title_prompt"]
    prefix: str = pconf["title_prefix"]
    lo, hi = pconf["title_len"]

    def _count_chars(title: str) -> int:
        return len(_re.sub(r"[^\w\u4e00-\u9fff]", "", title))

    titles: list[str] = []
    for _attempt in range(2):
        prompt = prompt_tpl.format(
            name=project.name,
            channel=project.gender,
            genre=project.genre,
            synopsis=project.synopsis[:500],
        )
        result_text = ModelManager().call_llm(prompt, role="planner", temperature=0.8, max_tokens=1024)
        parsed = _robust_json_parse(result_text)
        if isinstance(parsed, dict) and parsed.get("parse_error"):
            # 兜底：从原文里抠引号包裹的候选
            arr_match = _re.findall(r'"([^"]{4,40})"', result_text)
            titles = [t.strip() for t in arr_match[:8]] if arr_match else []
        elif isinstance(parsed, list):
            titles = [str(t) for t in parsed[:8]]
        else:
            titles = []
        # 百度必须有前缀，缺了就补；番茄不加前缀
        if prefix:
            titles = [t if t.startswith(prefix) else f"{prefix}{t}" for t in titles]
        titles = [t for t in titles if lo <= _count_chars(t) <= hi]
        if len(titles) >= 3:
            break

    if not titles:
        titles = [f"{prefix}{project.name}"]
    titles = titles[:5]
    project.titles = titles
    db.commit()
    return {"titles": titles, "project_id": str(project_id), "platform": pkey}
