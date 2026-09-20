import urllib.request
import json
import time

def search_github(query, per_page=30):
    url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page={per_page}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("items", [])
    except Exception as e:
        print(f"Error searching '{query}': {e}")
        return []

def get_repo_info(full_name):
    url = f"https://api.github.com/repos/{full_name}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"Error getting repo '{full_name}': {e}")
        return None

queries = [
    "humanize+ai+text",
    "ai+text+humanizer",
    "dehumanize+ai+text",
    "ai+detector+bypass",
    "text+humanization",
    "ai+writing+remover",
    "stop+slop+ai",
    "humanize-text+ai",
]

all_repos = {}
seen = set()

for q in queries:
    print(f"\n=== Searching: {q} ===")
    repos = search_github(q)
    for r in repos:
        name = r["full_name"]
        if name not in seen:
            seen.add(name)
            all_repos[name] = r
            print(f"  {name} | ⭐{r['stargazers_count']} | {r.get('language','?')} | Updated: {r.get('pushed_at','?')[:10]} | {r.get('description','')[:80]}")
    time.sleep(2)

specific_repos = [
    "Humanize-Text",
    "Stop-Slop",
    "TextHumanize",
    "Humanizer",
]

print("\n\n=== Searching specific projects ===")
for sp in specific_repos:
    results = search_github(sp, per_page=5)
    for r in results:
        name = r["full_name"]
        if name not in seen:
            seen.add(name)
            all_repos[name] = r
            print(f"  {name} | ⭐{r['stargazers_count']} | {r.get('language','?')} | Updated: {r.get('pushed_at','?')[:10]} | {r.get('description','')[:80]}")
    time.sleep(2)

print("\n\n=== Detailed Top Repos ===")
sorted_repos = sorted(all_repos.values(), key=lambda x: x["stargazers_count"], reverse=True)
for r in sorted_repos[:25]:
    print(f"\n--- {r['full_name']} ---")
    print(f"  URL: {r['html_url']}")
    print(f"  Stars: {r['stargazers_count']}")
    print(f"  Forks: {r['forks_count']}")
    print(f"  Language: {r.get('language', 'N/A')}")
    print(f"  Created: {r.get('created_at', 'N/A')[:10]}")
    print(f"  Updated: {r.get('pushed_at', 'N/A')[:10]}")
    print(f"  Archived: {r.get('archived', False)}")
    print(f"  Description: {r.get('description', 'N/A')}")
    print(f"  Topics: {r.get('topics', [])}")
    print(f"  License: {r.get('license', {}).get('name', 'N/A') if r.get('license') else 'N/A'}")