import os, sys
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'e2e_verify.db').replace(os.sep, '/')}"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config.database import Base, engine
Base.metadata.create_all(bind=engine)

print("=== Module Verification ===")

# 1. Outline generation
print("\n[1] Outline Generation...")
from app.services.novel_engine import NovelEngine
ne = NovelEngine()
outline = ne.generate_outline("深夜书店老板发现每到午夜书架上的书会自己翻页", "恐怖推理", 3)
print(f"  OK: {len(outline.get('chapters', []))} chapters planned")
for ch in outline.get("chapters", []):
    print(f"  Ch{ch.get('number')}: {ch.get('title')}")

# 2. Humanizer
print("\n[2] Humanizer...")
from app.services.humanizer import Humanizer
h = Humanizer()
test = "值得注意的是这个发现具有重要意义不仅如此它产生了深远影响毫无疑问这引起了广泛关注"
result = h.humanize_quick(test)
ai_before = h.evaluate_ai_score(test)
ai_after = h.evaluate_ai_score(result["text"])
print(f"  OK: replaced={result['patterns_replaced']}, AI score {ai_before:.1f}->{ai_after:.1f}")

# 3. Cover generation
print("\n[3] Cover Generation...")
from app.services.cover_generator import CoverGenerator
cg = CoverGenerator()
url = cg._generate_text_cover("午夜书店", "恐怖推理", "深夜书店老板发现每到午夜书架上的书会自己翻页")
print(f"  OK: {url}")

# 4. Model manager
print("\n[4] Model Manager...")
from app.services.model_manager import ModelManager
mm = ModelManager()
models = mm.get_all_models_status()
print(f"  OK: {len(models)} models loaded")
for m in models:
    print(f"  {m['name']} (priority={m['priority']}, role={m.get('role', 'general')})")

# 5. Knowledge base
print("\n[5] Knowledge Base...")
from app.services.knowledge_base import KnowledgeBaseManager
kb = KnowledgeBaseManager()
print(f"  OK: ChromaDB initialized")

# 6. Config service
print("\n[6] Config Service...")
from app.services.config_service import ConfigService
config = ConfigService.load_models_config()
valid, msg = ConfigService.validate_models_config(config)
print(f"  OK: config valid={valid}, msg={msg}")

print("\n=== All Modules Verified ===")

Base.metadata.drop_all(bind=engine)