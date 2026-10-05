# -*- coding: utf-8 -*-
"""快手「首发评论 + 置顶」补发器（幂等，可错过补跑）。

队列: data/ks_comment_queue.json
用法:
  _ks_comment_run.py            执行所有到点且未完成的任务
  _ks_comment_run.py status     只看队列状态
  _ks_comment_run.py check      只做定位与校验，不真的发评论

铁律（CLAUDE.md）：评论前必须确认「作品真的已发布」且「就是这个 workId」，
任一项不过就不发，写 error 等人工看，绝不对着别的作品发评论。
"""
import datetime as dt
import io
import json
import os
import re
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.abspath(__file__))
QUEUE_F = os.path.join(ROOT, "data", "ks_comment_queue.json")
GUIDE_F = os.path.join(ROOT, "发布指南.md")
LOG_F = os.path.join(ROOT, "logs", "ks_comment.log")
CDP = os.environ.get("KS_CDP", "http://127.0.0.1:9223")
CHROME = r"C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"
PROFILE = os.path.join(ROOT, ".pw_chrome")
GRACE = int(os.environ.get("KS_COMMENT_GRACE", "120"))   # 发布后留出的落地时间(秒)
DONE = ("comment_done", "skipped")


def log(msg):
    line = "[%s] %s" % (dt.datetime.now().strftime("%m-%d %H:%M:%S"), msg)
    print(line)
    d = os.path.dirname(LOG_F)
    if not os.path.isdir(d):
        os.makedirs(d)
    with io.open(LOG_F, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load():
    with io.open(QUEUE_F, encoding="utf-8") as f:
        return json.load(f)


def save(tasks):
    tmp = QUEUE_F + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    os.replace(tmp, QUEUE_F)


def cdp_up():
    return subprocess.run(["curl", "-s", "--max-time", "3", CDP + "/json/version"],
                          capture_output=True).stdout.strip() != b""


def ensure_chrome():
    for _ in range(4):
        if cdp_up():
            return True
        subprocess.Popen([CHROME, "--remote-debugging-port=9223", "--remote-allow-origins=*",
                          "--user-data-dir=" + PROFILE, "--no-first-run",
                          "--no-default-browser-check", "https://cp.kuaishou.com/article/publish/video"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(12)
    return cdp_up()


def parse_guide():
    """从 发布指南.md 取每条作品的「首发评论」正文，文档是唯一权威来源。
    同名条目以先出现的为准（快手节在抖音节之前）。"""
    txt = io.open(GUIDE_F, encoding="utf-8").read()
    out = {}
    for part in re.split(r"^### ", txt, flags=re.M)[1:]:
        head, _, body = part.partition("\n")
        m2 = re.search(r"｜山海经·([^\s#，。]+)", body)
        name = m2.group(1) if m2 else re.split(r"[（(]", head.strip())[0].strip()
        m = re.search(r"\*\*首发评论\*\*[^\n]*\n+\s*((?:>[^\n]*\n?)+)", body)
        if not m:
            continue
        lines = [re.sub(r"^\s*>\s?", "", l).strip() for l in m.group(1).strip().split("\n")]
        c = "".join(l for l in lines if l)
        if c:
            out.setdefault(name, c)
    return out


def sync_from_guide(tasks):
    """把文档里的评论正文刷进队列（已完成的不动）；文档缺条目就报错，绝不自己编文案。"""
    guide = parse_guide()
    n = 0
    for t in tasks:
        if t["status"] in DONE:
            continue
        name = t["match"].split("·")[-1]
        if name not in guide:
            log("SYNC_MISS %s: 发布指南.md 找不到「%s」的首发评论，沿用队列原文" % (t["key"], name))
            continue
        if guide[name] != t["comment"]:
            log("SYNC_UPD %s: 以文档为准（%d→%d 字）" % (t["key"], len(t["comment"]), len(guide[name])))
            t["comment"] = guide[name]
            n += 1
    if n:
        save(tasks)
    return n


def parse_ts(s):
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def with_only(ctx, keep):
    """关掉本任务之外新开的标签页，保留 keep 里列出的。"""
    for pg in list(ctx.pages):
        if pg not in keep:
            try:
                pg.close()
            except Exception:
                pass


def resolve_work_id(ctx, task):
    """在创作者中心「已发布」里按标题串定位作品，取编辑页 URL 上的 workId。"""
    base = set(ctx.pages)
    pg = ctx.new_page()
    try:
        pg.goto("https://cp.kuaishou.com/article/manage/video?status=1",
                wait_until="domcontentloaded")
        for _ in range(20):
            pg.wait_for_timeout(1500)
            if pg.locator(".video-item").count():
                break
        item = pg.locator(".video-item").filter(has_text=task["match"])
        n = item.count()
        if n == 0:
            return None, "NOT_PUBLISHED"
        if n > 1:
            return None, "AMBIGUOUS_TITLE"
        item = item.first
        item.hover()
        pg.wait_for_timeout(800)
        item.get_by_text("编辑作品", exact=True).first.click(timeout=6000)
        for _ in range(40):
            pg.wait_for_timeout(1000)
            urls = [x.url for x in ctx.pages if x not in base] + [pg.url]
            m = next((re.search(r"workId=([A-Za-z0-9_-]+)", u) for u in urls
                      if re.search(r"workId=([A-Za-z0-9_-]+)", u)), None)
            if m:
                return m.group(1), "OK"
            if any("publishId" in u for u in urls):     # 还在待发布，没真正发出去
                return None, "STILL_PENDING"
        return None, "NO_WORKID"
    finally:
        with_only(ctx, base | {pg})


def post_comment(ctx, task, work_id, dry):
    """在公开页校验作品身份 -> 查重 -> 发首评 -> 尝试置顶。"""
    base = set(ctx.pages)
    pg = ctx.new_page()
    try:
        pg.goto("https://www.kuaishou.com/short-video/" + work_id,
                wait_until="domcontentloaded")
        pg.wait_for_timeout(8000)
        body = pg.inner_text("body")
        # 身份校验：标题串必须出现在这个公开页上
        if task["match"] not in body:
            return "error", "TITLE_MISMATCH"
        if task["match"] not in (pg.title() or "") and task["match"] not in body[:1500]:
            return "error", "TITLE_MISMATCH"
        ta = pg.locator("textarea.pl-textarea, textarea").first
        if ta.count() == 0:
            return "blocked_login", "NO_TEXTAREA"
        dup = task["comment"][:12]
        if dup in body:
            return "comment_done", "ALREADY_POSTED"
        ta.click(timeout=5000)
        pg.wait_for_timeout(1200)
        if "扫码" in pg.inner_text("body") or "手机号" in pg.inner_text("body"):
            return "blocked_login", "LOGIN_GATE"
        if dry:
            return "checked", "DRY"
        ta.fill(task["comment"])
        pg.wait_for_timeout(800)
        sent = False
        for lab in ["发送", "发布"]:
            btn = pg.locator("button, div, span").filter(has_text=lab).last
            try:
                if btn.is_visible():
                    btn.click(timeout=3000)
                    sent = True
                    break
            except Exception:
                continue
        if not sent:
            return "error", "NO_SEND_BTN"
        pg.wait_for_timeout(6000)
        if dup not in pg.inner_text("body"):
            return "error", "POST_NOT_CONFIRMED"
        pinned = False
        mine = pg.locator("[class*=comment]").filter(has_text=dup).first
        try:
            mine.hover()
            pg.wait_for_timeout(900)
            pin = mine.locator("text=置顶").first
            if pin.count() and pin.is_visible():
                pin.click(timeout=3000)
                pg.wait_for_timeout(2500)
                for lab in ["确定", "确认"]:
                    ok = pg.locator("button").filter(has_text=lab).first
                    if ok.count() and ok.is_visible():
                        ok.click(timeout=2500)
                        break
                pg.wait_for_timeout(2500)
                pinned = "已置顶" in pg.inner_text("body") or "置顶评论" in pg.inner_text("body")
        except Exception:
            pinned = False
        return "comment_done", ("PIN_OK" if pinned else "PIN_MANUAL_ON_APP")
    finally:
        with_only(ctx, base | {pg})


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    tasks = load()
    if mode == "status":
        for t in tasks:
            print("%-12s %-20s %-18s work=%-18s %s" % (
                t["key"], t["publish_at"], t["status"], t.get("work_id") or "-",
                t.get("note", "")))
        return
    if mode == "sync":
        n = sync_from_guide(tasks)
        print("SYNC_CHANGED:", n, "| guide entries:", len(parse_guide()))
        return
    log("START mode=%s" % mode)
    if not ensure_chrome():
        log("CHROME 起不来，退出")
        sys.exit(1)
    sync_from_guide(tasks)
    now = dt.datetime.now()
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        if not b.contexts:
            log("CDP 连上了但没有浏览器上下文（Chrome 处于无窗口的僵尸态），退出")
            b.close()
            sys.exit(1)
        ctx = b.contexts[0]
        for t in tasks:
            if t["status"] in DONE or t["status"] == "needs_human":
                continue
            due = parse_ts(t["publish_at"]) + dt.timedelta(seconds=GRACE)
            if due > now:
                continue
            log("DUE %s (%s)" % (t["key"], t["publish_at"]))
            if not t.get("comment"):
                t["status"], t["note"] = "error", "NO_COMMENT_IN_GUIDE"
                save(tasks)
                log("  %s 队列和发布指南都没有评论正文，跳过" % t["key"])
                continue
            if not t.get("work_id"):
                wid, note = resolve_work_id(ctx, t)
                t["attempts"] = t.get("attempts", 0) + 1
                t["note"] = note
                if wid is None:
                    t["status"] = "waiting_publish" if note == "NOT_PUBLISHED" else "error"
                    if note == "STILL_PENDING":
                        t["status"] = "waiting_publish"
                    if t["attempts"] >= 3:
                        t["status"] = "needs_human"
                        t["note"] = "%s（已试 %d 次，需人工）" % (note, t["attempts"])
                    log("  %s 未定位到已发布作品: %s" % (t["key"], note))
                    save(tasks)
                    continue
                t["work_id"] = wid
                log("  %s workId=%s" % (t["key"], wid))
            st, note = post_comment(ctx, t, t["work_id"], mode == "check")
            t["status"], t["note"] = st, note
            t["updated"] = now.strftime("%Y-%m-%d %H:%M:%S")
            save(tasks)
            log("  %s -> %s (%s)" % (t["key"], st, note))
            if st == "blocked_login":
                log("  网页版未登录，后续任务需要人工先扫码，全部停止")
                break
        b.close()
    save(tasks)
    log("END mode=%s" % mode)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        log("CRASH:\n" + traceback.format_exc())
        raise
