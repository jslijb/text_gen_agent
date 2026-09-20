# -*- coding: utf-8 -*-
"""番茄平台适配端到端验证。

设计说明：结果不直接 print（会被 Windows 控制台按 GBK 解码成乱码），
而是累积后以 UTF-8 写入容器内文件，再拷回宿主机查看。
源码 UTF-8，中文字面量直接书写（docker cp 为字节级传输，不经 shell）。
"""
import json
import re
import urllib.request
import urllib.error
import io

BASE = "http://localhost:8000/api/v1"
OUT_PATH = "/tmp/_fq_e2e_out.txt"

NAN = "男频"
NV = "女频"
NANXING = "男性向"
NVXING = "女性向"
WUXING = "无性向"
FANTASY = "玄幻仙侠"
SUSPENSE = "悬疑惊悚"
DUSHI = "都市日常"
LABEL_BAIDU = "百度作家平台"
LABEL_FQ = "番茄小说"
PREFIX = "故事："
SYNOPSIS = "测试用梗概，至少十个字符。" * 2

L = []
results = []


def log(s=""):
    L.append(s)


def req(method, path, body=None, timeout=120):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    if data:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def check(label, ok, detail=""):
    results.append((label, bool(ok), detail))
    log("  [%s] %s%s" % ("PASS" if ok else "FAIL", label, ("   <- " + str(detail)) if detail else ""))


def count_chars(t):
    return len(re.sub(r"[^\w\u4e00-\u9fff]", "", t))


def mk(name, platform, gender, genre):
    return {
        "name": name, "synopsis": SYNOPSIS, "platform": platform,
        "gender": gender, "genre": genre, "target_word_count": 30000,
        "initial_chapters": 5, "total_chapters": 30,
        "daily_chapters": 2, "daily_publish_time": "08:00",
    }


# ---------------------------------------------------------------- A
log("=" * 72)
log("A. GET /projects/platforms —— UTF-8 完整性 + 平台配置正确性")
log("=" * 72)
st, d = req("GET", "/projects/platforms")
check("HTTP 200", st == 200, st)
plats = {}
if isinstance(d, dict):
    plats = {p["key"]: p for p in d["platforms"]}
    b, f = plats.get("baidu"), plats.get("fanqie")
    check("默认平台 = baidu", d.get("default") == "baidu", d.get("default"))
    check("平台数 = 2", len(plats) == 2, list(plats))
    check("baidu 名称字符数=6（证明服务端非乱码）", b and len(b["label"]) == 6, b and len(b["label"]))
    check("baidu 名称 == 百度作家平台", b and b["label"] == LABEL_BAIDU, b and b["label"])
    check("fanqie 名称字符数=4（证明服务端非乱码）", f and len(f["label"]) == 4, f and len(f["label"]))
    check("fanqie 名称 == 番茄小说", f and f["label"] == LABEL_FQ, f and f["label"])
    check("baidu 频道 = 男性向/女性向/无性向",
          b and b["channels"] == [NANXING, NVXING, WUXING], b and b["channels"])
    check("fanqie 频道 = 女频/男频", f and f["channels"] == [NV, NAN], f and f["channels"])
    check("baidu 书名区间 = 17-30", b and b["title_len"] == [17, 30], b and b["title_len"])
    check("fanqie 书名区间 = 5-20", f and f["title_len"] == [5, 20], f and f["title_len"])
    check("baidu 前缀 = 故事：", b and b["title_prefix"] == PREFIX, b and b["title_prefix"])
    check("fanqie 无前缀", f and f["title_prefix"] == "", repr(f and f["title_prefix"]))
    check("baidu publish_ready=True", b and b["publish_ready"] is True)
    check("fanqie publish_ready=False（自动发布未实现）", f and f["publish_ready"] is False)
    check("fanqie 悬疑惊悚 属于 女频", f and SUSPENSE in f["genres"].get(NV, []))
    check("fanqie 悬疑惊悚 属于 男频", f and SUSPENSE in f["genres"].get(NAN, []))
    check("fanqie 都市日常 属于 男频", f and DUSHI in f["genres"].get(NAN, []))
    official = ["男频脑洞", "女频脑洞", "悬疑惊悚", "玄幻仙侠", "青春虐恋", "古言虐恋",
                "历史古代", "都市日常", "宫斗宅斗", "现言甜宠", "古言甜宠", "民国旧影",
                "年代", "女性成长"]
    have = set()
    for g in (f["genres"].values() if f else []):
        have.update(g)
    missing = [x for x in official if x not in have]
    check("番茄官方 14 品类全覆盖", not missing, ("缺: " + "、".join(missing)) if missing else "")

# ---------------------------------------------------------------- B
log("")
log("=" * 72)
log("B. 「平台 + 频道 + 品类」组合合法性校验")
log("=" * 72)
# 说明：成功创建会连带投递一次封面生成任务（create_project 内置行为），
# 故「放行」用例只保留 1 条，其余全部用「应拒绝」用例验证，不落库。
cases = [
    ("fanqie + 男频 + 玄幻仙侠  → 应放行（唯一落库用例）", "fanqie", NAN, FANTASY, 201),
    ("fanqie + 女频 + 玄幻仙侠  → 应拒绝（品类不属于该频道）", "fanqie", NV, FANTASY, 400),
    ("fanqie + 男性向          → 应拒绝（百度频道名）", "fanqie", NANXING, FANTASY, 400),
    ("baidu  + 男频            → 应拒绝（番茄频道名）", "baidu", NAN, "都市情感", 400),
    ("baidu  + 女性向 + 玄幻仙侠 → 应拒绝（番茄品类名）", "baidu", NVXING, FANTASY, 400),
    ("未知平台 zzz + 男频       → 应回落 baidu 后拒绝（证明回落生效）", "zzz", NAN, FANTASY, 400),
]
created = []
for idx, (label, plat, gd, ge, expect) in enumerate(cases):
    st, body = req("POST", "/projects", mk("E2E-%d-%s" % (idx, plat), plat, gd, ge))
    check(label, st == expect, "HTTP %s" % st)
    if st == 201 and isinstance(body, dict):
        created.append(body["id"])
        log("        落库: platform=%s gender=%s(%d字) genre=%s"
            % (body.get("platform"), body.get("gender"), len(body.get("gender", "")), body.get("genre")))
    if st == 400 and isinstance(body, dict):
        det = str(body.get("detail", ""))
        check("  拒绝信息含可选值提示", "可选值" in det, det[:90])
        # 拒绝文案应带对应平台名，证明走的是该平台配置而非硬编码
        if plat == "fanqie" and idx in (1, 2):
            check("  拒绝文案标注『番茄小说』", "番茄小说" in det, det[:50])
        if plat == "baidu":
            check("  拒绝文案标注『百度作家平台』", "百度作家平台" in det, det[:50])
        if plat == "zzz":
            check("  回落文案标注『百度作家平台』(证明 zzz→baidu)", "百度作家平台" in det, det[:50])

# ---------------------------------------------------------------- C
log("")
log("=" * 72)
log("C. 番茄书名生成（真实调用 LLM）")
log("=" * 72)
if created:
    pid = created[0]
    st, body = req("POST", "/projects/%s/generate-titles" % pid, timeout=240)
    check("generate-titles HTTP 200", st == 200, st)
    if st == 200 and isinstance(body, dict):
        check("返回 platform = fanqie", body.get("platform") == "fanqie", body.get("platform"))
        titles = body.get("titles") or []
        check("书名数量 >= 1", len(titles) >= 1, len(titles))
        check("无『故事：』前缀", all(not t.startswith(PREFIX) for t in titles), titles)
        lens = [count_chars(t) for t in titles]
        check("每本书名 5-20 字", all(5 <= n <= 20 for n in lens), lens)
        log("        生成书名：")
        for t, n in zip(titles, lens):
            log("          · %s   （%d 字）" % (t, n))
    else:
        log("        响应: %s" % str(body)[:300])
else:
    log("  跳过：无成功创建的项目")

# ---------------------------------------------------------------- D
log("")
log("=" * 72)
log("D. 清理测试数据")
log("=" * 72)
for pid in created:
    st, _ = req("DELETE", "/projects/%s" % pid)
    check("删除测试项目 %s…" % pid[:8], st in (204, 404), st)

# ---------------------------------------------------------------- 汇总
passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
log("")
log("=" * 72)
log("汇总：%d / %d 通过" % (passed, total))
fails = [l for l, ok, _ in results if not ok]
if fails:
    log("失败项：")
    for x in fails:
        log("  - " + x)
else:
    log("全部通过 ✔")
log("=" * 72)

with io.open(OUT_PATH, "w", encoding="utf-8") as fh:
    fh.write("\n".join(L) + "\n")

# stdout 只输出 ASCII 摘要，避免控制台乱码干扰
print("RESULT %d/%d PASS" % (passed, total))
print("DETAIL_FILE %s" % OUT_PATH)
if fails:
    print("FAILED_ITEMS %d" % len(fails))
