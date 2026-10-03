# -*- coding: utf-8 -*-
"""在「待发布」tab 找到蚩尤条目，打印其操作按钮/菜单。"""
import json
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"


def main():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        pg = ctx.new_page()
        pg.goto("https://cp.kuaishou.com/article/manage/video", wait_until="domcontentloaded")
        pg.wait_for_timeout(6000)
        try:
            pg.locator("text=待发布").first.click(timeout=6000)
            pg.wait_for_timeout(4000)
        except Exception as e:
            print("tab fail", str(e)[:100])
        # 找包含「蚩尤」的最外层作品卡片
        info = pg.evaluate(
            """() => {
            const all=[...document.querySelectorAll('div,li')].filter(e => e.innerText && e.innerText.includes('蚩尤') && e.innerText.length < 2000);
            if(!all.length) return {none:true};
            const card = all[all.length-1];
            const btns=[...card.querySelectorAll('button,[role=button],[class*=btn],[class*=Btn],[class*=icon],[class*=more]')].map(e=>({
                t:(e.innerText||'').trim().slice(0,12),
                cls:(e.className||'').toString().slice(0,70),
                title:e.getAttribute('title')||e.getAttribute('aria-label')||''
            })).filter(x=>x.t||x.cls);
            return {cardCls:(card.className||'').toString().slice(0,80), n:all.length, btns:btns.slice(0,25)};
        }"""
        )
        print(json.dumps(info, ensure_ascii=False, indent=2))
        pg.close()
        b.close()


if __name__ == "__main__":
    main()
