# -*- coding: utf-8 -*-
"""采集快手后台数据中心概览（新标签页，不动管理页）。"""
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"
URLS = [
    "https://cp.kuaishou.com/data/overview",
    "https://cp.kuaishou.com/profile",
]


def main():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        for u in URLS:
            pg = ctx.new_page()
            try:
                pg.goto(u, wait_until="domcontentloaded")
                pg.wait_for_timeout(7000)
                print("=" * 30, u)
                print("FINAL:", pg.url)
                print(pg.inner_text("body")[:2500].replace("\n", " | "))
            except Exception as e:
                print("err", u, str(e)[:120])
            pg.close()
        b.close()


if __name__ == "__main__":
    main()
