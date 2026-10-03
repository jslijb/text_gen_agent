# -*- coding: utf-8 -*-
"""打开作品管理的「待发布」筛选，打印待发布作品。"""
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"


def main():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        pg = ctx.new_page()
        pg.goto("https://cp.kuaishou.com/article/manage/video", wait_until="domcontentloaded")
        pg.wait_for_timeout(6000)
        try:
            pg.locator("text=待发布").first.click(timeout=6000)
            print("clicked 待发布")
        except Exception as e:
            print("click fail:", str(e)[:120])
        pg.wait_for_timeout(4000)
        print("URL:", pg.url)
        t = pg.inner_text("body")
        print(t[:1800].replace("\n", " | "))
        pg.screenshot(path="output/videos/_ks_pending.png", full_page=True)
        pg.close()
        b.close()


if __name__ == "__main__":
    main()
