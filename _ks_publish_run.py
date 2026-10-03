# -*- coding: utf-8 -*-
"""一键代发: 上传 -> 填描述 -> 定时 -> 发布。

用法: _ks_publish_run.py <video_path> <desc_txt> <when "YYYY-MM-DD HH:MM:SS">
"""
import io
import sys
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"
PUB = "https://cp.kuaishou.com/article/publish/video"
VIDEO, DESC_FILE, WHEN = sys.argv[1], sys.argv[2], sys.argv[3]


def joyride_off(pg):
    pg.evaluate(
        "() => { const el=document.getElementById('react-joyride-portal'); if(el) el.remove();"
        " document.querySelectorAll('.react-joyride__overlay,.react-joyride__spotlight').forEach(e=>e.remove()); }"
    )


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
            print("NO KUAISHOU PAGE")
            b.close()
            return
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
