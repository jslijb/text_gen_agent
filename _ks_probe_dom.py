# -*- coding: utf-8 -*-
"""探针：打印快手桌面发布页的关键元素（file input / textarea / 按钮）。"""
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"


def main():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        pg = None
        for x in ctx.pages:
            if "kuaishou" in x.url:
                pg = x
                break
        if pg is None:
            print("NO PAGE")
            b.close()
            return
        print("URL:", pg.url)

        info = pg.evaluate(
            """() => {
            const out = {};
            out.fileInputs = [...document.querySelectorAll('input[type=file]')].map(el => ({
                accept: el.accept, multiple: el.multiple,
                name: el.name, id: el.id,
                cls: (el.className||'').toString().slice(0,80),
                hidden: el.offsetParent === null,
            }));
            out.textareas = [...document.querySelectorAll('textarea,input[type=text]')].map(el => ({
                tag: el.tagName, ph: el.placeholder||'', maxlen: el.maxLength,
                cls: (el.className||'').toString().slice(0,80),
            }));
            out.buttons = [...document.querySelectorAll('button,[role=button],a')].map(el => (el.innerText||'').trim()).filter(t => t && t.length < 12).slice(0, 60);
            return out;
        }"""
        )
        import json

        print(json.dumps(info, ensure_ascii=False, indent=2))
        b.close()


if __name__ == "__main__":
    main()
