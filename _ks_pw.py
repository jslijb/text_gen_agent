# -*- coding: utf-8 -*-
"""快手代发驱动（连接真实 Chrome，CDP 9222）。

用法： python _ks_pw.py <action>
  dump      打印当前页状态
  login     点击「立即登录」并截图登录二维码
  waitlogin 轮询等待登录成功（最多 240s）
"""
import sys
import time
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"
PUB = "https://cp.kuaishou.com/article/publish/video"


def kpage(ctx):
    for pg in ctx.pages:
        if "kuaishou" in pg.url:
            return pg
    return ctx.pages[0] if ctx.pages else None


def connected(fn):
    def inner():
        with sync_playwright() as p:
            b = p.chromium.connect_over_cdp(CDP)
            ctx = b.contexts[0]
            try:
                fn(ctx)
            finally:
                b.close()
    return inner


@connected
def dump(ctx):
    print("PAGES:", [pg.url for pg in ctx.pages])
    pg = kpage(ctx)
    if not pg:
        print("NO PAGE")
        return
    pg.wait_for_timeout(800)
    print("URL:", pg.url)
    print("TITLE:", pg.title())
    print("TEXT:", pg.inner_text("body")[:600].replace("\n", " | "))
    pg.screenshot(path="output/videos/_ks_state.png")


@connected
def login(ctx):
    pg = kpage(ctx)
    if not pg:
        print("NO PAGE")
        return
    pg.goto(PUB, wait_until="domcontentloaded")
    pg.wait_for_timeout(2500)
    for sel in ["text=立即登录", "text=登录"]:
        try:
            pg.locator(sel).first.click(timeout=4000)
            print("clicked", sel)
            break
        except Exception as e:
            print("skip", sel, str(e)[:60])
    pg.wait_for_timeout(3500)
    print("URL:", pg.url)
    print("TEXT:", pg.inner_text("body")[:400].replace("\n", " | "))
    pg.screenshot(path="output/videos/_ks_login.png")
    print("saved output/videos/_ks_login.png")


@connected
def waitlogin(ctx):
    pg = kpage(ctx)
    if not pg:
        print("NO PAGE")
        return
    for i in range(120):
        try:
            txt = pg.inner_text("body")[:2000]
        except Exception:
            txt = ""
        url = pg.url
        if ("Albert" in txt or "山海经" in txt or "发布作品" in txt) and "cp.kuaishou.com" in url:
            print("LOGIN OK url=%s" % url)
            pg.screenshot(path="output/videos/_ks_logged.png")
            return
        time.sleep(2)
    print("TIMEOUT url=%s" % pg.url)


if __name__ == "__main__":
    act = sys.argv[1] if len(sys.argv) > 1 else "dump"
    {"dump": dump, "login": login, "waitlogin": waitlogin}.get(act, dump)()
