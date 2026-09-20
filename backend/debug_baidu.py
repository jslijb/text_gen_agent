"""调试百度热搜小说榜真实 HTML 结构"""
import requests
import random

UA = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]

headers = {
    "User-Agent": random.choice(UA),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

print("=== 抓取百度热搜小说榜 ===")
resp = requests.get("https://top.baidu.com/board?tab=novel", headers=headers, timeout=15)
print(f"状态码: {resp.status_code}")
print(f"内容长度: {len(resp.text)}")
print(f"编码: {resp.encoding}")
print(f"apparent_encoding: {resp.apparent_encoding}")

# 修正编码
if resp.encoding.lower() != "utf-8":
    resp.encoding = resp.apparent_encoding or "utf-8"

html = resp.text
print(f"\n=== HTML 前 1500 字符 ===")
print(html[:1500])

# 搜索关键标记
print(f"\n=== 关键标记检查 ===")
markers = ["board", "item", "c-single-text-clip", "title", "author", "type", "hot", "desc",
           "热搜", "小说", "rank", "category", "text-clip", "content"]
for m in markers:
    count = html.lower().count(m.lower())
    if count > 0:
        # 找第一个出现位置
        idx = html.lower().find(m.lower())
        snippet = html[max(0, idx-30):idx+80].replace("\n", " ")
        print(f"  {m}: {count} 次, 首次上下文: ...{snippet}...")

# 保存完整 HTML 供分析
with open("debug_baidu_hot.html", "w", encoding="utf-8") as f:
    f.write(html)
print(f"\n完整 HTML 已保存到 debug_baidu_hot.html")
