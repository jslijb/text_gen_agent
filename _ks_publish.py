# -*- coding: utf-8 -*-
"""立即发布夸父：点发布 -> 处理确认弹窗 -> 报告结果。"""
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"


def main():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        pg = next((x for x in ctx.pages if "publish/video" in x.url), None)
        if pg is None:
            print("NO PUBLISH PAGE")
            b.close()
            return

        # 关掉引导遮罩
        pg.evaluate(
            "() => { const el=document.getElementById('react-joyride-portal'); if(el) el.remove();"
            " document.querySelectorAll('.react-joyride__overlay,.react-joyride__spotlight').forEach(e=>e.remove()); }"
        )
        pg.wait_for_timeout(300)

        # 确认描述仍在
        got = pg.locator("#work-description-edit").inner_text()
        print("DESC_OK:", "原来神就是孤独的" in got)

        # 点发布
        btn = pg.locator("._edit-section-btns_ql0z6_118 div._button-primary_3a3lq_60").first
        btn.click()
        print("clicked publish")
        pg.wait_for_timeout(2500)

        # 处理可能的确认弹窗
        for sel in ["text=确认发布", "text=确定", "text=继续发布"]:
            try:
                loc = pg.locator(sel).first
                if loc.is_visible():
                    loc.click(timeout=3000)
                    print("clicked confirm:", sel)
                    pg.wait_for_timeout(2500)
                    break
            except Exception as e:
                print("no confirm", sel, str(e)[:50])

        pg.wait_for_timeout(3000)
        body = pg.inner_text("body")
        print("URL:", pg.url)
        for kw in ["发布成功", "已发布", "审核", "定时", "失败", "异常", "违规"]:
            if kw in body:
                print("HIT:", kw)
        print("TAIL:", body[-500:].replace("\n", " | "))
        pg.screenshot(path="output/videos/_ks_published.png", full_page=True)
        b.close()


if __name__ == "__main__":
    main()
