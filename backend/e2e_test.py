"""
端到端测试脚本：选题 → 生成10章短篇小说 → 去AI味 → 生成封面
不依赖HTTP服务，直接调用后端服务层
"""
import os
import sys
import json
import time
import logging

os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'e2e_test.db').replace(os.sep, '/')}"
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config.database import Base, engine, SessionLocal
from app.models import Project, Chapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("e2e_test")


def step1_create_project():
    """步骤1：选题 - 创建小说项目"""
    logger.info("=" * 60)
    logger.info("步骤1：选题 - 创建小说项目")
    logger.info("=" * 60)

    db = SessionLocal()
    try:
        project = Project(
            name="午夜书店",
            synopsis="一个深夜书店的老板发现每到午夜十二点书架上的书会自己翻页他开始记录这些自读的书发现它们讲述的竟然是顾客们尚未发生的命运当他试图改变一位常客的命运时整个书店开始崩塌原来书店本身就是一本活着的书",
            gender="无性向",
            genre="恐怖推理",
            target_word_count=20000,
            initial_chapters=3,
            daily_chapters=2,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        logger.info(f"项目创建成功: id={project.id}, name={project.name}")
        return project
    finally:
        db.close()


def step2_generate_novel(project):
    """步骤2：生成10章短篇小说"""
    logger.info("=" * 60)
    logger.info("步骤2：生成10章短篇小说")
    logger.info("=" * 60)

    from app.services.novel_engine import NovelEngine
    engine = NovelEngine()

    start_time = time.time()
    result = engine.generate_full_novel(
        synopsis=project.synopsis,
        genre=project.genre,
        target_chapters=project.initial_chapters,
    )
    elapsed = time.time() - start_time

    logger.info(f"小说生成完成，耗时 {elapsed:.1f}秒")

    db = SessionLocal()
    try:
        project.status = "pending_review"
        outline = result.get("outline", {})
        project.outline = outline
        if "characters" in outline:
            project.characters = outline["characters"]

        chapter_count = 0
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
            chapter_count += 1

        db.commit()
        logger.info(f"已保存 {chapter_count} 章到数据库")

        total_chars = sum(len(ch.get("content", "")) for ch in result.get("chapters", []))
        logger.info(f"总字数: {total_chars}")
    finally:
        db.close()

    return result


def step3_humanize(project):
    """步骤3：去AI味"""
    logger.info("=" * 60)
    logger.info("步骤3：去AI味")
    logger.info("=" * 60)

    from app.services.humanizer import Humanizer
    humanizer = Humanizer()

    db = SessionLocal()
    try:
        chapters = db.query(Chapter).filter(Chapter.project_id == project.id).order_by(Chapter.chapter_number).all()
        total_before = 0.0
        total_after = 0.0
        count = 0

        for chapter in chapters:
            ai_score_before = humanizer.evaluate_ai_score(chapter.content)
            chapter.ai_score_before = ai_score_before
            chapter.original_content = chapter.content
            total_before += ai_score_before

            result = humanizer.humanize_quick(chapter.content)
            chapter.content = result["text"]
            chapter.humanize_strategy = result

            ai_score_after = humanizer.evaluate_ai_score(chapter.content)
            chapter.ai_score_after = ai_score_after
            total_after += ai_score_after
            count += 1

            logger.info(f"  第{chapter.chapter_number}章: AI分数 {ai_score_before:.1f} → {ai_score_after:.1f} (替换{result['patterns_replaced']}处)")

        db.commit()

        if count > 0:
            avg_before = total_before / count
            avg_after = total_after / count
            reduction = ((avg_before - avg_after) / avg_before * 100) if avg_before > 0 else 0
            logger.info(f"去AI化统计: 平均AI分数 {avg_before:.1f} → {avg_after:.1f}, 降低 {reduction:.1f}%")
    finally:
        db.close()


def step4_generate_cover(project):
    """步骤4：生成封面"""
    logger.info("=" * 60)
    logger.info("步骤4：生成封面")
    logger.info("=" * 60)

    from app.services.cover_generator import CoverGenerator
    cover_gen = CoverGenerator()

    cover_url = cover_gen.generate_cover_with_api(
        title=project.name,
        genre=project.genre,
        synopsis=project.synopsis,
    )

    if cover_url:
        db = SessionLocal()
        try:
            project.cover_url = cover_url
            db.commit()
            logger.info(f"封面生成成功: {cover_url}")
        finally:
            db.close()
    else:
        logger.warning("封面生成失败（API可能不可用），尝试文字封面...")
        cover_url = cover_gen._generate_text_cover(
            title=project.name,
            genre=project.genre,
            synopsis=project.synopsis,
        )
        if cover_url:
            db = SessionLocal()
            try:
                project.cover_url = cover_url
                db.commit()
                logger.info(f"文字封面生成成功: {cover_url}")
            finally:
                db.close()
        else:
            logger.error("封面生成完全失败")


def step5_verify(project):
    """步骤5：验证结果"""
    logger.info("=" * 60)
    logger.info("步骤5：验证结果")
    logger.info("=" * 60)

    db = SessionLocal()
    try:
        chapters = db.query(Chapter).filter(Chapter.project_id == project.id).order_by(Chapter.chapter_number).all()

        logger.info(f"项目: {project.name}")
        logger.info(f"状态: {project.status}")
        logger.info(f"章节数: {len(chapters)}")
        logger.info(f"封面: {project.cover_url or '无'}")

        total_chars = 0
        for ch in chapters:
            chars = len(ch.content)
            total_chars += chars
            ai_before = f"{ch.ai_score_before:.0f}" if ch.ai_score_before else "N/A"
            ai_after = f"{ch.ai_score_after:.0f}" if ch.ai_score_after else "N/A"
            logger.info(f"  第{ch.chapter_number}章 [{ch.title}]: {chars}字, AI分数 {ai_before}→{ai_after}")

        logger.info(f"总字数: {total_chars}")
        logger.info(f"目标字数: {project.target_word_count}")

        passed = True
        if len(chapters) < 10:
            logger.error(f"❌ 章节数不足: {len(chapters)}/10")
            passed = False
        else:
            logger.info(f"✅ 章节数达标: {len(chapters)}/10")

        if total_chars >= 10000:
            logger.info(f"✅ 字数达标: {total_chars}/10000+")
        else:
            logger.warning(f"⚠️ 字数偏少: {total_chars}/10000+")

        if project.cover_url:
            logger.info(f"✅ 封面已生成")
        else:
            logger.warning(f"⚠️ 封面未生成")

        humanized_count = sum(1 for ch in chapters if ch.ai_score_after is not None)
        if humanized_count > 0:
            logger.info(f"✅ 去AI化已完成: {humanized_count}/{len(chapters)}章")
        else:
            logger.warning(f"⚠️ 去AI化未执行")

        return passed
    finally:
        db.close()


def main():
    Base.metadata.create_all(bind=engine)

    try:
        project = step1_create_project()
        result = step2_generate_novel(project)
        step3_humanize(project)
        step4_generate_cover(project)
        passed = step5_verify(project)

        logger.info("=" * 60)
        if passed:
            logger.info("端到端测试: ✅ 通过")
        else:
            logger.info("端到端测试: ⚠️ 部分通过（请检查上方日志）")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"端到端测试失败: {e}", exc_info=True)
    finally:
        Base.metadata.drop_all(bind=engine)


if __name__ == "__main__":
    main()