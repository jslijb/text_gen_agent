import logging
from celery import shared_task
from app.config.database import SessionLocal
from app.models.knowledge import KnowledgeEntry

logger = logging.getLogger(__name__)


@shared_task
def scrape_trending_novels():
    try:
        from playwright.sync_api import sync_playwright
        from app.services.publisher import Publisher
        publisher = Publisher()
        cookies = publisher.load_cookies()
        if not cookies:
            logger.error("Cookie不存在，无法抓取爆款数据")
            return

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            context.add_cookies(cookies)
            page = context.new_page()
            page.goto("https://zuojia.baidu.com", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)

            trending_items = page.query_selector_all(".trending-item, .hot-item, [class*='rank']")
            features = []
            for item in trending_items[:20]:
                try:
                    title_el = item.query_selector("h3, .title, [class*='title']")
                    title = title_el.inner_text() if title_el else ""
                    desc_el = item.query_selector("p, .desc, [class*='desc']")
                    desc = desc_el.inner_text() if desc_el else ""
                    if title or desc:
                        features.append({"title": title, "description": desc})
                except Exception:
                    continue

            browser.close()

        db = SessionLocal()
        try:
            for feat in features:
                entry = KnowledgeEntry(
                    topic="scraped",
                    word_count_range="10000-30000",
                    opening_pattern=feat.get("description", "")[:200],
                    emotion_type="thrill",
                    ending_type="open",
                    source=f"自动抓取-{__import__('datetime').datetime.utcnow().strftime('%Y-%m-%d')}",
                    content=feat.get("title", "") + " " + feat.get("description", ""),
                )
                db.add(entry)
            db.commit()

            from app.services.knowledge_base import KnowledgeBaseManager
            kb = KnowledgeBaseManager()
            entries = db.query(KnowledgeEntry).filter(KnowledgeEntry.vectorized == False).all()
            for entry in entries:
                if kb.add_entry(entry):
                    entry.vectorized = True
            db.commit()
            logger.info(f"爆款抓取完成，新增{len(features)}条")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"爆款抓取失败: {e}")


@shared_task
def cleanup_knowledge_base():
    db = SessionLocal()
    try:
        from app.services.knowledge_base import KnowledgeBaseManager
        kb = KnowledgeBaseManager()
        deleted = kb.cleanup_expired(db)
        outdated = kb.review_and_dedup(db)
        logger.info(f"知识库清理完成，删除过期{deleted}条，标记过时{len(outdated)}条")
        return {"deleted": deleted, "outdated": outdated}
    except Exception as e:
        logger.error(f"知识库清理失败: {e}")
        return {"error": str(e)}
    finally:
        db.close()