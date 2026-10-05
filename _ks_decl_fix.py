# -*- coding: utf-8 -*-
"""给「待发布」作品补勾 作者声明=内容为AI生成。

用法:
  _ks_decl_fix.py dry <标题关键词>     只打开编辑页，打印表单状态，不保存
  _ks_decl_fix.py one <标题关键词>     打开编辑页，勾声明并保存
"""
import os
import sys
from playwright.sync_api import sync_playwright

CDP = os.environ.get("KS_CDP", "http://127.0.0.1:9223")
STATUS = os.environ.get("KS_STATUS", "2")
MANAGE = "https://cp.kuaishou.com/article/manage/video?status=" + STATUS
DECL = "内容为AI生成"


def open_editor(ctx, pg, kw):
    """从待发布列表进入匹配 kw 的第一条的编辑页（可能新开标签页）。"""
    pg.goto(MANAGE, wait_until="domcontentloaded")
    pg.wait_for_timeout(7000)
    item = pg.locator(".video-item").filter(has_text=kw).first
    if item.count() == 0:
        print("NO ITEM:", kw)
        return None
    before = set(ctx.pages)
    item.hover()
    pg.wait_for_timeout(800)
    item.get_by_text("编辑作品", exact=True).first.click(timeout=6000)
    for _ in range(40):
        pg.wait_for_timeout(1000)
        new = [x for x in ctx.pages if x not in before]
        if new:
            pg = new[-1]
            print("NEW TAB:", pg.url)
        try:
            if pg.locator("#work-description-edit").count():
                break
        except Exception:
            pass
    pg.wait_for_timeout(2500)
    print("EDIT URL:", pg.url)
    return pg


def form_state(pg):
    declared = DECL in pg.inner_text("body")
    sched, when = False, ""
    try:
        sched = pg.locator(".ant-radio-wrapper").filter(has_text="定时发布").first.locator("input").is_checked()
    except Exception:
        pass
    try:
        when = pg.locator("input[placeholder='选择日期时间']").first.input_value()
    except Exception:
        pass
    btns = [b.strip() for b in pg.evaluate(
        "()=>[...document.querySelectorAll('button,[class*=button],[class*=btn]')]"
        ".map(e=>(e.innerText||'').trim()).filter(t=>t&&t.length<10)") if b.strip()]
    return declared, sched, when, sorted(set(btns))


def set_declare(pg):
    sel = pg.locator(".ant-select").filter(has_text="为作品添加补充说明").first
    if sel.count() == 0:
        sel = pg.locator(".ant-select").filter(has_text=DECL).first
    if sel.count() == 0:
        print("!! 找不到作者声明控件")
        return False
    sel.click()
    pg.wait_for_timeout(1200)
    opt = pg.locator(".ant-select-item-option").filter(has_text=DECL).first
    if opt.count() == 0:
        pg.keyboard.press("Escape")
        print("!! 声明选项未出现")
        return False
    opt.click()
    pg.wait_for_timeout(1000)
    return True


def run(ctx, mode, kw):
    pg = open_editor(ctx, ctx.new_page(), kw)
    if pg is None:
        return "NO_ITEM"
    declared, sched, when, btns = form_state(pg)
    print("  已声明=%s 定时=%s 时间=%r" % (declared, sched, when))
    print("  按钮=", btns)
    if mode == "dry":
        print("  SELECTS=", pg.evaluate(
            "()=>[...document.querySelectorAll('.ant-select')].map(e=>(e.innerText||'').trim().replace(/\\n/g,'|'))")) 
        print("  DECLTXT=", pg.evaluate(
            "()=>[...document.querySelectorAll('body *')].filter(e=>!e.childElementCount&&(e.innerText||'').trim().length<30&&(e.innerText||'').includes('声明')).map(e=>e.innerText.trim())"))
        return "DRY"
    if declared:
        print("  SKIP: 已有 AI 声明")
        return "SKIP"
    if not set_declare(pg):
        return "NO_CTRL"
    declared2, sched2, when2, _ = form_state(pg)
    print("  声明后: 已声明=%s 定时=%s 时间=%r" % (declared2, sched2, when2))
    if not declared2 or (sched and when2 != when):
        print("  !! 状态不符预期，放弃保存")
        return "ABORT"
    save = None
    for lab in ["保存", "提交", "确认发布", "发布"]:
        loc = pg.locator("button").filter(has_text=lab).first
        if loc.count() and loc.is_visible():
            save = lab
            break
    if not save:
        print("  !! 找不到保存按钮，放弃")
        return "NO_SAVE_BTN"
    pg.locator("button").filter(has_text=save).first.click()
    pg.wait_for_timeout(4000)
    for lab in ["确认", "确定", "继续"]:
        try:
            loc = pg.locator(".ant-modal button, button").filter(has_text=lab).first
            if loc.is_visible():
                loc.click(timeout=2500)
                pg.wait_for_timeout(2500)
                break
        except Exception:
            pass
    print("  SAVED via:", save, "| URL:", pg.url)
    body = pg.inner_text("body")
    print("  HIT:", [k for k in ["成功", "待发布", "失败", "审核"] if k in body])
    pg.screenshot(path="output/videos/_ks_decl_fix.png", full_page=True)
    return "SAVED"


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "dry"
    kw = sys.argv[2]
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        base = set(ctx.pages)
        try:
            print(mode, kw, "->", run(ctx, mode, kw))
        finally:
            for x in [y for y in ctx.pages if y not in base]:
                try:
                    x.close()
                except Exception:
                    pass
            b.close()


if __name__ == "__main__":
    main()
