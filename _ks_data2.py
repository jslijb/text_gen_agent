# -*- coding: utf-8 -*-
"""点左侧「数据中心」，打印概览（尝试采集账号近7日数据）。"""
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"


def main():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        pg = ctx.new_page()
        pg.goto("https://cp.kuaishou.com/article/manage/video", wait_until="domcontentloaded")
        pg.wait_for_timeout(5000)
        for label in ["数据中心", "作品数据"]:
            try:
                pg.locator("text=" + label).first.click(timeout=5000)
                print("clicked", label)
                pg.wait_for_timeout(7000)
                print("URL:", pg.url)
                print(pg.inner_text("body")[:1500].replace("\n", " | "))
                break
            except Exception as e:
                print("fail", label, str(e)[:80])
        pg.close()
        b.close()


if __name__ == "__main__":
    main()
