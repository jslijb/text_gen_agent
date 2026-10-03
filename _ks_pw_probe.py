# -*- coding: utf-8 -*-
"""临时探针：连接真实 Chrome (CDP 9222)，打印快手发布页状态。"""
import sys
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"


def main():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        urls = [pg.url for pg in ctx.pages]
        print("PAGES:", urls)
        pg = None
        for x in ctx.pages:
            if "kuaishou" in x.url:
                pg = x
                break
        if pg is None and ctx.pages:
            pg = ctx.pages[0]
        if pg is None:
            print("NO PAGE")
            b.close()
            return
        try:
            pg.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception as e:
            print("wait:", e)
        print("URL:", pg.url)
        print("TITLE:", pg.title())
        txt = pg.inner_text("body")[:1200]
        print("TEXT:", txt.replace("\n", " | "))
        try:
            pg.screenshot(path="output/videos/_ks_probe.png")
            print("screenshot saved")
        except Exception as e:
            print("shot err", e)
        b.close()


if __name__ == "__main__":
    main()
