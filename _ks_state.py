# -*- coding: utf-8 -*-
"""在独立标签页读取「内容管理」作品列表（不动上传表单页）。"""
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"
MANAGE = "https://cp.kuaishou.com/article/manage/video"


def main():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        pg = ctx.new_page()
        pg.goto(MANAGE, wait_until="domcontentloaded")
        pg.wait_for_timeout(6000)
        print("URL:", pg.url)
        try:
            print("TEXT:", pg.inner_text("body")[:3000].replace("\n", " | "))
        except Exception as e:
            print("err", e)
        pg.screenshot(path="output/videos/_ks_manage.png", full_page=True)
        pg.close()
        b.close()


if __name__ == "__main__":
    main()
