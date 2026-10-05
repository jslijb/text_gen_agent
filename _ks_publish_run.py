# -*- coding: utf-8 -*-
"""一键代发: 上传 -> 填描述 -> 定时 -> 发布。

用法: _ks_publish_run.py <video_path> <desc_txt> <when "YYYY-MM-DD HH:MM:SS">
"""
import io
import os
import sys
from playwright.sync_api import sync_playwright

CDP = os.environ.get("KS_CDP", "http://127.0.0.1:9222")
PUB = "https://cp.kuaishou.com/article/publish/video"
VIDEO, DESC_FILE, WHEN = sys.argv[1], sys.argv[2], sys.argv[3]


def joyride_off(pg):
    pg.evaluate(
        "() => { const el=document.getElementById('react-joyride-portal'); if(el) el.remove();"
        " document.querySelectorAll('.react-joyride__overlay,.react-joyride__spotlight').forEach(e=>e.remove()); }"
    )


def set_ai_declare(pg):
    """作者声明 -> 内容为AI生成（必填项，否则平台不标 AI 来源）。"""
    sel = pg.locator(".ant-select").filter(has_text="为作品添加补充说明").first
    if sel.count() == 0:
        sel = pg.locator(".ant-select").filter(has_text="内容为AI生成").first
    if sel.count() == 0:
        print("!! 作者声明控件未找到")
        return False
    sel.click()
    pg.wait_for_timeout(1200)
    opt = pg.locator(".ant-select-item-option").filter(has_text="内容为AI生成").first
    if opt.count() == 0:
        pg.keyboard.press("Escape")
        print("!! 声明选项未出现")
        return False
    opt.click()
    pg.wait_for_timeout(1000)
    ok = "内容为AI生成" in pg.locator(".ant-select").filter(has_text="内容为AI生成").first.inner_text()
    print("DECLARE_AI:", ok)
    return ok


def dup_pending(ctx, title):
    """发布前硬闸：待发布列表里已有同标题作品就拒绝再发（防重复发布）。"""
    pg = ctx.new_page()
    try:
        pg.goto("https://cp.kuaishou.com/article/manage/video?status=2",
                wait_until="domcontentloaded")
        for _ in range(20):
            pg.wait_for_timeout(1500)
            if pg.locator(".video-item").count():
                break
        n = pg.locator(".video-item").filter(has_text=title).count()
        print("DUP_PENDING:", n, "|", title[:20])
        return n
    finally:
        pg.close()


def main():
    with io.open(DESC_FILE, encoding="utf-8") as f:
        desc = f.read()
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        pg = None
        for x in ctx.pages:
            if "cp.kuaishou.com" in x.url:
                pg = x
                break
        if pg is None:
            pg = ctx.new_page()
        title = desc.split("\n")[0].strip()
        if dup_pending(ctx, title) > 0:
            print("!! 待发布里已有同标题作品，拒绝重复发布")
            b.close()
            sys.exit(3)
        pg.goto(PUB, wait_until="domcontentloaded")
        pg.wait_for_timeout(3000)

        # 上传
        pg.locator("input[type=file]").first.set_input_files(VIDEO, timeout=30000)
        print("file set, waiting...")
        ok = False
        for i in range(120):
            pg.wait_for_timeout(2000)
            st = pg.evaluate(
                "() => ({d: !!document.querySelector('#work-description-edit'),"
                " f: (document.body.innerText||'').includes('上传失败'),"
                " p: (document.body.innerText||'').includes('上传中')})"
            )
            if st["f"]:
                print("!! UPLOAD FAILED")
                break
            if st["d"] and not st["p"]:
                ok = True
                print("form ready at", i)
                break
        if not ok:
            print("NOT_READY")
            b.close()
            return

        # 填描述
        joyride_off(pg)
        ed = pg.locator("#work-description-edit").first
        ed.fill(desc)
        pg.wait_for_timeout(1000)
        got = ed.inner_text()
        print("DESC_OK:", got.replace("\n", "").strip() == desc.replace("\n", "").strip())

        # 作者声明：内容为AI生成
        if not set_ai_declare(pg):
            print("!! 作者声明未勾上，放弃发布")
            b.close()
            sys.exit(4)
        pg.screenshot(path="output/videos/_ks_pub_state.png", full_page=True)

        # 定时
        r = pg.locator(".ant-radio-wrapper").filter(has_text="定时发布").first
        if not r.locator("input").is_checked():
            r.click()
            pg.wait_for_timeout(1000)
        inp = pg.locator("input[placeholder='选择日期时间']").first
        inp.click()
        pg.wait_for_timeout(400)
        pg.keyboard.press("Control+a")
        pg.keyboard.type(WHEN, delay=40)
        pg.wait_for_timeout(600)
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(1200)
        print("PICKER:", repr(inp.input_value()))
        got_when = inp.input_value().strip()
        if got_when != WHEN.strip():
            print("!! 定时时间被平台改成 %s（期望 %s），放弃发布" % (got_when, WHEN))
            b.close()
            sys.exit(2)
        sched = pg.locator(".ant-radio-wrapper").filter(has_text="定时发布").first.locator("input").is_checked()
        if not sched:
            print("!! 定时发布没勾上，放弃发布")
            b.close()
            sys.exit(2)
        print("SCHEDULED: %s" % WHEN)

        # 发布
        pg.locator("._edit-section-btns_ql0z6_118 div._button-primary_3a3lq_60").first.click()
        print("clicked 发布")
        pg.wait_for_timeout(2500)
        for sel in ["确认发布", "确定", "继续发布"]:
            try:
                loc = pg.locator("button,.el-button").filter(has_text=sel).first
                if loc.is_visible():
                    loc.click(timeout=3000)
                    print("confirm:", sel)
                    pg.wait_for_timeout(2500)
                    break
            except Exception:
                pass
        pg.wait_for_timeout(3000)
        body = pg.inner_text("body")
        print("URL:", pg.url)
        for kw in ["定时发布成功", "发布成功", "待发布", "已发布", "审核", "失败", "异常"]:
            if kw in body:
                print("HIT:", kw)
        b.close()


if __name__ == "__main__":
    main()
