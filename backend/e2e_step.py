import os, sys, json
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'e2e_test.db').replace(os.sep, '/')}"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config.database import Base, engine, SessionLocal
from app.models import Project, Chapter

Base.metadata.create_all(bind=engine)

db = SessionLocal()
project = Project(
    name="午夜书店",
    synopsis="深夜书店老板发现每到午夜书架上的书会自己翻页记录这些自读的书发现它们讲述的是顾客们尚未发生的命运当他试图改变一位常客的命运时整个书店开始崩塌原来书店本身就是一本活着的书",
    gender="无性向", genre="恐怖推理", target_word_count=20000, initial_chapters=3, daily_chapters=2,
)
db.add(project)
db.commit()
db.refresh(project)
pid = str(project.id)
db.close()

print(f"PROJECT_ID={pid}")

from app.services.novel_engine import NovelEngine
ne = NovelEngine()
print("Generating outline...")
outline = ne.generate_outline(project.synopsis, project.genre, 3)
print(f"Outline done, {len(outline.get('chapters', []))} chapters planned")

db = SessionLocal()
project.outline = outline
db.commit()
db.close()

chapters_plan = outline.get("chapters", [])
characters = outline.get("characters", [])

if chapters_plan:
    ch_plan = chapters_plan[0]
    print(f"Generating chapter 1: {ch_plan.get('title', '')}...")
    draft, model_name = ne.generate_chapter(
        chapter_plan=ch_plan,
        previous_summary="",
        character_states=json.dumps(characters, ensure_ascii=False),
    )
    print(f"Chapter 1 done: {len(draft)} chars, model={model_name}")

    db = SessionLocal()
    chapter = Chapter(
        project_id=project.id, chapter_number=1,
        title=ch_plan.get("title", "第1章"),
        content=draft, original_content=draft, model_used=model_name,
    )
    db.add(chapter)
    project.status = "pending_review"
    db.commit()
    db.close()

    from app.services.humanizer import Humanizer
    humanizer = Humanizer()
    db = SessionLocal()
    chapter = db.query(Chapter).filter(Chapter.project_id == project.id).first()
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
    print(f"Humanized: AI {ai_before:.1f} -> {ai_after:.1f}, replaced {result['patterns_replaced']}")

    from app.services.cover_generator import CoverGenerator
    cg = CoverGenerator()
    cover_url = cg.generate_cover_with_api(title=project.name, genre=project.genre, synopsis=project.synopsis)
    if not cover_url:
        cover_url = cg._generate_text_cover(project.name, project.genre, project.synopsis)
    if cover_url:
        db = SessionLocal()
        project.cover_url = cover_url
        db.commit()
        db.close()
    print(f"Cover: {cover_url or 'FAILED'}")

print("=" * 60)
print("E2E TEST COMPLETE")
print(f"Project: {project.name}")
print(f"Outline chapters: {len(chapters_plan)}")
print(f"Chapter 1 chars: {len(draft) if chapters_plan else 0}")
print(f"Cover: {cover_url if chapters_plan else 'N/A'}")
print("=" * 60)

Base.metadata.drop_all(bind=engine)