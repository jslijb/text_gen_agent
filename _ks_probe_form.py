# -*- coding: utf-8 -*-
"""探针2：找作品描述 contenteditable、发布/定时控件。"""
import json
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"


def main():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        pg = next((x for x in ctx.pages if "kuaishou" in x.url), None)
        info = pg.evaluate(
            """() => {
            const out = {};
            out.editables = [...document.querySelectorAll('[contenteditable]')].map(el => ({
                ce: el.getAttribute('contenteditable'),
                ph: el.getAttribute('data-placeholder') || el.getAttribute('placeholder') || '',
                cls: (el.className||'').toString().slice(0,120),
                txt: (el.innerText||'').slice(0,60),
            }));
            out.allButtons = [...document.querySelectorAll('button,[role=button],[class*=btn],[class*=Btn]')].map(el => ({
                tag: el.tagName,
                t: (el.innerText||'').trim().slice(0,20),
                cls: (el.className||'').toString().slice(0,90),
            })).filter(x => x.t);
            out.inputs = [...document.querySelectorAll('input')].map(el => ({
                type: el.type, ph: el.placeholder||'', cls: (el.className||'').toString().slice(0,80)
            }));
            return out;
        }"""
        )
        print(json.dumps(info, ensure_ascii=False, indent=2))
        b.close()


if __name__ == "__main__":
    main()
