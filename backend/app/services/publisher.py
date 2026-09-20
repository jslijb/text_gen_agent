import os
import json
import time
import random
import logging
import asyncio
from datetime import datetime, date
from pathlib import Path
from app.config.settings import settings

logger = logging.getLogger(__name__)

# 真实浏览器 User-Agent 轮换池
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
]

# 反爬检测关键词（页面出现这些则判定为触发反爬）
ANTICRAWL_MARKERS = ["验证码", "滑动验证", "安全验证", "操作频繁", "账号异常", "请稍后再试", "登录已过期", "访问被拒绝"]

# 发布节流参数（spec 5.4.1 + design 1.3.5）
MIN_PUBLISH_INTERVAL_SECONDS = 300  # 单章最小发布间隔 5 分钟
MAX_DAILY_PUBLISH_COUNT = 10        # 每日最大发布章节数 10


def _encrypt_data(data: str) -> str:
    """AES-256-GCM 加密（符合 design 1.3.5 要求）"""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import base64
    import os as _os
    # 密钥派生为 32 字节（AES-256）
    raw_key = settings.COOKIE_ENCRYPTION_KEY.encode("utf-8")
    key = raw_key[:32].ljust(32, b"0")
    aesgcm = AESGCM(key)
    nonce = _os.urandom(12)  # GCM 推荐 12 字节 nonce
    ciphertext = aesgcm.encrypt(nonce, data.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def _decrypt_data(encrypted: str) -> str:
    """AES-256-GCM 解密"""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import base64
    raw_key = settings.COOKIE_ENCRYPTION_KEY.encode("utf-8")
    key = raw_key[:32].ljust(32, b"0")
    aesgcm = AESGCM(key)
    blob = base64.urlsafe_b64decode(encrypted.encode("ascii"))
    nonce, ciphertext = blob[:12], blob[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")


class Publisher:
    _instance = None
    _cookie_path = None
    _state_path = None  # 发布节流状态文件
    _browser = None
    _antircawl_paused_until = 0  # 反爬暂停截止时间戳

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cookie_path = Path(settings.COOKIES_DIR) / "baidu_cookies.json"
            cls._instance._state_path = Path(settings.COOKIES_DIR) / ".publish_state.json"
        return cls._instance

    # ---------- Cookie 加密存储 ----------
    def save_cookies(self, cookies: list[dict]):
        data = json.dumps(cookies)
        encrypted = _encrypt_data(data)
        self._cookie_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._cookie_path, "w", encoding="utf-8") as f:
            f.write(encrypted)
        logger.info("Cookie已加密保存(AES-256-GCM)")

    def load_cookies(self) -> list[dict]:
        if not self._cookie_path.exists():
            return []
        try:
            with open(self._cookie_path, "r", encoding="utf-8") as f:
                encrypted = f.read()
            data = _decrypt_data(encrypted)
            return json.loads(data)
        except Exception as e:
            logger.error(f"Cookie加载失败: {e}")
            return []

    def check_cookie_valid(self) -> bool:
        cookies = self.load_cookies()
        if not cookies:
            return False
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(user_agent=random.choice(USER_AGENTS))
                context.add_cookies(cookies)
                page = context.new_page()
                page.goto("https://zuojia.baidu.com", timeout=15000)
                current_url = page.url
                browser.close()
                return "login" not in current_url.lower()
        except Exception as e:
            logger.error(f"Cookie验证失败: {e}")
            return False

    def open_login_browser(self, timeout_seconds: int = 300) -> dict:
        """同步打开浏览器等待用户登录，由 Celery worker 调用（避免 API 线程被回收）。
        返回 {"success": bool, "message": str, "cookie_count": int}
        """
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            try:
                context = browser.new_context(user_agent=random.choice(USER_AGENTS))
                page = context.new_page()
                page.goto("https://zuojia.baidu.com", timeout=30000)
                logger.info("已打开浏览器，等待用户手动登录...")
                # 等待登录成功：URL 仍是 zuojia.baidu.com 且不含 login
                deadline = time.time() + timeout_seconds
                while time.time() < deadline:
                    current_url = page.url
                    if "zuojia.baidu.com" in current_url and "login" not in current_url.lower():
                        # 二次确认：等待 2 秒后再次检查，避免跳转中途
                        time.sleep(2)
                        if "login" not in page.url.lower():
                            break
                    time.sleep(1)
                else:
                    return {"success": False, "message": "登录超时", "cookie_count": 0}

                cookies = context.cookies()
                if not cookies:
                    return {"success": False, "message": "未获取到 Cookie", "cookie_count": 0}
                self.save_cookies(cookies)
                logger.info(f"登录成功，Cookie已保存({len(cookies)}条)")
                return {"success": True, "message": "登录成功", "cookie_count": len(cookies)}
            finally:
                browser.close()

    # ---------- 发布节流（间隔 + 每日总量） ----------
    def _load_state(self) -> dict:
        if not self._state_path.exists():
            return {"last_publish_ts": 0, "daily_count": 0, "daily_date": ""}
        try:
            with open(self._state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"last_publish_ts": 0, "daily_count": 0, "daily_date": ""}

    def _save_state(self, state: dict):
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._state_path, "w", encoding="utf-8") as f:
            json.dump(state, f)

    def _check_and_update_throttle(self) -> tuple[bool, str]:
        """检查发布节流：返回 (是否允许, 原因)"""
        # 反爬暂停期
        if time.time() < self._antircawl_paused_until:
            wait = int(self._antircawl_paused_until - time.time())
            return False, f"反爬暂停中，请等待{wait}秒后再试"
        state = self._load_state()
        today = date.today().isoformat()
        # 跨天重置计数
        if state.get("daily_date") != today:
            state["daily_count"] = 0
            state["daily_date"] = today
        # 每日总量
        if state.get("daily_count", 0) >= MAX_DAILY_PUBLISH_COUNT:
            return False, f"今日已发布{MAX_DAILY_PUBLISH_COUNT}章，达到每日上限"
        # 发布间隔
        elapsed = time.time() - state.get("last_publish_ts", 0)
        if elapsed < MIN_PUBLISH_INTERVAL_SECONDS:
            wait = int(MIN_PUBLISH_INTERVAL_SECONDS - elapsed)
            return False, f"发布间隔不足5分钟，请等待{wait}秒"
        return True, ""

    def _mark_published(self):
        state = self._load_state()
        today = date.today().isoformat()
        if state.get("daily_date") != today:
            state["daily_count"] = 0
            state["daily_date"] = today
        state["daily_count"] = state.get("daily_count", 0) + 1
        state["last_publish_ts"] = time.time()
        self._save_state(state)

    # ---------- 反爬检测 ----------
    @staticmethod
    def _detect_anticrawl(page) -> bool:
        """检测当前页面是否触发反爬"""
        try:
            body_text = page.inner_text("body", timeout=2000)
            for marker in ANTICRAWL_MARKERS:
                if marker in body_text:
                    return True
        except Exception:
            pass
        return False

    def _trigger_anticrawl_pause(self, duration_seconds: int = 1800):
        """触发反爬暂停（默认30分钟）"""
        self._antircawl_paused_until = time.time() + duration_seconds
        logger.error(f"检测到反爬限制，暂停所有发布任务{duration_seconds}秒")

    # ---------- 鼠标轨迹模拟 ----------
    @staticmethod
    def _human_mouse_move(page, target_x: float, target_y: float):
        """模拟人类鼠标移动轨迹：随机折线 + 多步移动"""
        try:
            current = page.evaluate("() => ({x: window.scrollX, y: window.scrollY})")
            start_x = random.uniform(100, 400)
            start_y = random.uniform(100, 300)
            # 生成 3-5 个中间随机点
            steps = random.randint(3, 5)
            for i in range(steps):
                ratio = (i + 1) / steps
                mid_x = start_x + (target_x - start_x) * ratio + random.uniform(-30, 30)
                mid_y = start_y + (target_y - start_y) * ratio + random.uniform(-30, 30)
                page.mouse.move(mid_x, mid_y, steps=random.randint(5, 15))
                time.sleep(random.uniform(0.05, 0.15))
            page.mouse.move(target_x, target_y, steps=random.randint(5, 10))
            time.sleep(random.uniform(0.1, 0.3))
        except Exception as e:
            logger.debug(f"鼠标轨迹模拟失败(非致命): {e}")

    @staticmethod
    def _random_sleep(a: float = 2.0, b: float = 5.0):
        time.sleep(random.uniform(a, b))

    # ---------- 发布主流程 ----------
    def publish_chapter(self, project_name: str, chapter_title: str, chapter_content: str, is_first: bool = False, synopsis: str = "", genre: str = "") -> dict:
        # 节流检查
        allowed, reason = self._check_and_update_throttle()
        if not allowed:
            logger.warning(f"发布被节流拒绝: {reason}")
            return {"success": False, "error": reason, "throttled": True}

        cookies = self.load_cookies()
        if not cookies:
            return {"success": False, "error": "Cookie不存在，请先登录百度账号"}

        from playwright.sync_api import sync_playwright
        browser = None
        screenshot_path = None
        try:
            with sync_playwright() as p:
                # 有头模式更接近真人，不易被检测（design 1.3.5 反爬策略）
                browser = p.chromium.launch(headless=False)
                self.__class__._browser = browser  # 修复原死代码：赋值以便截图
                ua = random.choice(USER_AGENTS)
                context = browser.new_context(
                    user_agent=ua,
                    viewport={"width": 1280, "height": 800},
                    locale="zh-CN",
                    timezone_id="Asia/Shanghai",
                )
                # 注入反检测脚本（隐藏 webdriver 标记）
                context.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                )
                context.add_cookies(cookies)
                page = context.new_page()

                logger.info(f"开始发布章节[{chapter_title}]，UA={ua[:40]}...")
                page.goto("https://zuojia.baidu.com", timeout=30000)
                self._random_sleep()

                # 反爬检测
                if self._detect_anticrawl(page):
                    self._trigger_anticrawl_pause()
                    return {"success": False, "error": "检测到反爬限制，已暂停发布30分钟", "anticrawl": True}

                if is_first:
                    # 首次发布：创建作品
                    page.click("text=开始创作", timeout=10000)
                    self._random_sleep(1, 3)
                    # 鼠标轨迹模拟移动到作品名称输入框
                    self._human_mouse_move(page, 400, 300)
                    page.fill('input[placeholder*="作品名称"]', project_name, timeout=10000)
                    self._random_sleep(0.5, 1.5)
                    if synopsis:
                        page.fill('textarea[placeholder*="简介"]', synopsis[:200], timeout=10000)
                    self._random_sleep(0.5, 1.5)
                    if genre:
                        try:
                            page.click(f"text={genre}", timeout=5000)
                            self._random_sleep(0.3, 0.8)
                        except Exception:
                            logger.debug(f"题材[{genre}]选择失败，跳过")
                else:
                    # 日更：进入已有作品
                    self._human_mouse_move(page, 400, 300)
                    page.click(f"text={project_name}", timeout=10000)
                    self._random_sleep(1, 3)

                # 填写章节正文
                self._human_mouse_move(page, 640, 400)
                page.fill('textarea, [contenteditable="true"]', chapter_content[:5000], timeout=10000)
                self._random_sleep(2, 5)

                # 反爬检测（填写后再次检查）
                if self._detect_anticrawl(page):
                    self._trigger_anticrawl_pause()
                    screenshot_path = Path(settings.COOKIES_DIR) / f"anticrawl_{int(time.time())}.png"
                    page.screenshot(path=str(screenshot_path))
                    return {"success": False, "error": "提交前检测到反爬限制，已截图保存", "anticrawl": True, "screenshot": str(screenshot_path)}

                # 点击投稿
                self._human_mouse_move(page, 640, 600)
                page.click("text=投稿", timeout=10000)
                self._random_sleep(2, 5)

                # 再次反爬检测
                if self._detect_anticrawl(page):
                    self._trigger_anticrawl_pause()
                    screenshot_path = Path(settings.COOKIES_DIR) / f"anticrawl_{int(time.time())}.png"
                    page.screenshot(path=str(screenshot_path))
                    return {"success": False, "error": "投稿后检测到反爬限制，已截图保存", "anticrawl": True, "screenshot": str(screenshot_path)}

                # 保存新 Cookie
                new_cookies = context.cookies()
                self.save_cookies(new_cookies)
                browser.close()
                self.__class__._browser = None

                # 标记发布成功（更新节流计数）
                self._mark_published()
                logger.info(f"章节[{chapter_title}]发布成功")
                return {"success": True, "message": f"章节'{chapter_title}'发布成功"}
        except Exception as e:
            logger.error(f"发布失败: {e}", exc_info=True)
            # 修复原死代码：截图保存现场
            try:
                if browser is not None:
                    screenshot_path = Path(settings.COOKIES_DIR) / f"error_{int(time.time())}.png"
                    page = context.new_page() if 'context' in dir() and context else None
                    if page is None and 'page' in dir():
                        page = page
                    # 尝试对当前页面截图
                    if browser.contexts:
                        ctx = browser.contexts[0]
                        if ctx.pages:
                            ctx.pages[-1].screenshot(path=str(screenshot_path))
                            logger.info(f"已保存错误截图: {screenshot_path}")
            except Exception as screenshot_err:
                logger.debug(f"截图保存失败: {screenshot_err}")
            return {"success": False, "error": str(e)}
        finally:
            self.__class__._browser = None
