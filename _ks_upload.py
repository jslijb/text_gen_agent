# -*- coding: utf-8 -*-
"""快手代发：上传视频（真实 Chrome，CDP 9222）。

用法： python _ks_upload.py <video_path>
只做：选文件 -> 等上传 -> 打印表单状态 + 截图。不发布。
"""
import sys
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:9222"
PUB = "https://cp.kuaishou.com/article/publish/video"
VIDEO = sys.argv[1] if len(sys.argv) > 1 else r"D:\Python\text_gen_agent\output\videos\山海经夸父_AI漫剧版.mp4"


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
        if "publish/video" not in pg.url:
            pg.goto(PUB, wait_until="domcontentloaded")
            pg.wait_for_timeout(2500)

        # 选文件（隐藏 input 也可以 set）
        fi = pg.locator("input[type=file]").first
        print("setting file:", VIDEO)
        fi.set_input_files(VIDEO, timeout=20000)
        print("file set, waiting for upload...")

        # 轮询等待：textarea 出现（进入编辑表单）或出现错误
        ok = False
        for i in range(120):  # 最多 240s
            pg.wait_for_timeout(2000)
            state = pg.evaluate(
                """() => {
                const body = document.body.innerText || '';
                return {
                    hasDesc: !!document.querySelector('#work-description-edit'),
                    hasUploadFailed: body.includes('上传失败'),
                    hasReupload: body.includes('重新上传'),
                    hasProgress: body.includes('上传中'),
                };
            }"""
            )
            if i % 3 == 0:
                print(i, state)
            if state["hasUploadFailed"]:
                print("!! UPLOAD FAILED")
                break
            if state["hasDesc"] and not state["hasProgress"]:
                ok = True
                print("form ready at", i)
                break
        pg.screenshot(path="output/videos/_ks_after_upload.png", full_page=True)
        print("UPLOAD_OK" if ok else "NOT_READY")
        print("TEXT:", pg.inner_text("body")[:1200].replace("\n", " | "))
        b.close()


if __name__ == "__main__":
    main()
