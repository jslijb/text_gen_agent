# -*- coding: utf-8 -*-
"""删除「待发布」里的蚩尤条目。"""
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"


def main():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        pg = ctx.new_page()
        pg.goto("https://cp.kuaishou.com/article/manage/video", wait_until="domcontentloaded")
        pg.wait_for_timeout(6000)
        pg.locator("text=待发布").first.click(timeout=8000)
        pg.wait_for_timeout(4000)

        item = pg.locator(".video-item").filter(has_text="蚩尤").first
        if item.count() == 0:
            print("NO ITEM")
            pg.close(); b.close(); return
        item.hover()
        pg.wait_for_timeout(800)
        op = item.locator(".video-item__controls__operations__operation").filter(has_text="删除作品").first
        op.click(timeout=6000)
        print("clicked 删除作品")
        pg.wait_for_timeout(2000)
        # 确认弹窗
        for sel in ["text=确定", "text=确认", "text=删除"]:
            try:
                loc = pg.locator(".el-message-box__btns button, .ant-modal button, button").filter(has_text=sel.split("=")[1]).first
                if loc.is_visible():
                    loc.click(timeout=3000)
                    print("confirm:", sel)
                    pg.wait_for_timeout(2500)
                    break
            except Exception:
                pass
        pg.wait_for_timeout(3000)
        print("URL:", pg.url)
        t = pg.inner_text("body")
        print("STILL HAS 蚩尤:", "蚩尤" in t)
        print(t[:600].replace("\n", " | "))
        pg.close()
        b.close()


if __name__ == "__main__":
    main()
