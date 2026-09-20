import json
import logging
import uuid
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from app.config.database import SessionLocal
from app.models.project import Project
from app.models.chapter import Chapter
from app.models.config import Foreshadowing
from app.api.ws import broadcast_progress

logger = logging.getLogger(__name__)

# 去 AI 化策略：首批生成与日更续写统一用同一策略。
# 原实现首批用 recursive、日更用 adversarial，同一本书的章节质量与风格会漂移。
DEFAULT_HUMANIZE_STRATEGY = "recursive"

# 续写互斥锁 TTL（秒）：防止连点按钮 / 定时任务与手动触发同时跑，
# 两个任务读到同一个 existing_count → 章号相撞 → 撞 uq_chapter_project_number
CONTINUE_LOCK_TTL = 1800
CONTINUE_LOCK_KEY = "novel:continue_lock:{}"


def _project_platform(project) -> str:
    """取项目目标平台（决定字数区间与正文规范），读不到按默认平台。"""
    return getattr(project, "platform", None) or "baidu"


def _redis_client(db_index: int = 1):
    from app.config.celery_config import celery_app
    import redis as redis_lib
    broker = celery_app.conf.broker_url.replace("redis://", "").split("/")[0]
    return redis_lib.Redis.from_url(f"redis://{broker}/{db_index}")


def _current_task_id() -> str:
    """当前 Celery 任务 id；在非 Celery 上下文（本地脚本直调）下退化为随机串。"""
    try:
        from celery import current_task
        tid = getattr(current_task.request, "id", None)
        if tid:
            return str(tid)
    except Exception:
        pass
    return f"local-{uuid.uuid4().hex[:12]}"


# 仅当锁的当前持有者仍是 observed 时才改写 —— 避免两个任务同时"接管"把对方挤掉
_TAKEOVER_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
    return 1
end
return 0
"""


def _acquire_continue_lock(project_id: str, task_id: str, takeover_ok: bool = False) -> bool:
    """抢"同一项目只能有一个续写任务"的互斥锁。

    锁的 value 存 Celery task_id，用来识别两种"持锁者其实已经不算数"的情况：

    1. **同一个任务被重投**（task_id 相同）：项目配置了 task_acks_late=True，
       worker 挂掉/重启后未 ack 的任务会被重投，且 task_id 不变 —— 认锁续期即可接管。
    2. **上一个持有者已收工**（takeover_ok=True）：调用方发现项目状态已不是 generating，
       说明前一个任务已经走完流程，只是锁还没删掉，此时用 Lua CAS 原子接管。

    （2026-09-15 实测踩坑：重建 worker 后 beat 触发 + 任务重投，
     固定 value "1" 的旧锁让 3 个项目同时卡死在 generating，锁 TTL 还有 17 分钟。）

    Redis 不可用时按放行处理，不让基础设施故障阻断创作。
    """
    key = CONTINUE_LOCK_KEY.format(project_id)
    try:
        r = _redis_client()
        holder = r.get(key)
        if holder is None:
            return bool(r.set(key, str(task_id), nx=True, ex=CONTINUE_LOCK_TTL))

        holder = holder.decode("utf-8", "ignore")
        if holder == str(task_id):
            r.expire(key, CONTINUE_LOCK_TTL)
            return True

        if takeover_ok:
            ok = r.eval(_TAKEOVER_LUA, 1, key, holder, str(task_id), CONTINUE_LOCK_TTL)
            if ok:
                logger.warning(f"项目 {project_id} 的残留锁（持有者 {holder[:8]}）已接管给 {str(task_id)[:8]}")
                return True
        return False
    except Exception as e:
        logger.warning(f"续写锁获取失败，按放行处理: {e}")
        return True


def _release_continue_lock(project_id: str, task_id: str) -> None:
    """只释放自己持有的锁 —— 避免误删别的任务刚抢到的锁。"""
    key = CONTINUE_LOCK_KEY.format(project_id)
    try:
        r = _redis_client()
        holder = r.get(key)
        if holder is not None and holder.decode("utf-8", "ignore") == str(task_id):
            r.delete(key)
    except Exception:
        pass


@shared_task
def generate_novel(project_id: str, force: bool = False):
    """生成首批章节。

    force=False（默认）：项目已有章节时**不清空、不重写**，转为"补齐首批"
        （只补到 initial_chapters 为止）。连载中误点"生成"不会毁掉已更新的内容。
        force=True：显式重写——清空项目下全部章节与伏笔后从头生成。
    """
    db = SessionLocal()
    lock_task_id = _current_task_id()
    lock_held = False
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            logger.error(f"项目不存在: {project_id}")
            return

        old_chapters = (
            db.query(Chapter)
            .filter(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_number)
            .all()
        )

        # 已有章节且未显式要求重写 → 转"补齐首批"，绝不清空
        if old_chapters and not force:
            written = len(old_chapters)
            initial = project.initial_chapters or 10
            if written >= initial:
                logger.info(f"项目已写 {written} 章（≥ 首批 {initial} 章），无需补齐，跳过")
                broadcast_progress(project_id, {
                    "type": "status", "status": project.status,
                    "message": f"项目已有 {written} 章，无需补齐首批",
                })
                return
            logger.info(f"项目已写 {written} 章，补齐首批至 {initial} 章")
            broadcast_progress(project_id, {
                "type": "progress", "agent": "writer", "status": "generating",
                "message": f"已有 {written} 章，补齐首批至 {initial} 章",
            })
            try:
                generate_daily_chapters.delay(str(project_id), initial)
            except Exception as e:
                logger.error(f"补齐首批任务投递失败: {e}")
                raise
            return

        if old_chapters and force:
            logger.warning(f"[force] 清空项目 {project_id} 的旧章节 {len(old_chapters)} 章并重写")
            db.query(Chapter).filter(Chapter.project_id == project_id).delete(synchronize_session=False)
            db.query(Foreshadowing).filter(Foreshadowing.project_id == project_id).delete(synchronize_session=False)
            project.outline = None
            project.characters = None
            project.foreshadowing_plan = None
            db.commit()

        # 首批生成与续写共用同一把项目锁：否则 beat 定时日更可能在首批还在写的时候
        # 读到旧的 existing_count，从 max_num+1 开始写 → 与首批的章号撞车。
        # 注意：锁必须在"补齐首批"分支之后才抢 —— 那条分支会把活转派给 generate_daily_chapters，
        # 提前持锁会让被转派的任务自己把自己挡在门外。
        if not _acquire_continue_lock(
            str(project_id), _current_task_id(), takeover_ok=(project.status != "generating")
        ):
            logger.warning(f"项目 {project_id} 已有生成/续写任务在跑，跳过本次首批生成")
            return
        lock_held = True

        project.status = "generating"
        db.commit()
        platform = _project_platform(project)
        broadcast_progress(project_id, {"type": "status", "status": "generating", "message": "开始生成小说"})

        from app.services.novel_engine import NovelEngine
        engine = NovelEngine(platform)
        # spec 5.6.1 规则 2：实时进度推送（传入进度回调）
        def progress_cb(ch_num, total, agent, message):
            broadcast_progress(project_id, {
                "type": "progress",
                "chapter": ch_num,
                "total_chapters": total,
                "agent": agent,
                "status": "generating",
                "progress": round(ch_num / total, 2) if total else 0,
                "message": message,
            })
        result = engine.generate_full_novel(
            synopsis=project.synopsis,
            genre=project.genre,
            target_chapters=project.total_chapters or project.initial_chapters,
            initial_chapters=project.initial_chapters,
            progress_callback=progress_cb,
        )

        outline = result.get("outline", {})
        project.outline = outline
        if "characters" in outline:
            project.characters = outline["characters"]
        if "foreshadowing" in outline:
            project.foreshadowing_plan = outline["foreshadowing"]
            for fs in outline["foreshadowing"]:
                foreshadowing = Foreshadowing(
                    project_id=project.id,
                    description=fs.get("description", ""),
                    planted_chapter=fs.get("planted_chapter", 1),
                    resolved_chapter=fs.get("resolved_chapter"),
                    status="planted",
                )
                db.add(foreshadowing)

        for ch_data in result.get("chapters", []):
            chapter = Chapter(
                project_id=project.id,
                chapter_number=ch_data["chapter_number"],
                title=ch_data["title"],
                content=ch_data["content"],
                original_content=ch_data.get("original_content", ""),
                model_used=ch_data.get("model_used", ""),
                review_comment=ch_data.get("review_comment", ""),
            )
            db.add(chapter)

        project.status = "pending_review"
        db.commit()
        broadcast_progress(project_id, {"type": "status", "status": "done", "message": f"生成完成，共{len(result.get('chapters', []))}章"})
        logger.info(f"小说生成完成: {project_id}, 共{len(result.get('chapters', []))}章, 平台={platform}")

        # spec 5.2.1 + v1.5.0：生成完成后自动批量触发去 AI 化
        # 策略统一为 DEFAULT_HUMANIZE_STRATEGY（recursive：3轮×3候选 Best-of-N 评分筛选），
        # 与日更续写保持一致，避免同一本书前后章节的处理策略不同。
        saved_chapters = db.query(Chapter).filter(Chapter.project_id == project_id).order_by(Chapter.chapter_number).all()
        for ch in saved_chapters:
            humanize_chapter.delay(str(ch.id), DEFAULT_HUMANIZE_STRATEGY, platform)
            logger.info(f"已派发去AI化任务({DEFAULT_HUMANIZE_STRATEGY}, 平台={platform}): 章节 {ch.chapter_number} ({ch.id})")
    except SoftTimeLimitExceeded:
        # 软超时：任务即将被 kill，尽快回滚状态，避免永久卡在 generating
        logger.error(f"小说生成软超时，回滚状态: {project_id}")
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.status = "draft"
                db.commit()
            broadcast_progress(project_id, {"type": "error", "message": "生成超时，已回滚，请重试"})
        except Exception:
            pass
    except Exception as e:
        logger.error(f"小说生成失败: {e}", exc_info=True)
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.status = "draft"
            db.commit()
        broadcast_progress(project_id, {"type": "error", "message": f"生成失败: {e}"})
    finally:
        db.close()
        if lock_held:
            _release_continue_lock(str(project_id), lock_task_id)


@shared_task
def generate_daily_chapters(project_id: str, target_upto: int | None = None, batch_size: int | None = None):
    """续写章节 —— 连载主链路（手动触发与定时日更都走这里）。

    - target_upto: 写到第几章为止（含）。默认 total_chapters；补齐首批时传 initial_chapters
    - batch_size:  本次最多写几章。默认 daily_chapters

    与首批生成共用 NovelEngine.write_chapter_with_review 和同一套上下文规格，
    并由 Redis 互斥锁保证同一项目同时只有一个续写任务在跑。
    """
    db = SessionLocal()
    lock_task_id = _current_task_id()
    lock_held = False
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            logger.error(f"项目不存在: {project_id}")
            return

        # 项目状态已不是 generating → 上一个持有者早已走完流程，锁是残留的，允许接管。
        # 这一步是 2026-09-15 卡死事故的根治：光靠 TTL 等 30 分钟太慢，且会把项目挂在 generating。
        if not _acquire_continue_lock(
            str(project_id), lock_task_id, takeover_ok=(project.status != "generating")
        ):
            logger.warning(f"项目 {project_id} 已有续写任务在跑，本次跳过（防并发导致章号冲突）")
            return
        lock_held = True

        platform = _project_platform(project)
        existing = (
            db.query(Chapter)
            .filter(Chapter.project_id == project_id)
            .order_by(Chapter.chapter_number)
            .all()
        )
        existing_count = len(existing)
        # 章号取 max+1 而不是"总数+1"：章节号一旦有空洞（删过章），总数推算会撞唯一约束
        max_num = max((c.chapter_number for c in existing), default=0)

        total_target = target_upto or project.total_chapters or 30
        remaining = total_target - existing_count
        if remaining <= 0:
            logger.info(f"项目[{project.name}]已达到目标章节数 {total_target}，跳过续写")
            return

        per_batch = batch_size if batch_size is not None else (project.daily_chapters or 2)
        chapters_to_write = max(1, min(per_batch, remaining))

        outline = project.outline or {}
        chapters_plan = outline.get("chapters", []) or []
        characters = project.characters or {}
        character_states = json.dumps(characters, ensure_ascii=False)

        project.status = "generating"
        db.commit()
        broadcast_progress(project_id, {
            "type": "progress", "agent": "writer", "status": "generating",
            "total_chapters": total_target, "completed_chapters": existing_count,
            "message": f"开始续写：已有 {existing_count} 章，本次续写 {chapters_to_write} 章（目标 {total_target} 章）",
        })

        from app.services.novel_engine import NovelEngine, build_continuation_context
        engine = NovelEngine(platform)

        # 历史章节（已在库里的），用于构建衔接上下文
        history = [
            {"chapter_number": c.chapter_number, "title": c.title, "content": c.content}
            for c in existing
        ]
        new_chapter_ids: list[str] = []

        for i in range(chapters_to_write):
            next_num = max_num + i + 1
            if next_num <= len(chapters_plan):
                chapter_plan = dict(chapters_plan[next_num - 1])
            else:
                chapter_plan = {
                    "number": next_num,
                    "title": f"第{next_num}章",
                    "summary": "继续推进剧情，收束主线冲突并给出新钩子",
                }
            chapter_plan["number"] = next_num  # 以库内实际章号为准

            previous_summary, previous_tail = build_continuation_context(chapters_plan, history)
            result = engine.write_chapter_with_review(
                chapter_plan=chapter_plan,
                previous_summary=previous_summary,
                character_states=character_states,
                previous_tail=previous_tail,
                ch_num=next_num,
                total=total_target,
            )

            chapter = Chapter(
                project_id=project.id,
                chapter_number=next_num,
                title=result["title"],
                content=result["content"],
                original_content=result["original_content"],
                model_used=result["model_used"],
                review_comment=result["review_comment"],
                review_status="approved",
            )
            db.add(chapter)
            db.commit()
            db.refresh(chapter)
            new_chapter_ids.append(str(chapter.id))
            history.append({
                "chapter_number": next_num,
                "title": chapter.title,
                "content": chapter.content,
            })
            # 字数口径必须和合规判定一致（去掉空白后的字符数），
            # 之前用 len() 会把换行空格算进去，日志数字与平台校验结果对不上，容易误读
            from app.services.novel_engine import count_words as _cw
            word_count = _cw(chapter.content or "")
            logger.info(f"续写第{next_num}章完成: {project_id}, 字数={word_count}")
            broadcast_progress(project_id, {
                "type": "progress", "agent": "writer", "status": "generating",
                "chapter": next_num, "total_chapters": total_target,
                "completed_chapters": existing_count + i + 1,
                "message": f"第{next_num}章完成（{word_count} 字）",
            })

        # 去 AI 化：策略与首批统一，并显式传平台
        for ch_id in new_chapter_ids:
            humanize_chapter.delay(ch_id, DEFAULT_HUMANIZE_STRATEGY, platform)

        written_total = existing_count + chapters_to_write
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.status = "pending_review"
            db.commit()
        final_status = project.status if project else "pending_review"
        broadcast_progress(project_id, {
            "type": "status", "status": final_status,
            "message": f"续写完成：本次新增 {chapters_to_write} 章，累计 {written_total}/{total_target} 章",
        })
        logger.info(
            f"续写完成: {project_id}, 新增{chapters_to_write}章, 累计{written_total}/{total_target}, "
            f"平台={platform}, 已派发去AI化({DEFAULT_HUMANIZE_STRATEGY})"
        )
    except Exception as e:
        logger.error(f"续写失败: {e}", exc_info=True)
        # 别把项目永久卡在 generating
        try:
            _proj = db.query(Project).filter(Project.id == project_id).first()
            if _proj and _proj.status == "generating":
                _proj.status = "pending_review"
                db.commit()
        except Exception:
            pass
        broadcast_progress(project_id, {"type": "error", "message": f"续写失败: {e}"})
    finally:
        db.close()
        if lock_held:
            _release_continue_lock(str(project_id), lock_task_id)


@shared_task
def humanize_chapter(chapter_id: str, strategy: str = "default", platform: str | None = None):
    db = SessionLocal()
    try:
        chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not chapter:
            logger.error(f"章节不存在: {chapter_id}")
            return
        # 2026-09-14 平台化：未显式指定时，按章节所属项目的目标平台决定节奏档位
        if not platform:
            _proj = db.query(Project).filter(Project.id == chapter.project_id).first()
            platform = getattr(_proj, "platform", None) or "baidu"
        broadcast_progress(str(chapter.project_id), {"type": "progress", "agent": "humanizer", "status": "humanizing", "chapter": chapter.chapter_number, "message": f"正在对第{chapter.chapter_number}章去AI化"})
        from app.services.humanizer import Humanizer
        humanizer = Humanizer()
        original_content = chapter.content
        # 保留最初的原文（如果已去AI化过，original_content 已是原文，不再覆盖）
        if not chapter.original_content:
            chapter.original_content = original_content
        ai_score_before = humanizer._statistical_ai_score_v2(original_content)
        chapter.ai_score_before = ai_score_before
        # 不在此处commit——等去AI化完成后再一起提交，避免中途失败导致"已评分但未处理"

        import asyncio
        # v1.5.0 修复：Celery Worker 子线程中没有事件循环，get_event_loop() 会抛 RuntimeError。
        # 改用 asyncio.run()：每次创建新事件循环，运行后自动关闭，线程安全。
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            # 极端情况：已有运行中的循环（不应发生在 Celery 同步任务中）
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = pool.submit(
                    asyncio.run, humanizer.humanize(original_content, strategy, platform)
                ).result()
        else:
            result = asyncio.run(humanizer.humanize(original_content, strategy, platform))
        humanized_text = result["text"]

        # spec 5.2.3 异常 3：去AI化改变核心剧情则回滚
        # quick 策略跳过 LLM 一致性检查（纯正则替换不会改变剧情）
        if strategy != "quick":
            consistency = humanizer.check_consistency(original_content, humanized_text)
            result["consistency_check"] = consistency
            if not consistency.get("consistent", True):
                logger.warning(f"去AI化后剧情一致性检查未通过，回滚到原文: {chapter_id}, 问题: {consistency.get('issues')}")
                result["rolled_back"] = True
                result["consistency_issues"] = consistency.get("issues", [])
                chapter.humanize_strategy = result
                db.commit()
                broadcast_progress(str(chapter.project_id), {"type": "error", "agent": "humanizer", "chapter": chapter.chapter_number, "message": "去AI化改变剧情，已回滚"})
                return

        # 2026-09-15：去AI化会重写全文，字数可能被改动（改短或改长）。
        # 正文在进入这里之前刚按平台区间校准过，所以改写后若跌出区间，
        # 宁可回滚到合规原文，也不要把刚校准好的稿子改坏。
        from app.services.novel_engine import count_words
        from app.config import platforms as pf
        import re as _re
        _lo, _hi = pf.chapter_words_of(platform)
        _n = count_words(humanized_text or "")
        # 结尾完整性最终闸门：覆盖所有策略（recursive 的候选级检查只管本策略）。
        # 原稿以句读收尾、改写稿却断在半句 —— 判为截尾。
        # 这条是被第10章"那里，还"溜到成品里逼出来的：字数只少了 16%，长度比例检查放行了。
        _orig_tail_ok = bool(_re.search(r"[。！？…\.\!\?\"'”’』」）\)】]$", (original_content or "").strip()))
        _hum_tail_ok = bool(_re.search(r"[。！？…\.\!\?\"'”’』」）\)】]$", (humanized_text or "").strip()))
        if _orig_tail_ok and not _hum_tail_ok:
            logger.warning(
                f"去AI化后结尾无句读、疑似截尾（末尾：…{(humanized_text or '').strip()[-20:]}），"
                f"回滚到原文: {chapter_id}"
            )
            result["rolled_back"] = True
            result["rollback_reason"] = "truncated_tail"
            chapter.humanize_strategy = result
            db.commit()
            broadcast_progress(str(chapter.project_id), {"type": "error", "agent": "humanizer", "chapter": chapter.chapter_number, "message": "去AI化后结尾被截断，已回滚"})
            return
        if not (_lo <= _n <= _hi):
            logger.warning(
                f"去AI化后字数跌出平台区间（{_n} 字，区间 {_lo}-{_hi}，平台={platform}），"
                f"回滚到原文: {chapter_id}"
            )
            result["rolled_back"] = True
            result["rollback_reason"] = "word_count_out_of_range"
            result["humanized_word_count"] = _n
            chapter.humanize_strategy = result
            db.commit()
            broadcast_progress(str(chapter.project_id), {"type": "error", "agent": "humanizer", "chapter": chapter.chapter_number, "message": f"去AI化后字数 {_n} 字不合规，已回滚"})
            return

        chapter.content = humanized_text
        chapter.humanize_strategy = result
        # v2.0: 统一使用统计评分v2（LLM自评权重过高导致虚高）
        if strategy == "recursive":
            chapter.ai_score_before = result.get("score_before", ai_score_before)
            chapter.ai_score_after = result.get("score_after")
            ai_score_before = chapter.ai_score_before
        elif strategy == "adversarial":
            chapter.ai_score_before = result.get("score_before", ai_score_before)
            chapter.ai_score_after = result.get("score_after")
            ai_score_before = chapter.ai_score_before
        else:
            chapter.ai_score_after = humanizer._statistical_ai_score_v2(humanized_text)

        # spec v1.3.0：自动回滚兜底——分数上升说明改写方向错误，恢复原文
        # recursive 策略跳过（内部 Best-of-N 已保证 score_after <= score_before，外部单次评分不稳定会误判）
        ai_score_after_val = chapter.ai_score_after
        if strategy != "recursive" and ai_score_after_val is not None and ai_score_after_val > ai_score_before:
            logger.warning(
                f"去AI化后分数上升，自动回滚: {chapter_id}, 策略={strategy}, "
                f"before={ai_score_before:.1f} -> after={ai_score_after_val:.1f}"
            )
            chapter.content = original_content  # 恢复原文
            chapter.ai_score_after = None  # 置空，表示未成功去AI化
            result["auto_rolled_back"] = True
            result["rollback_reason"] = f"分数上升 {ai_score_before:.1f}->{ai_score_after_val:.1f}"
            chapter.humanize_strategy = result
            db.commit()
            broadcast_progress(str(chapter.project_id), {
                "type": "error", "agent": "humanizer", "chapter": chapter.chapter_number,
                "message": f"去AI化后分数上升({ai_score_before:.1f}->{ai_score_after_val:.1f}), 已自动恢复原文"
            })
            return

        db.commit()
        broadcast_progress(str(chapter.project_id), {"type": "progress", "agent": "humanizer", "status": "done", "chapter": chapter.chapter_number, "message": f"去AI化完成: {ai_score_before:.1f} -> {chapter.ai_score_after:.1f}"})
        logger.info(f"去AI化完成: {chapter_id}, 策略={strategy}, AI分数: {ai_score_before:.1f} -> {chapter.ai_score_after:.1f}")
    except Exception as e:
        logger.error(f"去AI化失败: {e}", exc_info=True)
        broadcast_progress(str(chapter.project_id), {"type": "error", "agent": "humanizer", "message": f"去AI化失败: {e}"})
    finally:
        db.close()


@shared_task
def humanize_project(project_id: str, strategy: str = "default"):
    """全局去 AI 化：批量处理项目下所有章节。
    串行调用 humanize_chapter（避免 LLM 并发限流 + 反爬检测），
    实时推送整体进度（已完成/总章节数）。
    支持暂停（检查 _is_paused 标志）和断点续跑（跳过已有 ai_score_after 的章节）。
    """
    db = SessionLocal()
    try:
        # v1.5.0：跳过 Project 查询（数据库 schema 可能不匹配，且 humanize 不需要 Project 数据）
        # 直接查章节，有章节就说明项目存在
        chapters = db.query(Chapter).filter(Chapter.project_id == project_id).order_by(Chapter.chapter_number.asc()).all()
        total = len(chapters)
        if total == 0:
            logger.warning(f"项目无章节可去AI化: {project_id}")
            return
        # 2026-09-14 平台化：取项目目标平台并透传给每章；读不到则按默认平台处理
        try:
            _proj = db.query(Project).filter(Project.id == project_id).first()
            proj_platform = getattr(_proj, "platform", None) or "baidu"
        except Exception as _pe:
            logger.warning(f"读取项目平台失败，按默认平台处理: {_pe}")
            proj_platform = "baidu"
        logger.info(f"开始全局去AI化: 项目={project_id}, 章节={total}, 策略={strategy}, 平台={proj_platform}")
        broadcast_progress(project_id, {"type": "progress", "agent": "humanizer", "status": "batch_start", "total": total, "completed": 0, "message": f"开始批量去AI化({total}章)"})

        completed = 0
        failed = 0
        skipped = 0
        paused = False
        for ch in chapters:
            # 暂停检查：每章处理前检查 Redis 标志
            if _is_paused(project_id):
                logger.info(f"收到暂停信号，停止处理后续章节: 项目={project_id}, 已完成={completed}")
                paused = True
                break
            # 断点续跑：跳过已有 ai_score_after 的章节
            if ch.ai_score_after is not None:
                skipped += 1
                completed += 1
                logger.info(f"章节{ch.chapter_number}已处理过，跳过")
                continue
            try:
                humanize_chapter(str(ch.id), strategy, proj_platform)
                completed += 1
            except Exception as e:
                failed += 1
                logger.error(f"章节{ch.chapter_number}去AI化失败: {e}")
            broadcast_progress(project_id, {"type": "progress", "agent": "humanizer", "status": "batch_progress", "total": total, "completed": completed, "failed": failed, "skipped": skipped, "chapter": ch.chapter_number, "message": f"已完成 {completed}/{total}（失败 {failed}，跳过 {skipped}）"})

        if paused:
            broadcast_progress(project_id, {"type": "progress", "agent": "humanizer", "status": "paused", "total": total, "completed": completed, "failed": failed, "skipped": skipped, "message": f"已暂停：完成 {completed}/{total}（下次继续从第 {completed + 1} 章开始）"})
            logger.info(f"全局去AI化已暂停: 项目={project_id}, 完成={completed}, 跳过={skipped}")
        else:
            broadcast_progress(project_id, {"type": "progress", "agent": "humanizer", "status": "batch_done", "total": total, "completed": completed, "failed": failed, "skipped": skipped, "message": f"批量去AI化完成: 成功{completed}/{total}（跳过{skipped}），失败{failed}"})
            logger.info(f"全局去AI化完成: 项目={project_id}, 成功={completed}, 跳过={skipped}, 失败={failed}")
    except Exception as e:
        logger.error(f"全局去AI化失败: {e}", exc_info=True)
        broadcast_progress(project_id, {"type": "error", "agent": "humanizer", "message": f"全局去AI化失败: {e}"})
    finally:
        db.close()


def _is_paused(project_id: str) -> bool:
    """检查项目是否被暂停去AI化（Redis 标志）"""
    try:
        from app.config.celery_config import celery_app
        redis = celery_app.conf.broker_url.replace("redis://", "").split("/")[0]
        import redis as redis_lib
        r = redis_lib.Redis.from_url(f"redis://{redis}/1")
        return r.get(f"humanize:pause:{project_id}") == b"1"
    except Exception:
        return False


def set_pause_flag(project_id: str):
    """设置暂停标志"""
    try:
        from app.config.celery_config import celery_app
        broker = celery_app.conf.broker_url.replace("redis://", "").split("/")[0]
        import redis as redis_lib
        r = redis_lib.Redis.from_url(f"redis://{broker}/1")
        r.set(f"humanize:pause:{project_id}", "1")
    except Exception as e:
        logger.error(f"设置暂停标志失败: {e}")


def clear_pause_flag(project_id: str):
    """清除暂停标志"""
    try:
        from app.config.celery_config import celery_app
        broker = celery_app.conf.broker_url.replace("redis://", "").split("/")[0]
        import redis as redis_lib
        r = redis_lib.Redis.from_url(f"redis://{broker}/1")
        r.delete(f"humanize:pause:{project_id}")
    except Exception as e:
        logger.error(f"清除暂停标志失败: {e}")


def reset_humanize_progress(project_id: str):
    """停止时重置所有章节的去AI化进度（ai_score_before/after/original_content）"""
    db = SessionLocal()
    try:
        chapters = db.query(Chapter).filter(Chapter.project_id == project_id).all()
        for ch in chapters:
            ch.ai_score_before = None
            ch.ai_score_after = None
            if ch.original_content:
                ch.content = ch.original_content
                ch.original_content = ""
        db.commit()
        logger.info(f"已重置项目{project_id}的{len(chapters)}章去AI化进度")
    except Exception as e:
        logger.error(f"重置去AI化进度失败: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()