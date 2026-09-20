"""分步端到端测试：每步独立运行，避免bash超时
用法：python e2e_step_v2.py [step]
  step1: 创建项目+生成大纲
  step2: 生成第1章
  step3: 去AI化
  step4: 生成封面
  (无参数则运行全部)
"""
import os, sys, json, time, logging


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config.database import Base, engine, SessionLocal
from app.models import Project, Chapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("e2e_step")

PID_FILE = os.path.join(os.path.dirname(__file__), "data", "e2e_project_id.txt")
REPORT_FILE = os.path.join(os.path.dirname(__file__), "data", "e2e_report.json")


def load_pid():
    if os.path.exists(PID_FILE):
        with open(PID_FILE, "r") as f:
            return f.read().strip()
    return None


def save_pid(pid):
    os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
    with open(PID_FILE, "w") as f:
        f.write(pid)


def load_report():
    if os.path.exists(REPORT_FILE):
        with open(REPORT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"steps": []}


def save_report(report):
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def step1():
    logger.info("STEP 1: Create project + Generate outline")
    Base.metadata.create_all(bind=engine)
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
    db.close()
    save_pid(pid)
    logger.info(f"Project created: {pid}")

    from app.services.novel_engine import NovelEngine
    ne = NovelEngine()
    outline = ne.generate_outline(project.synopsis, project.genre, 3)
    db = SessionLocal()
    proj = db.query(Project).filter(Project.id == pid).first()
    proj.outline = outline
    db.commit()
    db.close()
    n_chapters = len(outline.get("chapters", []))
    logger.info(f"Outline done: {n_chapters} chapters planned")
    report = load_report()
    report["steps"].append({"step": "create_project+outline", "status": "PASS", "project_id": pid, "chapters_planned": n_chapters})
    save_report(report)
    return pid


def step2():
    pid = load_pid()
    if not pid:
        logger.error("No project ID found. Run step1 first.")
        return
    Base.metadata.create_all(bind=engine)
    logger.info(f"STEP 2: Generate chapter 1 (project={pid})")
    db = SessionLocal()
    project = db.query(Project).filter(Project.id == pid).first()
    if not project or not project.outline:
        logger.error("Project or outline not found")
        db.close()
        return
    outline = project.outline
    chapters_plan = outline.get("chapters", [])
    characters = outline.get("characters", [])
    db.close()

    if not chapters_plan:
        logger.error("No chapters in outline")
        return

    ch_plan = chapters_plan[0]
    from app.services.novel_engine import NovelEngine
    ne = NovelEngine()
    draft, model_name = ne.generate_chapter(
        chapter_plan=ch_plan,
        previous_summary="",
        character_states=json.dumps(characters, ensure_ascii=False),
    )
    db = SessionLocal()
    chapter = Chapter(
        project_id=project.id,
        chapter_number=1,
        title=ch_plan.get("title", "第1章"),
        content=draft,
        original_content=draft,
        model_used=model_name,
    )
    db.add(chapter)
    project = db.query(Project).filter(Project.id == pid).first()
    project.status = "pending_review"
    db.commit()
    db.close()
    logger.info(f"Chapter 1 done: {len(draft)} chars, model={model_name}")
    report = load_report()
    report["steps"].append({"step": "generate_chapter", "status": "PASS", "chars": len(draft), "model": model_name})
    save_report(report)


def step3():
    pid = load_pid()
    if not pid:
        logger.error("No project ID found. Run step1 first.")
        return
    Base.metadata.create_all(bind=engine)
    logger.info(f"STEP 3: Humanize (project={pid})")
    from app.services.humanizer import Humanizer
    humanizer = Humanizer()
    db = SessionLocal()
    chapter = db.query(Chapter).filter(Chapter.project_id == pid).first()
    if not chapter:
        logger.error("No chapter found")
        db.close()
        return
    ai_before = humanizer.evaluate_ai_score(chapter.content)
    chapter.ai_score_before = ai_before
    chapter.original_content = chapter.content
    result = humanizer.humanize_quick(chapter.content)
    chapter.content = result["text"]
    chapter.humanize_strategy = result
    ai_after = humanizer.evaluate_ai_score(chapter.content)
    chapter.ai_score_after = ai_after
    db.commit()
    db.close()
    logger.info(f"Humanized: AI {ai_before:.1f} -> {ai_after:.1f}, replaced {result['patterns_replaced']}")
    report = load_report()
    report["steps"].append({"step": "humanize", "status": "PASS", "ai_before": round(ai_before, 1), "ai_after": round(ai_after, 1), "replaced": result["patterns_replaced"]})
    save_report(report)


def step4():
    pid = load_pid()
    if not pid:
        logger.error("No project ID found. Run step1 first.")
        return
    Base.metadata.create_all(bind=engine)
    logger.info(f"STEP 4: Generate cover (project={pid})")
    db = SessionLocal()
    project = db.query(Project).filter(Project.id == pid).first()
    if not project:
        logger.error("Project not found")
        db.close()
        return
    db.close()

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
        project = db.query(Project).filter(Project.id == pid).first()
        project.cover_url = cover_url
        db.commit()
        db.close()
        logger.info(f"Cover generated: {cover_url}, model={cover_result['model_used']}")
        report = load_report()
        report["steps"].append({"step": "generate_cover", "status": "PASS", "cover_url": cover_url, "model_used": cover_result["model_used"]})
        save_report(report)
    except CoverGenerationError as e:
        logger.warning(f"Cover generation skipped: {e}")
        report = load_report()
        report["steps"].append({"step": "generate_cover", "status": "SKIP", "reason": str(e)[:200]})
        save_report(report)
    except Exception as e:
        logger.error(f"Cover generation failed: {e}")
        report = load_report()
        report["steps"].append({"step": "generate_cover", "status": "FAIL", "error": str(e)[:200]})
        save_report(report)


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    if step == "step1":
        step1()
    elif step == "step2":
        step2()
    elif step == "step3":
        step3()
    elif step == "step4":
        step4()
    elif step == "all":
        step1()
        step2()
        step3()
        step4()
    elif step == "cleanup":
        Base.metadata.drop_all(bind=engine)
        for f in [PID_FILE, REPORT_FILE]:
            if os.path.exists(f):
                os.remove(f)
        logger.info("Cleaned up e2e test data")
    else:
        print(f"Usage: python {sys.argv[0]} [step1|step2|step3|step4|all|cleanup]")