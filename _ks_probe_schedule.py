# -*- coding: utf-8 -*-
"""探针3：发布时间（立即/定时）控件与发布按钮。"""
import json
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"


def main():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        pg = next((x for x in ctx.pages if "publish/video" in x.url), None)
        info = pg.evaluate(
            """() => {
            const out = {};
            out.radios = [...document.querySelectorAll('.ant-radio-wrapper,label')].map(el => ({
                t: (el.innerText||'').trim().slice(0,30),
                checked: !!el.querySelector('input:checked'),
                cls: (el.className||'').toString().slice(0,80),
            })).filter(x => x.t);
            out.pickers = [...document.querySelectorAll('.ant-picker,input')].map(el => ({
                tag: el.tagName, type: el.type||'',
                ph: el.placeholder||el.getAttribute('placeholder')||'',
                val: el.value||'',
                cls: (el.className||'').toString().slice(0,90),
            }));
            const btns = [...document.querySelectorAll('button')].map(el => (el.innerText||'').trim());
            out.buttons = btns.filter(Boolean).slice(0,20);
            return out;
        }"""
        )
        print(json.dumps(info, ensure_ascii=False, indent=2))
        b.close()


if __name__ == "__main__":
    main()
