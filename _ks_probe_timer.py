# -*- coding: utf-8 -*-
"""点「定时发布」并打印日期/时间控件。"""
import json
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"


def main():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        pg = next((x for x in ctx.pages if "publish/video" in x.url), None)
        pg.evaluate(
            "() => { const el=document.getElementById('react-joyride-portal'); if(el) el.remove();"
            " document.querySelectorAll('.react-joyride__overlay,.react-joyride__spotlight').forEach(e=>e.remove()); }"
        )
        pg.wait_for_timeout(300)
        # 点「定时发布」radio
        try:
            pg.locator(".ant-radio-wrapper").filter(has_text="定时发布").first.click(timeout=6000)
            print("clicked 定时发布")
        except Exception as e:
            print("click fail:", str(e)[:150])
        pg.wait_for_timeout(1500)
        info = pg.evaluate(
            """() => {
            const out = {};
            out.inputs = [...document.querySelectorAll('input')].map(el => ({
                type: el.type, ph: el.placeholder||'', val: el.value||'',
                cls: (el.className||'').toString().slice(0,70)
            })).filter(x => x.ph || x.val);
            out.pickers = [...document.querySelectorAll('.ant-picker,[class*=picker],[class*=date],[class*=time]')].map(el => ({
                cls: (el.className||'').toString().slice(0,80), t: (el.innerText||'').trim().slice(0,40)
            })).slice(0,20);
            out.checkedRadios = [...document.querySelectorAll('.ant-radio-wrapper')].map(el => ({
                t:(el.innerText||'').trim().slice(0,10), c: !!el.querySelector('input:checked')
            })).filter(x=>x.t);
            return out;
        }"""
        )
        print(json.dumps(info, ensure_ascii=False, indent=2))
        pg.screenshot(path="output/videos/_ks_timer.png", full_page=True)
        b.close()


if __name__ == "__main__":
    main()
