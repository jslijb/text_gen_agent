# -*- coding: utf-8 -*-
"""填入夸父作品描述（contenteditable）。不发布。"""
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"

DESC = """铜头铁额的战神，兵家却祭他千年｜山海经·蚩尤
《山海经·大荒北经》：蚩尤作兵伐黄帝，黄帝乃令应龙攻之冀州之野。应龙畜水，蚩尤请风伯雨师，纵大风雨。黄帝乃下天女曰魃，雨止，遂杀蚩尤。
《大荒南经》：蚩尤所弃其桎梏，是为枫木。
第一个造兵器的人，为什么成了「作乱」的代名词？你说他是败将，还是被写输了的英雄？
#山海经 #蚩尤 #AI经典奇谈 #原来神就是孤独的"""


def main():
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        pg = next((x for x in ctx.pages if "publish/video" in x.url), None)
        if pg is None:
            print("NO PUBLISH PAGE")
            b.close()
            return
        # 关掉 react-joyride 引导遮罩（会拦截点击）
        pg.evaluate(
            """() => {
            const p = document.getElementById('react-joyride-portal');
            if (p) p.remove();
            document.querySelectorAll('.react-joyride__overlay,.react-joyride__spotlight').forEach(e => e.remove());
        }"""
        )
        pg.wait_for_timeout(300)
        ed = pg.locator("#work-description-edit").first
        try:
            ed.fill(DESC)
            print("fill ok")
        except Exception as e:
            print("fill failed:", str(e)[:200], "-> keyboard")
            ed.focus()
            pg.keyboard.insert_text(DESC)
        pg.wait_for_timeout(1200)
        got = ed.inner_text()
        print("GOT:", repr(got[:400]))
        print("MATCH:", got.replace("\n", "").strip() == DESC.replace("\n", "").strip())
        pg.screenshot(path="output/videos/_ks_filled.png", full_page=True)
        b.close()


if __name__ == "__main__":
    main()
