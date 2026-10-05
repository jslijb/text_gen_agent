# -*- coding: utf-8 -*-
"""探针：发布页上与「内容声明 / AI 生成」相关的控件与文案。"""
import os
import sys
from playwright.sync_api import sync_playwright

CDP = os.environ.get("KS_CDP", "http://127.0.0.1:9223")
PUB = "https://cp.kuaishou.com/article/publish/video"

JS = """() => {
  const res = {hits: [], switches: [], radios: [], labels: []};
  const walk = document.querySelectorAll('body *');
  for (const el of walk) {
    const t = (el.childElementCount === 0 ? (el.innerText || '') : '').trim();
    if (!t || t.length > 80) continue;
    if (/声明|AI|人工|实拍|虚拟|内容类型/.test(t)) {
      res.hits.push({tag: el.tagName, cls: (el.className || '').toString().slice(0, 90), t});
    }
  }
  res.switches = [...document.querySelectorAll('[role=switch], .ant-switch, input[type=checkbox]')]
    .map((el, i) => ({i, cls: (el.className || '').toString().slice(0, 70),
      near: (el.closest('div') ? el.closest('div').innerText : '').replace(/\\n/g, ' ').slice(0, 60)}));
  res.radios = [...document.querySelectorAll('.ant-radio-wrapper, .el-radio')]
    .map(el => el.innerText.trim().slice(0, 30)).filter(Boolean);
  res.selects = [...document.querySelectorAll('.ant-select, .el-select')]
    .map(el => (el.closest('div') ? el.closest('div').innerText : '').replace(/\\n/g, ' ').slice(0, 80));
  return res;
}"""


def main():
    edit = "edit" in sys.argv
    pub = "pub" in sys.argv
    upload = "upload" in sys.argv
    decl = "decl" in sys.argv
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        pg = next((x for x in ctx.pages if "cp.kuaishou.com" in x.url), None) or ctx.new_page()
        if decl:
            pg.wait_for_timeout(2000)
            if not pg.locator("#work-description-edit").count():
                print("FORM EMPTY - need upload first")
                b.close()
                return
            row = pg.locator("div").filter(has_text="作者声明").last
            sel = pg.locator(".ant-select").filter(has_text="为作品添加补充说明").first
            if not sel.count():
                sel = row.locator(".ant-select").first
            sel.click()
            pg.wait_for_timeout(1500)
            opts = pg.evaluate("""() => [...document.querySelectorAll(
                '.ant-select-item-option, .ant-cascader-menu-item, li[role=option]')]
                .map(e => (e.innerText||'').trim().replace(/\\n/g,'>')).filter(Boolean)""")
            print("OPTIONS:", opts)
            pg.screenshot(path="output/videos/_ks_decl.png", full_page=True)
            b.close()
            return
        if upload:
            vid = sys.argv[sys.argv.index("upload") + 1]
            pg.goto(PUB, wait_until="domcontentloaded")
            pg.wait_for_timeout(3000)
            pg.locator("input[type=file]").first.set_input_files(vid, timeout=30000)
            print("uploading", vid)
            for i in range(150):
                pg.wait_for_timeout(2000)
                st = pg.evaluate("() => ({d: !!document.querySelector('#work-description-edit'),"
                                 " p: (document.body.innerText||'').includes('上传中')})")
                if st["d"] and not st["p"]:
                    print("form ready at", i)
                    break
            pg.wait_for_timeout(3000)
            for lab in ["更多设置", "展开", "高级设置"]:
                try:
                    loc = pg.locator("div,span,a,button").filter(has_text=lab).last
                    if loc.is_visible():
                        loc.click(timeout=2000)
                        pg.wait_for_timeout(1200)
                        print("expanded:", lab)
                except Exception:
                    pass
            print("URL:", pg.url)
            info = pg.evaluate(JS)
            print("=== HITS ===")
            for h in info["hits"]:
                print("  [%s|%s] %s" % (h["tag"], h["cls"][:50], h["t"]))
            print("=== SWITCHES ===")
            for s in info["switches"]:
                print("  #%d %s | %s" % (s["i"], s["cls"][:40], s["near"]))
            print("=== RADIOS ===", info["radios"])
            print("=== SELECTS ===")
            for x in info["selects"]:
                print("  ", x)
            print("=== FORM TEXT ===")
            t = pg.evaluate("() => { const e=document.querySelector('._edit-section_1l5c9_1, form, .ant-form');"
                            " return (e||document.body).innerText; }")
            print(t[:3000].replace("\n", " | "))
            pg.screenshot(path="output/videos/_ks_form_ai.png", full_page=True)
            b.close()
            return
        if "scan" in sys.argv:
            prof = sys.argv[sys.argv.index("scan") + 1]
            pg.goto(prof, wait_until="domcontentloaded")
            pg.wait_for_timeout(9000)
            for _ in range(8):
                pg.mouse.wheel(0, 4000)
                pg.wait_for_timeout(1200)
            ids = pg.evaluate("""()=>{
                const html = document.documentElement.innerHTML;
                const s = new Set();
                const re1 = /\"photoId\"\\s*:\\s*\"([A-Za-z0-9_-]{8,})\"/g;
                const re2 = /short-video\\/([A-Za-z0-9_-]{8,})/g;
                let m; while ((m = re1.exec(html))) s.add(m[1]);
                while ((m = re2.exec(html))) s.add(m[1]);
                return [...s]; }""")
            print("works:", len(ids))
            for vid in ids:
                try:
                    pg.goto("https://www.kuaishou.com/short-video/" + vid,
                            wait_until="domcontentloaded")
                    pg.wait_for_timeout(4500)
                    r = pg.evaluate("""()=>{const t=document.body.innerText||'';
                        const ln=t.split(String.fromCharCode(10)).map(s=>s.trim()).filter(Boolean);
                        return {ai: /疑似含AI生成内容|内容由AI生成|AI生成/.test(t),
                                pin: /置顶/.test(t),
                                title: (ln.find(l=>l.includes('｜山海经'))||ln.slice(0,3).join('/')).slice(0,34),
                                cmt: (t.match(/(\\d+)\\s*条?评论/)||[])[1]||'-'}; }""")
                    print("  %-22s AI=%-5s 评论=%-4s %s" % (vid, r["ai"], r["cmt"], r["title"]))
                except Exception as e:
                    print("  ", vid, "FAIL", str(e)[:60])
            b.close()
            return
        if "web" in sys.argv:
            url = sys.argv[sys.argv.index("web") + 1]
            pg.goto(url, wait_until="domcontentloaded")
            pg.wait_for_timeout(9000)
            info = pg.evaluate("""() => {
              const t = document.body.innerText || '';
              const ins = [...document.querySelectorAll('[contenteditable], textarea, input[type=text]')]
                .map(e => ({tag: e.tagName, cls: (e.className||'').toString().slice(0,70),
                            ph: e.getAttribute('placeholder') || e.getAttribute('data-placeholder') || '',
                            vis: !!(e.offsetWidth || e.offsetHeight)}));
              const cmts = [...document.querySelectorAll('[class*=comment]')]
                .map(e => (e.className||'').toString()).filter((v,i,a)=>a.indexOf(v)===i).slice(0,25);
              return {url: location.href, loginHint: /登录|注册/.test(t.slice(0,4000)),
                      hasMe: /我的主页|个人主页|退出/.test(t), inputs: ins, cmts,
                      head: t.slice(0, 500).replace(/\\n/g, ' | ')};
            }""")
            print("URL:", info["url"])
            print("loginHint(未登录迹象):", info["loginHint"], "| hasMe:", info["hasMe"])
            print("INPUTS:", info["inputs"])
            print("COMMENT_CLASSES:", info["cmts"])
            print("PROFILE_LINKS:", pg.evaluate(
                "()=>[...document.querySelectorAll('a[href]')].map(a=>a.getAttribute('href'))"
                ".filter(h=>/profile|short-video/.test(h)).filter((v,i,s)=>s.indexOf(v)===i).slice(0,10)"))
            print("AI_MARK:", pg.evaluate(
                "()=>{const t=document.body.innerText||'';return [...new Set(t.split(String.fromCharCode(10))"
                ".filter(l=>/AI|ai生成|虚拟|声明/.test(l)&&l.length<40))].slice(0,8)}"))
            print("HEAD:", info["head"])
            pg.screenshot(path="output/videos/_ks_web.png", full_page=True)
            b.close()
            return
        if "ops" in sys.argv:
            st = sys.argv[sys.argv.index("ops") + 1]
            pg.goto("https://cp.kuaishou.com/article/manage/video?status=" + st,
                    wait_until="domcontentloaded")
            pg.wait_for_timeout(8000)
            n = pg.locator(".video-item").count()
            print("items:", n)
            for i in range(n):
                it = pg.locator(".video-item").nth(i)
                title = it.inner_text().replace("\n", " ")[:26]
                try:
                    it.hover()
                    pg.wait_for_timeout(700)
                except Exception:
                    pass
                ops = it.locator(".video-item__controls__operations__operation, [class*=operation]")
                texts = []
                for j in range(ops.count()):
                    try:
                        texts.append(ops.nth(j).inner_text().replace("\n", "").strip())
                    except Exception:
                        pass
                print("  %2d | %-26s | %s" % (i, title, sorted(set(t for t in texts if t))))
            b.close()
            return
        if "rows" in sys.argv:
            st = sys.argv[sys.argv.index("rows") + 1] if len(sys.argv) > sys.argv.index("rows") + 1 else "2"
            pg.goto("https://cp.kuaishou.com/article/manage/video?status=" + st,
                    wait_until="domcontentloaded")
            pg.wait_for_timeout(7000)
            info = pg.evaluate("""() => {
              const rows = [...document.querySelectorAll('a[href],button,[class*=opera] *,[class*=btn] *,span,div')]
                .filter(e => e.childElementCount === 0);
              const acts = [...new Set(rows.map(e => (e.innerText||'').trim())
                .filter(t => t && t.length <= 8 && /编辑|查看|删除|复制|链接|详情|预览|声明|更多/.test(t)))];
              const links = [...document.querySelectorAll('a[href]')].map(a => a.href)
                .filter(h => /kuaishou\\.com\\/(short-video|profile|fw)/.test(h)).slice(0, 8);
              return {acts, links};
            }""")
            print("ACTIONS:", info["acts"])
            print("LINKS:", info["links"])
            b.close()
            return
        if pub:
            pg.goto("https://cp.kuaishou.com/article/manage/video", wait_until="domcontentloaded")
            pg.wait_for_timeout(6000)
            try:
                pg.locator("text=已发布").first.click(timeout=6000)
                print("clicked 已发布")
            except Exception as e:
                print("click fail:", str(e)[:100])
            pg.wait_for_timeout(5000)
            t = pg.inner_text("body")
            print("URL:", pg.url)
            print("LEN:", len(t))
            print(t[:2500].replace("\n", " | "))
            pg.screenshot(path="output/videos/_ks_pub_ai.png", full_page=True)
            b.close()
            return
        if edit:
            pg.goto("https://cp.kuaishou.com/article/manage/video?status=2", wait_until="domcontentloaded")
            pg.wait_for_timeout(6000)
            clicked = False
            for sel in ["编辑", "修改"]:
                try:
                    loc = pg.locator("a,button,span").filter(has_text=sel).first
                    if loc.is_visible():
                        loc.click()
                        clicked = True
                        print("clicked", sel)
                        break
                except Exception:
                    pass
            if not clicked:
                print("NO EDIT BUTTON")
            pg.wait_for_timeout(6000)
            cand = [x for x in ctx.pages if "publish" in x.url or "edit" in x.url]
            if cand:
                pg = cand[-1]
            pg.wait_for_timeout(4000)
        else:
            pg.goto(PUB, wait_until="domcontentloaded")
            pg.wait_for_timeout(5000)
        print("URL:", pg.url)
        info = pg.evaluate(JS)
        print("=== HITS ===")
        for h in info["hits"]:
            print("  [%s|%s] %s" % (h["tag"], h["cls"][:50], h["t"]))
        print("=== SWITCHES ===")
        for s in info["switches"]:
            print("  #%d %s | %s" % (s["i"], s["cls"][:40], s["near"]))
        print("=== RADIOS ===", info["radios"])
        print("=== SELECTS ===")
        for x in info["selects"]:
            print("  ", x)
        b.close()


if __name__ == "__main__":
    main()
