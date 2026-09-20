from app.services.model_manager import ModelManager
from openai import OpenAI

m = ModelManager()
seen = set()
for model in m._models:
    if model.name in seen:
        continue
    seen.add(model.name)
    try:
        client = OpenAI(api_key=model.api_key, base_url=model.base_url)
        r = client.chat.completions.create(model=model.name, messages=[{"role":"user","content":"hi"}], max_tokens=5)
        print(f"{model.name}: OK, tokens={r.usage.total_tokens}")
    except Exception as e:
        err = str(e)[:100]
        print(f"{model.name}: FAIL, {err}")