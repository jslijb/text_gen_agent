"""简化版端到端测试：核心流水线（创建项目→大纲→写1章→去AI化→封面），减少LLM调用"""
import os, sys, json, time, logging

os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'e2e_test.db').replace(os.sep, '/')}"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config.database import Base, engine, SessionLocal
from app.models import Project, Chapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("e2e_quick")

def main():
    Base.metadata.create_all(bind=engine)
    results = {"steps": [], "started_at": time.strftime("%Y-%m-%d %H:%M:%S")}

    # Step 1: Create project
    logger.info("STEP 1: Create project")
    db = SessionLocal()
    project = Project(
        name="午夜书店",
        synopsis="深夜书店老板发现每到午夜书架上的书会自己翻页记录这些自读的书发现它们讲述的是顾客们尚未发生的命运当他试图改变一位常客的命运时整个书店开始崩塌原来书店本身就是一本活着的书",
        gender="无性向",
        genre="恐怖推理",
        target_word_count=20000,
        initial_chapters=3,
        daily_chapters=2,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    pid = str(project.id)
    logger.info(f"Project created: {pid}")
    results["steps"].append({"step": "create_project", "status": "PASS", "project_id": pid})
    db.close()

    # Step 2: Generate outline
    logger.info("STEP 2: Generate outline")
    outline = None
    try:
        from app.services.novel_engine import NovelEngine
        novel_engine = NovelEngine()
        outline = novel_engine.generate_outline(project.synopsis, project.genre, 3)
        db = SessionLocal()
        project.outline = outline
        db.commit()
        db.close()
        logger.info(f"Outline generated, chapters planned: {len(outline.get('chapters', []))}")
        results["steps"].append({"step": "generate_outline", "status": "PASS", "chapters_planned": len(outline.get('chapters', []))})
    except Exception as e:
        logger.error(f"Outline generation failed: {e}")
        results["steps"].append({"step": "generate_outline", "status": "FAIL", "error": str(e)[:200]})

    # Step 3: Generate 1 chapter (skip review to save time)
    logger.info("STEP 3: Generate chapter 1")
    try:
        chapters_plan = outline.get("chapters", []) if outline else []
        characters = outline.get("characters", []) if outline else []
        if chapters_plan:
            ch_plan = chapters_plan[0]
            draft, model_name = novel_engine.generate_chapter(
                chapter_plan=ch_plan,
                previous_summary="",
                character_states=json.dumps(characters, ensure_ascii=False),
            )
            final_content = draft
            db = SessionLocal()
            chapter = Chapter(
                project_id=project.id,
                chapter_number=1,
                title=ch_plan.get("title", "第1章"),
                content=final_content,
                original_content=draft,
                model_used=model_name,
            )
            db.add(chapter)
            project.status = "pending_review"
            db.commit()
            db.close()
            logger.info(f"Chapter 1 generated: {len(final_content)} chars")
            results["steps"].append({"step": "generate_chapter", "status": "PASS", "chars": len(final_content)})
        else:
            results["steps"].append({"step": "generate_chapter", "status": "SKIP", "reason": "no outline"})
    except Exception as e:
        logger.error(f"Chapter generation failed: {e}")
        results["steps"].append({"step": "generate_chapter", "status": "FAIL", "error": str(e)[:200]})

    # Step 4: Humanize (quick strategy, no LLM)
    logger.info("STEP 4: Humanize (quick)")
    try:
        from app.services.humanizer import Humanizer
        humanizer = Humanizer()
        db = SessionLocal()
        chapter = db.query(Chapter).filter(Chapter.project_id == project.id).first()
        if chapter:
            ai_before = humanizer.evaluate_ai_score(chapter.content)
            chapter.ai_score_before = ai_before
            chapter.original_content = chapter.content
            result = humanizer.humanize_quick(chapter.content)
            chapter.content = result["text"]
            chapter.humanize_strategy = result
            ai_after = humanizer.evaluate_ai_score(chapter.content)
            chapter.ai_score_after = ai_after
            db.commit()
            logger.info(f"Humanized: AI score {ai_before:.1f} -> {ai_after:.1f}, replaced {result['patterns_replaced']}")
            results["steps"].append({"step": "humanize", "status": "PASS", "ai_before": round(ai_before, 1), "ai_after": round(ai_after, 1), "replaced": result["patterns_replaced"]})
        else:
            results["steps"].append({"step": "humanize", "status": "SKIP", "reason": "no chapter"})
        db.close()
    except Exception as e:
        logger.error(f"Humanize failed: {e}")
        results["steps"].append({"step": "humanize", "status": "FAIL", "error": str(e)[:200]})

    # Step 5: Generate cover (v1.4.0: Agnes image API + Pillow overlay)
    logger.info("STEP 5: Generate cover")
    try:
        from app.services.cover_service import generate_cover, CoverGenerationError
        cover_result = generate_cover(
            project_id=pid,
            gender=project.gender,
            genre=project.genre,
            name=project.name,
            synopsis=project.synopsis,
        )
        cover_url = cover_result["cover_url"]
        db = SessionLocal()
        project.cover_url = cover_url
        db.commit()
        db.close()
        logger.info(f"Cover generated: {cover_url}, model={cover_result['model_used']}")
        results["steps"].append({"step": "generate_cover", "status": "PASS", "cover_url": cover_url, "model_used": cover_result["model_used"]})
    except CoverGenerationError as e:
        logger.warning(f"Cover generation failed (expected if AGNES_KEY not set): {e}")
        results["steps"].append({"step": "generate_cover", "status": "SKIP", "reason": str(e)[:200]})
    except Exception as e:
        logger.error(f"Cover generation failed: {e}")
        results["steps"].append({"step": "generate_cover", "status": "FAIL", "error": str(e)[:200]})

    # Summary
    results["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    logger.info("=" * 60)
    logger.info("E2E TEST SUMMARY")
    pass_count = sum(1 for s in results["steps"] if s["status"] == "PASS")
    skip_count = sum(1 for s in results["steps"] if s["status"] == "SKIP")
    fail_count = sum(1 for s in results["steps"] if s["status"] == "FAIL")
    total = len(results["steps"])
    for s in results["steps"]:
        logger.info(f"  {s['step']}: {s['status']}")
    logger.info(f"Result: {pass_count}/{total} passed, {skip_count} skipped, {fail_count} failed")
    logger.info("=" * 60)

    report_path = os.path.join(os.path.dirname(__file__), "data", "e2e_report.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info(f"Report saved to {report_path}")

    Base.metadata.drop_all(bind=engine)


if __name__ == "__main__":
    main()
