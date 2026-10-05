# -*- coding: utf-8 -*-
"""删除「待发布」里匹配关键词的作品（用于删除后带 AI 声明重发）。

用法: _ks_del_pending.py <标题关键词>
"""
import os
import sys
from playwright.sync_api import sync_playwright

CDP = os.environ.get("KS_CDP", "http://127.0.0.1:9223")
MANAGE = "https://cp.kuaishou.com/article/manage/video?status=2"


def main():
    kw = sys.argv[1]
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        pg = ctx.new_page()
        try:
            pg.goto(MANAGE, wait_until="domcontentloaded")
            for _ in range(30):
                pg.wait_for_timeout(1500)
                if pg.locator(".video-item").count():
                    break
            else:
                try:
                    pg.locator("text=待发布").first.click(timeout=5000)
                    pg.wait_for_timeout(6000)
                except Exception:
                    pass
            print("items on page:", pg.locator(".video-item").count())
            items = pg.locator(".video-item").filter(has_text=kw)
            n = items.count()
            print("matched:", n)
            if n == 0:
                print("NO ITEM:", kw)
                sys.exit(1)
            if n > 1:
                print("!! 匹配到 %d 条，目标不唯一，拒绝删除" % n)
                sys.exit(2)
            item = items.first
            txt = item.inner_text().replace("\n", " ")
            print("target:", txt[:40])
            # 硬闸：只允许删「待发布」条目（条目文本必须带「定时发布」字样）
            if "定时发布" not in txt:
                print("!! 目标条目不是待发布（无「定时发布」字样），拒绝删除")
                sys.exit(2)
            item.hover()
            pg.wait_for_timeout(800)
            item.get_by_text("删除作品", exact=True).first.click(timeout=6000)
            print("clicked 删除作品")
            pg.wait_for_timeout(2000)
            for lab in ["确定", "确认", "删除"]:
                try:
                    loc = pg.locator(".el-message-box__btns button, .ant-modal button, button") \
                        .filter(has_text=lab).first
                    if loc.count() and loc.is_visible():
                        loc.click(timeout=3000)
                        print("confirmed:", lab)
                        pg.wait_for_timeout(3000)
                        break
                except Exception:
                    pass
            left = pg.locator(".video-item").filter(has_text=kw).count()
            print("REMAIN matched:", left)
        finally:
            pg.close()
            b.close()


if __name__ == "__main__":
    main()
