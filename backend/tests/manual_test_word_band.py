"""定向验证字数兜底：对现有偏短章节调用 _enforce_word_limit，看能否补进 [1800,2200]。

不重新生成整章，只跑兜底环节，几十秒出结果。
"""
import sys
import uuid

sys.path.insert(0, "/app")

from app.config.database import SessionLocal
from app.models.chapter import Chapter
from app.services.novel_engine import NovelEngine, count_words

PID = "8ded393c-2fd6-4530-bfc2-ffe5a2352f7e"

db = SessionLocal()
try:
    chapters = (
        db.query(Chapter)
        .filter(Chapter.project_id == uuid.UUID(PID))
        .order_by(Chapter.chapter_number)
        .all()
    )
    engine = NovelEngine("fanqie")
    for c in chapters:
        before = count_words(c.content or "")
        if before >= 1800:
            print(f"ch{c.chapter_number}: {before} 字，已达标，跳过", flush=True)
            continue
        print(f"ch{c.chapter_number}: {before} 字 → 触发补写…", flush=True)
        fixed = engine._enforce_word_limit(c.content, c.chapter_number)
        after = count_words(fixed)
        ok = "OK" if 1800 <= after <= 2200 else "仍不合规"
        print(f"ch{c.chapter_number}: {before} → {after} 字  [{ok}]", flush=True)
finally:
    db.close()
