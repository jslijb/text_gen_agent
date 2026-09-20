"""
独立登录脚本（由 API 进程通过 subprocess.Popen 启动）。

原因：Playwright 在 Celery worker 子进程中报 NotImplementedError
（Windows ProactorEventLoop 在子进程中不支持 subprocess_exec），
导致浏览器进程根本无法启动。独立子进程不受 Celery event loop 限制。

用法：python -m app.services.login_runner --timeout 300
状态写入 {COOKIES_DIR}/.login_status.json 供 API 查询。
"""
import sys
import os
import time
import json
import random
import argparse
import logging
from pathlib import Path
from datetime import datetime

# 确保能导入 app 模块（cwd=backend 时可直接导入）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("login_runner")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
]

LOGIN_URL = "https://zuojia.baidu.com"


def write_status(status_path: Path, status: str, message: str, cookie_count: int = 0):
    """写入登录状态文件，供 API 端点轮询查询"""
    status_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "status": status,  # pending / success / failed
        "message": message,
        "cookie_count": cookie_count,
        "updated_at": datetime.now().isoformat(),
    }
    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"[登录状态] {status}: {message} (cookies={cookie_count})")


def main():
    parser = argparse.ArgumentParser(description="百度作家平台登录脚本（独立子进程）")
    parser.add_argument("--timeout", type=int, default=300, help="登录超时秒数（默认300）")
    args = parser.parse_args()

    try:
        from app.services.publisher import Publisher  # 复用加密存储逻辑
        from app.config.settings import settings
    except Exception as e:
        logger.error(f"导入 app 模块失败（请确保 cwd=backend）: {e}", exc_info=True)
        # 无法写入状态文件（不知道路径），只能退出
        sys.exit(2)

    status_path = Path(settings.COOKIES_DIR) / ".login_status.json"
    write_status(status_path, "pending", "正在启动浏览器...")
    logger.info(f"登录脚本启动，超时 {args.timeout} 秒")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        write_status(status_path, "failed", f"Playwright 未安装: {e}")
        logger.error(f"Playwright 未安装: {e}")
        sys.exit(1)

    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(user_agent=random.choice(USER_AGENTS))
            page = context.new_page()
            page.goto(LOGIN_URL, timeout=30000)
            write_status(status_path, "pending", "浏览器已打开，请在弹出的窗口中手动登录百度账号")
            logger.info("已打开浏览器，等待用户手动登录...")

            deadline = time.time() + args.timeout
            logged_in = False
            while time.time() < deadline:
                try:
                    current_url = page.url
                except Exception:
                    # 页面/浏览器被用户关闭
                    logger.warning("浏览器可能已被关闭")
                    break
                if "zuojia.baidu.com" in current_url and "login" not in current_url.lower():
                    # 二次确认：等待 2 秒后再次检查，避免跳转中途
                    time.sleep(2)
                    try:
                        if "login" not in page.url.lower():
                            logged_in = True
                            break
                    except Exception:
                        break
                time.sleep(1)

            if not logged_in:
                write_status(status_path, "failed", "登录超时或浏览器已关闭")
                logger.warning("登录超时或浏览器已关闭")
                return

            cookies = context.cookies()
            if not cookies:
                write_status(status_path, "failed", "未获取到 Cookie")
                logger.warning("未获取到 Cookie")
                return

            publisher = Publisher()
            publisher.save_cookies(cookies)
            write_status(status_path, "success", "登录成功，Cookie 已加密保存", cookie_count=len(cookies))
            logger.info(f"登录成功，Cookie 已加密保存 ({len(cookies)} 条)")
    except Exception as e:
        write_status(status_path, "failed", f"登录异常: {e}")
        logger.error(f"登录异常: {e}", exc_info=True)
        sys.exit(1)
    finally:
        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
