# -*- coding: utf-8 -*-
"""快手定时发布：set=设时间并校验；publish=提交。

用法： python _ks_schedule.py set|publish
"""
import sys
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"
WHEN = "2026-10-02 19:00:00"


def joyride_off(pg):
    pg.evaluate(
        "() => { const el=document.getElementById('react-joyride-portal'); if(el) el.remove();"
        " document.querySelectorAll('.react-joyride__overlay,.react-joyride__spotlight').forEach(e=>e.remove()); }"
    )


def set_time(pg):
    # 确保「定时发布」已选
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
    val = inp.input_value()
    print("PICKER VALUE =", repr(val))
    return val


def main():
    act = sys.argv[1] if len(sys.argv) > 1 else "set"
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        pg = next((x for x in b.contexts[0].pages if "publish/video" in x.url), None)
        if pg is None:
            print("NO PUBLISH PAGE")
            b.close()
            return
        joyride_off(pg)
        pg.wait_for_timeout(300)

        if act == "set":
            val = set_time(pg)
            print("SET_OK" if val.startswith("2026-10-02 19:00") else "SET_MISMATCH")
            pg.screenshot(path="output/videos/_ks_scheduled.png", full_page=True)
        elif act == "publish":
            val = set_time(pg)
            print("verify picker:", val)
            got = pg.locator("#work-description-edit").inner_text()
            print("desc has tag:", "蚩尤" in got)
            btn = pg.locator("._edit-section-btns_ql0z6_118 div._button-primary_3a3lq_60").first
            btn.click()
            print("clicked 发布")
            pg.wait_for_timeout(2500)
            for sel in ["text=确认发布", "text=确定", "text=继续发布"]:
                try:
                    loc = pg.locator(sel).first
                    if loc.is_visible():
                        loc.click(timeout=3000)
                        print("clicked confirm:", sel)
                        pg.wait_for_timeout(2500)
                        break
                except Exception:
                    pass
            pg.wait_for_timeout(3500)
            body = pg.inner_text("body")
            print("URL:", pg.url)
            for kw in ["定时发布成功", "发布成功", "待发布", "已发布", "审核", "失败", "异常"]:
                if kw in body:
                    print("HIT:", kw)
            print("TAIL:", body[-400:].replace("\n", " | "))
            pg.screenshot(path="output/videos/_ks_published2.png", full_page=True)
        b.close()


if __name__ == "__main__":
    main()
