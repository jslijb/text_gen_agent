import asyncio
from app.config.database import SessionLocal
from app.models import Chapter
from app.services.humanizer import Humanizer

db = SessionLocal()
ch = db.query(Chapter).filter(
    Chapter.chapter_number == 1,
    Chapter.project_id == "ae44d07d-b2f1-460d-aa1e-340ac70b03a6"
).first()
print(f"Before: AI={ch.ai_score_before}, chars={len(ch.original_content)}")
db.close()

h = Humanizer()
result = asyncio.run(h.humanize_adversarial(ch.original_content, max_rounds=3))

print(f"After: score={result['score_after']}, rounds={result['rounds_completed']}")
for h_item in result.get("history", []):
    print(f"  Round {h_item['round']}: {h_item['score_before']:.1f} -> {h_item['score_after']:.1f}")
print(f"Chars: {len(result['text'])}")
print(f"Preview: {result['text'][:400]}")

db = SessionLocal()
ch = db.query(Chapter).filter(
    Chapter.chapter_number == 1,
    Chapter.project_id == "ae44d07d-b2f1-460d-aa1e-340ac70b03a6"
).first()
ch.content = result["text"]
ch.ai_score_after = result["score_after"]
ch.humanize_strategy = result
db.commit()
db.close()
print("Saved to database.")