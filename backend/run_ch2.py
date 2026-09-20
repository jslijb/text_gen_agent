from app.config.database import SessionLocal
from app.models import Chapter
from app.services.humanizer import Humanizer

db = SessionLocal()
ch = db.query(Chapter).filter(
    Chapter.chapter_number == 2,
    Chapter.project_id == "ae44d07d-b2f1-460d-aa1e-340ac70b03a6"
).first()
print(f"Ch2: {ch.title}, chars={len(ch.content)}")
db.close()

h = Humanizer()
result = h.humanize_quick(ch.content)
score_before = h._statistical_ai_score_v2(ch.content)
score_after = h._statistical_ai_score_v2(result["text"])
print(f"Quick: patterns_replaced={result['patterns_replaced']}")
print(f"Score: {score_before} -> {score_after}")

db = SessionLocal()
ch = db.query(Chapter).filter(
    Chapter.chapter_number == 2,
    Chapter.project_id == "ae44d07d-b2f1-460d-aa1e-340ac70b03a6"
).first()
ch.original_content = ch.content
ch.content = result["text"]
ch.ai_score_before = score_before
ch.ai_score_after = score_after
ch.humanize_strategy = result
db.commit()
print(f"Saved: before={ch.ai_score_before}, after={ch.ai_score_after}")
db.close()