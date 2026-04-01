import asyncio
import json
import mimetypes
import os
import re
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List
from urllib.parse import quote

from playwright.async_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    Playwright,
    Response,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from app.config import settings
from app.logger import setup_logger
from app.models.tweet import Tweet
from app.services.twitter_account_store import (
    get_account_browser_storage_file,
    get_account_cookie_file,
    get_effective_account_key,
)

logger = setup_logger("twitter_browser")

COOKIE_FILE = "/app/data/twitter_cookies.json"
LOGIN_DIAGNOSTIC_FILE = "/app/data/twitter_browser_login_diagnostic.json"
HOME_URL = "https://x.com/home"
LOGIN_URL = "https://x.com/i/flow/login"
COMPOSE_URL = "https://x.com/compose/post"
TWEET_URL_RE = re.compile(r"/([^/]+)/status/(\d+)")
CURRENT_USER_SELECTORS = [
    "a[data-testid='AppTabBar_Profile_Link']",
    "a[aria-label*='Profile']",
    "button[data-testid='SideNav_AccountSwitcher_Button'] a[href^='/']",
    "div[data-testid='SideNav_AccountSwitcher_Button'] a[href^='/']",
    "a[data-testid='AppTabBar_More_Menu'] ~ div a[href^='/']",
]


_CACHE_MISS = object()


def _compact_number_to_int(value: str | None) -> int:
    if not value:
        return 0
    raw = value.strip().replace(",", "")
    if not raw:
        return 0
    multiplier = 1
    if raw.endswith("K"):
        raw = raw[:-1]
        multiplier = 1_000
    elif raw.endswith("M"):
        raw = raw[:-1]
        multiplier = 1_000_000
    elif raw.endswith("B"):
        raw = raw[:-1]
        multiplier = 1_000_000_000
    try:
        return int(float(raw) * multiplier)
    except ValueError:
        return 0


def _extract_tweet_id_from_url(value: str | None) -> str | None:
    if not value:
        return None
    match = TWEET_URL_RE.search(value)
    return match.group(2) if match else None


def _extract_username_from_url(value: str | None) -> str | None:
    if not value:
        return None
    match = TWEET_URL_RE.search(value)
    return match.group(1) if match else None


def _extract_first_tweet_id(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("rest_id", "id_str", "tweet_id"):
            value = payload.get(key)
            if isinstance(value, str) and value.isdigit():
                return value
        for value in payload.values():
            found = _extract_first_tweet_id(value)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _extract_first_tweet_id(item)
            if found:
                return found
    return None


def _extract_graphql_error(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    errors = payload.get("errors")
    if not isinstance(errors, list) or not errors:
        return None
    first = errors[0] if isinstance(errors[0], dict) else None
    if not first:
        return None
    message = str(first.get("message") or "").strip()
    code = first.get("code")
    if message and code is not None:
        return f"{message} [{code}]"
    return message or None


def _extract_onboarding_error(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    errors = payload.get("errors")
    if not isinstance(errors, list) or not errors:
        return None
    first = errors[0] if isinstance(errors[0], dict) else None
    if not first:
        return None
    message = str(first.get("message") or "").strip()
    code = first.get("code")
    if message and code is not None:
        return f"{message} [{code}]"
    return message or None


def _normalize_tweet_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _parse_created_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _select_login_challenge_value(page_text: str, username: str, email: str) -> str:
    lowered = (page_text or "").lower()
    normalized_username = (username or "").strip()
    normalized_email = (email or "").strip()

    if "phone number or username" in lowered or "username or phone number" in lowered:
        return normalized_username or normalized_email
    if "email" in lowered:
        return normalized_email or normalized_username
    if "username" in lowered:
        return normalized_username or normalized_email
    return normalized_email or normalized_username


def _detect_login_prompt_kind(page_text: str) -> str:
    lowered = (page_text or "").lower()

    if (
        "phone, email, or username" in lowered
        or "sign in to x" in lowered
        or "sign in to twitter" in lowered
    ):
        return "identifier"

    if (
        "phone number or username" in lowered
        or "username or phone number" in lowered
        or "confirm your email" in lowered
        or "enter your email" in lowered
        or "enter your phone number" in lowered
        or "enter your username" in lowered
        or "check your email" in lowered
        or "check your phone" in lowered
        or "we found more than one account" in lowered
    ):
        return "challenge"

    if "enter your password" in lowered or "password" in lowered:
        return "password"

    return "unknown"


def _build_button_text_patterns(button_text: str) -> list[re.Pattern[str]]:
    normalized = (button_text or "").strip().lower()
    variants: list[str] = [normalized]

    if normalized == "next":
        variants.extend(["verify", "continue"])
    elif normalized == "log in":
        variants.extend(["sign in", "next"])

    seen: set[str] = set()
    patterns: list[re.Pattern[str]] = []
    for item in variants:
        candidate = item.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        patterns.append(re.compile(rf"^\s*{re.escape(candidate)}\s*$", re.I))
    return patterns


def _mask_login_value(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if "@" in raw:
        local, _, domain = raw.partition("@")
        masked_local = local[:2] + "*" * max(len(local) - 2, 0)
        return f"{masked_local}@{domain}"
    if len(raw) <= 4:
        return "*" * len(raw)
    return raw[:2] + "*" * (len(raw) - 4) + raw[-2:]


class TwitterBrowser:
    def __init__(self):
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self._lock = asyncio.Lock()
        self._mention_detail_semaphore = asyncio.Semaphore(2)
        self._in_reply_to_cache: dict[str, tuple[str | None, float]] = {}
        self.cookies_file = COOKIE_FILE
        self.storage_state_file = get_account_browser_storage_file("default")
        self.login_diagnostic_file = LOGIN_DIAGNOSTIC_FILE
        self._browser_major_version = "146"
        self._current_account_key = "default"
        self._current_headless = settings.browser_headless
        self._manual_login_page: Page | None = None
        self._manual_login_account_key: str | None = None
        self._manual_login_email: str | None = None

    async def _handle_route(self, route):
        request = route.request
        resource_type = request.resource_type
        url = request.url.lower()

        blocked_domains = (
            "analytics.twitter.com",
            "static.ads-twitter.com",
            "google-analytics.com",
            "doubleclick.net",
        )
        if any(domain in url for domain in blocked_domains):
            await route.abort()
            return

        if settings.browser_low_traffic_mode:
            if settings.browser_block_images and resource_type == "image":
                await route.abort()
                return
            if settings.browser_block_media and resource_type == "media":
                await route.abort()
                return
            if settings.browser_block_fonts and resource_type == "font":
                await route.abort()
                return

        await route.continue_()

    def _is_manual_login_active(self) -> bool:
        page = self._manual_login_page
        return bool(page is not None and not page.is_closed())

    async def close(self):
        self._in_reply_to_cache.clear()
        if self.context is not None:
            await self.context.close()
            self.context = None
        if self.browser is not None:
            await self.browser.close()
            self.browser = None
        if self.playwright is not None:
            await self.playwright.stop()
            self.playwright = None
        self._current_account_key = "default"
        self._current_headless = settings.browser_headless
        self._manual_login_page = None
        self._manual_login_account_key = None
        self._manual_login_email = None

    def _cookie_entries_from_file(self) -> list[dict[str, Any]]:
        if not os.path.exists(self.cookies_file):
            return []
        try:
            raw = json.loads(Path(self.cookies_file).read_text())
        except Exception as exc:
            logger.warning("读取浏览器 cookie 文件失败: %s", exc)
            return []

        auth_token = raw.get("auth_token")
        ct0 = raw.get("ct0")
        if not auth_token or not ct0:
            return []

        cookies = []
        for domain in (".x.com", ".twitter.com"):
            cookies.append({
                "name": "auth_token",
                "value": auth_token,
                "domain": domain,
                "path": "/",
                "secure": True,
                "httpOnly": True,
                "sameSite": "Lax",
            })
            cookies.append({
                "name": "ct0",
                "value": ct0,
                "domain": domain,
                "path": "/",
                "secure": True,
                "httpOnly": False,
                "sameSite": "Lax",
            })
        return cookies

    def _build_user_agent(self) -> str:
        major = self._browser_major_version or "146"
        return (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36"
        )

    async def _get_visible_body_text(self, page: Page) -> str:
        with suppress(Exception):
            return ((await page.locator("body").inner_text()) or "").lower()
        return ""

    async def _get_visible_body_excerpt(self, page: Page, limit: int = 280) -> str:
        with suppress(Exception):
            text = ((await page.locator("body").inner_text()) or "").strip()
            if text:
                compact = re.sub(r"\s+", " ", text)
                return compact[:limit]
        return ""

    async def _log_login_snapshot(self, page: Page, label: str):
        with suppress(Exception):
            stage = await self._detect_login_stage(page)
            excerpt = await self._get_visible_body_excerpt(page, limit=220)
            logger.info(
                "Browser 登录阶段=%s, label=%s, url=%s, excerpt=%s",
                stage,
                label,
                page.url,
                excerpt or "<empty>",
            )

    async def _write_login_diagnostic(
        self,
        page: Page | None,
        *,
        label: str,
        username: str,
        email: str,
        error: str | None = None,
    ):
        stage = "unknown"
        url = ""
        excerpt = ""
        if page is not None:
            with suppress(Exception):
                stage = await self._detect_login_stage(page)
            with suppress(Exception):
                url = page.url
            with suppress(Exception):
                excerpt = await self._get_visible_body_excerpt(page, limit=400)
        payload = {
            "label": label,
            "stage": stage,
            "url": url,
            "excerpt": excerpt,
            "username": _mask_login_value(username),
            "email": _mask_login_value(email),
            "error": (error or "").strip(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            os.makedirs(os.path.dirname(self.login_diagnostic_file), exist_ok=True)
            Path(self.login_diagnostic_file).write_text(json.dumps(payload, indent=2))
            logger.info("Browser 登录诊断已写入: %s", self.login_diagnostic_file)
        except Exception as diag_exc:
            logger.warning("写入 Browser 登录诊断失败: %s", diag_exc)

    async def _recycle_context(self, reason: str, *, preserve_manual_login: bool = False):
        logger.info("回收 Browser 上下文: reason=%s", reason)
        if self.context is not None:
            with suppress(Exception):
                await self.context.close()
            self.context = None
        if self.browser is not None:
            with suppress(Exception):
                await self.browser.close()
            self.browser = None
        if self.playwright is not None:
            with suppress(Exception):
                await self.playwright.stop()
        self.playwright = None
        self._current_account_key = "default"
        self._current_headless = settings.browser_headless
        if not preserve_manual_login:
            self._manual_login_page = None
            self._manual_login_account_key = None
            self._manual_login_email = None

    async def _has_error_page(self, page: Page) -> bool:
        error_container = page.locator(".errorContainer").first
        with suppress(Exception):
            if await error_container.count() and await error_container.is_visible():
                container_text = ((await error_container.inner_text()) or "").lower()
                return (
                    "javascript is not available" in container_text
                    or "supported browsers" in container_text
                    or "enable javascript" in container_text
                )
        body_text = await self._get_visible_body_text(page)
        if body_text:
            return (
                "javascript is not available" in body_text
                or "supported browsers" in body_text
                or "enable javascript" in body_text
            )
        return False

    async def _is_account_suspended(self, page: Page) -> bool:
        body_text = await self._get_visible_body_text(page)
        return "your account is suspended" in body_text

    async def _assert_account_available(self, page: Page):
        if await self._is_account_suspended(page):
            raise RuntimeError(
                "Browser 账号状态受限：当前首页显示 Your account is suspended，账号暂时不可用于搜索、发帖、回复和引用。"
            )

    async def _assert_authenticated_action(
        self,
        page: Page,
        action_name: str,
        *,
        require_account_available: bool = True,
        require_username: bool = False,
    ) -> str | None:
        if await self._has_error_page(page):
            raise RuntimeError(
                f"Browser {action_name}失败：当前会话被 X 返回为 JavaScript 错误页，请重新导入 Cookie 或更换浏览器环境。"
            )
        if not await self._is_logged_in(page):
            login_error = await self._extract_login_error(page)
            if login_error:
                raise RuntimeError(f"Browser {action_name}失败：{login_error}")
            page_excerpt = await self._get_visible_body_excerpt(page, limit=240)
            if page_excerpt:
                raise RuntimeError(
                    f"Browser {action_name}失败：当前未处于已登录状态。页面内容: {page_excerpt}"
                )
            raise RuntimeError(f"Browser 模式未登录，无法{action_name}，请先导入 Cookie 或执行浏览器登录")

        if require_account_available:
            await self._assert_account_available(page)

        username = await self._extract_current_username(page)
        if require_username and not username:
            raise RuntimeError(f"Browser {action_name}失败：已登录，但未识别到当前账号")
        return username

    async def _assert_no_search_page_error(self, page: Page):
        body_text = await self._get_visible_body_text(page)
        if "something went wrong. try reloading." in body_text:
            raise RuntimeError("Browser 搜索页加载失败：X 返回 Something went wrong. Try reloading.")

    async def _assert_no_mentions_page_error(self, page: Page):
        body_text = await self._get_visible_body_text(page)
        if "something went wrong. try reloading." in body_text:
            raise RuntimeError("Browser 提及页加载失败：X 返回 Something went wrong. Try reloading.")

    async def _assert_no_read_page_error(self, page: Page, action_name: str):
        body_text = await self._get_visible_body_text(page)
        if "something went wrong. try reloading." in body_text:
            raise RuntimeError(f"Browser {action_name}失败：X 页面返回 Something went wrong. Try reloading.")
        if "this account doesn’t exist" in body_text or "this account doesn't exist" in body_text:
            raise RuntimeError(f"Browser {action_name}失败：目标账号不存在或当前无法访问该账号页面。")
        if "this post was deleted" in body_text or "post unavailable" in body_text or "this page doesn’t exist" in body_text or "this page doesn't exist" in body_text:
            raise RuntimeError(f"Browser {action_name}失败：目标推文不存在、已删除，或当前页面不可访问。")

    async def _extract_login_error(self, page: Page) -> str | None:
        body_text = await self._get_visible_body_text(page)
        if "could not log you in now. please try again later." in body_text:
            return "X 当前拒绝此次登录请求：Could not log you in now. Please try again later."
        if "enter your phone number or username" in body_text:
            return "X 要求额外账号验证：请输入 phone number 或 username。"
        if "enter your username" in body_text:
            return "X 要求额外账号验证：请输入 username。"
        if "check your email" in body_text:
            return "X 要求额外账号验证：请先确认邮箱验证码或邮箱确认流程。"
        if "check your phone" in body_text:
            return "X 要求额外账号验证：请先确认手机验证码或手机确认流程。"
        if "we found more than one account" in body_text:
            return "X 要求进一步确认账号身份：检测到多个候选账号。"
        if "suspicious login prevented" in body_text:
            return "X 阻止了本次可疑登录，请先在网页端人工完成验证。"
        return None

    async def _detect_login_stage(self, page: Page) -> str:
        password_locator = page.locator("input[name='password']").first
        with suppress(Exception):
            if await password_locator.count():
                await password_locator.wait_for(state="attached", timeout=500)
                return "password"

        username_locator = page.locator("input[autocomplete='username'], input[name='text']").first
        body_text = await self._get_visible_body_text(page)
        with suppress(Exception):
            if await username_locator.count():
                prompt_kind = _detect_login_prompt_kind(body_text)
                if prompt_kind in {"identifier", "challenge"}:
                    return prompt_kind
                return "text_input"

        if await self._is_logged_in(page):
            return "logged_in"

        if await self._extract_login_error(page):
            return "error"

        prompt_kind = _detect_login_prompt_kind(body_text)
        if prompt_kind != "unknown":
            return prompt_kind
        return "unknown"

    async def _extract_onboarding_response_error(self, response: Response) -> str | None:
        if response.status < 400:
            return None
        try:
            payload = await response.json()
        except Exception:
            payload = None
        message = _extract_onboarding_error(payload)
        if message:
            lowered = message.lower()
            if "could not log you in now" in lowered:
                return f"X 当前拒绝此次登录请求：{message}"
            return f"X 登录接口返回错误：{message}"
        try:
            text = (await response.text()).strip()
        except Exception:
            text = ""
        if text:
            return f"X 登录接口返回错误：HTTP {response.status} {text[:300]}"
        return f"X 登录接口返回错误：HTTP {response.status}"

    async def _ensure_context(self, *, headless: bool | None = None):
        manual_login_active = self._is_manual_login_active() or bool(self._manual_login_account_key)
        active_account_key = await get_effective_account_key()
        normalized_account_key = (
            self._manual_login_account_key
            if manual_login_active and self._manual_login_account_key
            else active_account_key or "default"
        )
        target_cookie_file = get_account_cookie_file(normalized_account_key)
        target_storage_state_file = get_account_browser_storage_file(normalized_account_key)
        if manual_login_active:
            target_headless = False
        else:
            target_headless = settings.browser_headless if headless is None else headless

        if self.context is not None:
            if (
                self._current_account_key == normalized_account_key
                and self.cookies_file == target_cookie_file
                and self.storage_state_file == target_storage_state_file
                and self._current_headless == target_headless
            ):
                return
            await self._recycle_context("account_switched", preserve_manual_login=manual_login_active)

        self._current_account_key = normalized_account_key
        self.cookies_file = target_cookie_file
        self.storage_state_file = target_storage_state_file
        self._current_headless = target_headless

        executable_path = settings.browser_executable_path if os.path.exists(settings.browser_executable_path) else None
        logger.info("启动 BrowserEngine，browser=%s, proxy=%s", executable_path or "bundled", settings.proxy_url or "无")
        self.playwright = await async_playwright().start()
        launch_kwargs: dict[str, Any] = {
            "headless": target_headless,
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        }
        if executable_path:
            launch_kwargs["executable_path"] = executable_path
        if settings.proxy_url:
            launch_kwargs["proxy"] = {"server": settings.proxy_url}

        self.browser = await self.playwright.chromium.launch(**launch_kwargs)
        version = getattr(self.browser, "version", None)
        if callable(version):
            try:
                version = version()
            except Exception:
                version = None
        if isinstance(version, str) and version:
            self._browser_major_version = version.split(".", 1)[0] or self._browser_major_version
        major = self._browser_major_version
        context_kwargs: dict[str, Any] = {
            "viewport": {"width": 1440, "height": 1024},
            "locale": "en-US",
            "user_agent": self._build_user_agent(),
            "extra_http_headers": {
                "sec-ch-ua": f'"Chromium";v="{major}", "Google Chrome";v="{major}", "Not=A?Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Linux"',
            },
        }
        if os.path.exists(self.storage_state_file):
            context_kwargs["storage_state"] = self.storage_state_file
        self.context = await self.browser.new_context(**context_kwargs)
        await self.context.route("**/*", self._handle_route)
        await self.context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'platform', { get: () => 'Linux x86_64' });
            Object.defineProperty(navigator, 'plugins', {
              get: () => [{ name: 'Chrome PDF Plugin' }, { name: 'Chrome PDF Viewer' }, { name: 'Native Client' }]
            });
            window.chrome = window.chrome || { runtime: {} };
            Object.defineProperty(Notification, 'permission', { get: () => 'default' });
            """
        )
        cookies = self._cookie_entries_from_file()
        if cookies:
            await self.context.add_cookies(cookies)

    async def _save_storage_state(self):
        if self.context is None:
            return
        os.makedirs(os.path.dirname(self.storage_state_file), exist_ok=True)
        await self.context.storage_state(path=self.storage_state_file)

    @asynccontextmanager
    async def _page_session(self, *, headless: bool | None = None):
        if self._is_manual_login_active():
            raise RuntimeError("当前正在人工接管登录，普通 Browser 操作已暂停，请先完成或关闭人工接管")
        await self._ensure_context(headless=headless)
        assert self.context is not None
        page = await self.context.new_page()
        page.set_default_timeout(settings.browser_timeout_ms)
        try:
            yield page
        finally:
            with suppress(Exception):
                await page.close()

    async def _wait_for_ready(self, page: Page, wait_for_networkidle: bool = True):
        await page.wait_for_load_state("domcontentloaded")
        if wait_for_networkidle:
            with suppress(PlaywrightTimeoutError):
                await page.wait_for_load_state("networkidle", timeout=10_000)

    async def _goto(self, page: Page, url: str, wait_for_networkidle: bool = True):
        await page.goto(url, wait_until="domcontentloaded")
        await self._wait_for_ready(page, wait_for_networkidle=wait_for_networkidle)

    async def _human_pause(self, page: Page, min_ms: int = 250, max_ms: int = 700):
        upper = max(min_ms, max_ms)
        await page.wait_for_timeout(upper)

    async def _human_pre_click(self, page: Page, locator: Locator):
        with suppress(Exception):
            box = await locator.bounding_box()
            if box:
                target_x = box["x"] + min(max(box["width"] * 0.45, 8), max(box["width"] - 8, 8))
                target_y = box["y"] + min(max(box["height"] * 0.5, 8), max(box["height"] - 8, 8))
                await page.mouse.move(target_x, target_y, steps=12)
        await self._human_pause(page, 180, 420)

    async def _extract_current_username(self, page: Page) -> str | None:
        for selector in CURRENT_USER_SELECTORS:
            locator = page.locator(selector).first
            try:
                if await locator.count():
                    href = await locator.get_attribute("href")
                    if href:
                        return href.strip("/").split("/")[0]
            except Exception:
                continue

        with suppress(Exception):
            href = await page.evaluate(
                r"""
                () => {
                  const anchors = [...document.querySelectorAll('a[href^="/"]')]
                  for (const anchor of anchors) {
                    const href = anchor.getAttribute('href') || ''
                    if (/^\/[A-Za-z0-9_]{1,32}$/.test(href) && !href.includes('/status/')) {
                      return href
                    }
                  }
                  return null
                }
                """
            )
            if href:
                return str(href).strip("/")
        return None

    async def _is_logged_in(self, page: Page) -> bool:
        if await self._has_error_page(page):
            return False
        if "login" in page.url or "flow/login" in page.url:
            return False
        if await page.locator("input[name='password']").count():
            return False
        if await page.locator("input[autocomplete='username']").count():
            return False
        username = await self._extract_current_username(page)
        return bool(username)

    async def _save_auth_cookies(self, page: Page, account_name: str | None = None):
        assert self.context is not None
        cookies = await self.context.cookies()
        cookie_map = {item["name"]: item["value"] for item in cookies}
        auth_token = cookie_map.get("auth_token")
        ct0 = cookie_map.get("ct0")
        if not auth_token or not ct0:
            raise RuntimeError("Browser 模式登录完成，但未提取到 auth_token/ct0")

        payload = {
            "auth_token": auth_token,
            "ct0": ct0,
            "account_name": account_name or await self._extract_current_username(page) or "default",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "is_valid": True,
            "validation_mode": "browser",
        }
        os.makedirs(os.path.dirname(self.cookies_file), exist_ok=True)
        Path(self.cookies_file).write_text(json.dumps(payload, indent=2))
        await self._save_storage_state()

    async def _maybe_fill_login_step(self, page: Page, selector: str, value: str | None, button_text: str) -> bool:
        if not value:
            return False
        previous_stage = await self._detect_login_stage(page)
        previous_excerpt = await self._get_visible_body_excerpt(page, limit=220)
        logger.info(
            "Browser 登录提交步骤: stage=%s, selector=%s, button=%s, value=%s",
            previous_stage,
            selector,
            button_text,
            _mask_login_value(value),
        )
        locator = page.locator(selector).first
        if await locator.count() == 0:
            return False
        try:
            await locator.wait_for(state="visible", timeout=4_000)
        except PlaywrightTimeoutError:
            return False
        await locator.click()
        await self._human_pause(page, 120, 260)
        with suppress(Exception):
            await locator.press("Control+A")
            await locator.press("Backspace")
        await locator.fill("")
        await locator.press_sequentially(value, delay=55)
        with suppress(Exception):
            current_value = await locator.input_value()
            if (current_value or "").strip() != value.strip():
                await locator.evaluate(
                    """(node, inputValue) => {
                        node.focus();
                        node.value = inputValue;
                        node.dispatchEvent(new Event('input', { bubbles: true }));
                        node.dispatchEvent(new Event('change', { bubbles: true }));
                    }""",
                    value,
                )

        button_candidates: list[Locator] = []
        for button_pattern in _build_button_text_patterns(button_text):
            button_candidates.extend([
                page.get_by_role("button", name=button_pattern).first,
                page.locator("button:visible").filter(has_text=button_pattern).first,
                page.locator("div[role='button']:visible").filter(has_text=button_pattern).first,
            ])
        response = None
        try:
            async with page.expect_response(
                lambda resp: (
                    "onboarding/task.json" in resp.url
                    and "flow_name=login" not in resp.url
                    and resp.request.method == "POST"
                ),
                timeout=10_000,
            ) as response_info:
                clicked = False
                for button in button_candidates:
                    with suppress(Exception):
                        if await button.count():
                            await self._human_pre_click(page, button)
                            await button.click()
                            clicked = True
                            break
                with suppress(Exception):
                    await self._human_pause(page, 200, 380)
                    await locator.press("Enter")
                if not clicked:
                    with suppress(Exception):
                        await self._human_pause(page, 200, 380)
                        await page.keyboard.press("Enter")
            response = await response_info.value
        except PlaywrightTimeoutError:
            response = None
        if response is not None:
            error = await self._extract_onboarding_response_error(response)
            if error:
                raise RuntimeError(error)
        await self._wait_for_ready(page)
        deadline = asyncio.get_running_loop().time() + 12
        while asyncio.get_running_loop().time() < deadline:
            current_stage = await self._detect_login_stage(page)
            if current_stage != previous_stage:
                await self._log_login_snapshot(page, f"{button_text}_advanced")
                return True
            current_excerpt = await self._get_visible_body_excerpt(page, limit=220)
            if current_excerpt and current_excerpt != previous_excerpt:
                await self._log_login_snapshot(page, f"{button_text}_content_changed")
                return True
            error = await self._extract_login_error(page)
            if error:
                raise RuntimeError(error)
            await page.wait_for_timeout(250)
        await self._log_login_snapshot(page, f"{button_text}_stalled")
        return False

    async def login(self, username: str, email: str, password: str) -> str:
        async with self._lock:
            if username:
                self.cookies_file = get_account_cookie_file(username)
                self.storage_state_file = get_account_browser_storage_file(username)
            async with self._page_session() as page:
                try:
                    logger.info(
                        "Browser 登录开始: username=%s, email=%s, proxy=%s",
                        _mask_login_value(username),
                        _mask_login_value(email),
                        settings.proxy_url or "无",
                    )
                    await self._goto(page, LOGIN_URL)
                    await self._human_pause(page, 500, 900)
                    await self._log_login_snapshot(page, "after_goto_login")
                    primary_identifier = (username or "").strip() or (email or "").strip()
                    identifier_advanced = await self._maybe_fill_login_step(
                        page,
                        "input[autocomplete='username'], input[name='text']",
                        primary_identifier,
                        "next",
                    )
                    await self._log_login_snapshot(page, "after_identifier_step")
                    login_error = await self._extract_login_error(page)
                    if login_error:
                        raise RuntimeError(login_error)
                    if not identifier_advanced:
                        login_stage = await self._detect_login_stage(page)
                        if login_stage in {"identifier", "text_input"}:
                            page_excerpt = await self._get_visible_body_excerpt(page, limit=400)
                            if page_excerpt:
                                raise RuntimeError(
                                    f"Browser 登录第一步提交后页面未继续。当前页面内容: {page_excerpt}"
                                )
                            raise RuntimeError("Browser 登录第一步提交后页面未继续，请检查代理/IP 环境或 X 登录页结构变化。")
                    challenge_text = await self._get_visible_body_excerpt(page, limit=500)
                    challenge_value = _select_login_challenge_value(challenge_text, username, email)
                    challenge_advanced = await self._maybe_fill_login_step(
                        page,
                        "input[data-testid='ocfEnterTextTextInput'], input[name='text']",
                        challenge_value,
                        "next",
                    )
                    if not challenge_advanced:
                        alternate_value = ""
                        normalized_username = (username or "").strip()
                        normalized_email = (email or "").strip()
                        if challenge_value == normalized_email:
                            alternate_value = normalized_username
                        elif challenge_value == normalized_username:
                            alternate_value = normalized_email
                        if alternate_value and alternate_value != challenge_value:
                            challenge_advanced = await self._maybe_fill_login_step(
                                page,
                                "input[data-testid='ocfEnterTextTextInput'], input[name='text']",
                                alternate_value,
                                "next",
                            )
                    await self._log_login_snapshot(page, "after_challenge_step")
                    login_error = await self._extract_login_error(page)
                    if login_error:
                        raise RuntimeError(login_error)
                    if not challenge_advanced:
                        login_stage = await self._detect_login_stage(page)
                        if login_stage in {"challenge", "text_input"}:
                            page_excerpt = await self._get_visible_body_excerpt(page, limit=400)
                            if page_excerpt:
                                raise RuntimeError(
                                    f"Browser 登录账号确认步骤未继续。当前页面内容: {page_excerpt}"
                                )
                            raise RuntimeError("Browser 登录账号确认步骤未继续，请检查 X 额外校验流程或当前代理/IP 环境。")

                    password_locator = page.locator("input[name='password']").first
                    try:
                        await password_locator.wait_for(state="visible", timeout=20_000)
                    except PlaywrightTimeoutError as exc:
                        login_error = await self._extract_login_error(page)
                        if login_error:
                            raise RuntimeError(login_error) from exc
                        page_excerpt = await self._get_visible_body_excerpt(page, limit=400)
                        if page_excerpt:
                            raise RuntimeError(
                                f"Browser 登录未进入密码输入步骤。当前页面内容: {page_excerpt}。这通常表示 X 额外要求账号确认、页面结构变化，或当前代理/IP 环境触发了拦截。"
                            ) from exc
                        raise RuntimeError("Browser 登录未进入密码输入步骤，请检查账号校验流程、代理/IP 环境，或直接改用 Cookie 登录") from exc
                    await self._human_pause(page, 300, 650)
                    await password_locator.fill(password)
                    login_button = page.get_by_role("button", name=re.compile("log in", re.I)).first
                    login_response = None
                    try:
                        async with page.expect_response(
                            lambda resp: "onboarding/task.json" in resp.url and resp.request.method == "POST",
                            timeout=10_000,
                        ) as response_info:
                            await self._human_pre_click(page, login_button)
                            await login_button.click()
                        login_response = await response_info.value
                    except PlaywrightTimeoutError:
                        await self._human_pre_click(page, login_button)
                        await login_button.click()
                    if login_response is not None:
                        error = await self._extract_onboarding_response_error(login_response)
                        if error:
                            raise RuntimeError(error)
                    try:
                        await page.wait_for_url(re.compile(r"x\.com/(home|i/.*|[^/]+$)"), timeout=settings.browser_timeout_ms)
                    except PlaywrightTimeoutError as exc:
                        await self._log_login_snapshot(page, "after_login_submit_timeout")
                        login_error = await self._extract_login_error(page)
                        if login_error:
                            raise RuntimeError(login_error) from exc
                        page_excerpt = await self._get_visible_body_excerpt(page, limit=400)
                        if page_excerpt:
                            raise RuntimeError(f"Browser 登录后未进入已登录页面。当前页面内容: {page_excerpt}") from exc
                        raise RuntimeError("Browser 登录后未进入已登录页面，请检查账号风控状态、代理/IP 环境或额外校验流程。") from exc
                    await self._wait_for_ready(page)
                    await self._log_login_snapshot(page, "after_login_success_navigation")

                    if not await self._is_logged_in(page):
                        await self._log_login_snapshot(page, "after_login_not_logged_in")
                        raise RuntimeError("Browser 模式登录后仍未进入已登录状态")

                    username_now = await self._extract_current_username(page)
                    logger.info(
                        "Browser 登录成功: current_username=%s, url=%s",
                        username_now or "<unknown>",
                        page.url,
                    )
                    await self._save_auth_cookies(page, username_now or username)
                    return username_now or username
                except Exception as exc:
                    await self._write_login_diagnostic(
                        page,
                        label="login_failed",
                        username=username,
                        email=email,
                        error=str(exc),
                    )
                    lowered = str(exc).lower()
                    if "could not log you in now" in lowered or "[399]" in lowered:
                        await self._recycle_context("login_399")
                    raise

    async def start_manual_login(self, username: str, email: str | None = None) -> dict[str, Any]:
        async with self._lock:
            normalized_username = (username or "").strip().lstrip("@")
            if not normalized_username:
                raise RuntimeError("启动人工接管登录失败：用户名不能为空")

            self.cookies_file = get_account_cookie_file(normalized_username)
            self.storage_state_file = get_account_browser_storage_file(normalized_username)
            self._manual_login_account_key = normalized_username
            self._manual_login_email = (email or "").strip() or None

            await self._ensure_context(headless=False)
            assert self.context is not None

            page = self._manual_login_page
            if page is None or page.is_closed():
                page = await self.context.new_page()
                page.set_default_timeout(settings.browser_timeout_ms)
                self._manual_login_page = page

            await self._goto(page, LOGIN_URL, wait_for_networkidle=False)
            await self._human_pause(page, 300, 600)
            with suppress(Exception):
                await page.bring_to_front()
            with suppress(Exception):
                await page.evaluate("window.focus()")
            return {
                "ready": os.path.exists(self.storage_state_file),
                "manual_login_active": True,
                "username": normalized_username,
                "account_key": normalized_username,
            }

    async def complete_manual_login(self) -> dict[str, Any]:
        async with self._lock:
            page = self._manual_login_page
            if page is None or page.is_closed():
                raise RuntimeError("当前没有可完成的人工接管登录会话，请先启动人工接管浏览器")

            await self._wait_for_ready(page, wait_for_networkidle=False)
            if not await self._is_logged_in(page):
                login_error = await self._extract_login_error(page)
                if login_error:
                    raise RuntimeError(login_error)
                page_excerpt = await self._get_visible_body_excerpt(page, limit=260)
                if page_excerpt:
                    raise RuntimeError(f"人工接管登录尚未完成。当前页面内容: {page_excerpt}")
                raise RuntimeError("人工接管登录尚未完成，请先在远程浏览器中完成登录")

            username_now = await self._extract_current_username(page)
            account_name = username_now or self._manual_login_account_key or "default"
            await self._save_auth_cookies(page, account_name)
            with suppress(Exception):
                await page.close()
            self._manual_login_page = None
            self._manual_login_account_key = None
            self._manual_login_email = None
            return {
                "ready": True,
                "manual_login_active": False,
                "username": username_now or account_name,
                "account_key": account_name,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

    async def cancel_manual_login(self):
        async with self._lock:
            if self._manual_login_page is not None and not self._manual_login_page.is_closed():
                with suppress(Exception):
                    await self._manual_login_page.close()
            self._manual_login_page = None
            self._manual_login_account_key = None
            self._manual_login_email = None

    def get_manual_login_status(self) -> dict[str, Any]:
        active = self._is_manual_login_active()
        return {
            "manual_login_active": active,
            "username": self._manual_login_account_key,
            "account_key": self._manual_login_account_key,
        }

    async def sync_session(self) -> str:
        async with self._lock:
            async with self._page_session() as page:
                await self._goto(page, HOME_URL)
                username = await self._assert_authenticated_action(
                    page,
                    "同步 Browser 会话",
                    require_account_available=False,
                    require_username=True,
                )
                await self._save_auth_cookies(page, username)
                return username or "unknown"

    def get_session_status(self, account_key: str | None = None) -> dict[str, Any]:
        target_file = (
            get_account_browser_storage_file(account_key)
            if account_key is not None
            else self.storage_state_file
        )
        exists = os.path.exists(target_file)
        updated_at = None
        if exists:
            with suppress(OSError):
                updated_at = datetime.fromtimestamp(
                    os.path.getmtime(target_file),
                    tz=timezone.utc,
                ).isoformat()
        return {
            "ready": exists,
            "storage_state_file": target_file,
            "updated_at": updated_at,
        }

    async def ensure_authenticated_page(self) -> Page:
        async with self._page_session() as page:
            await self._goto(page, HOME_URL)
            if not await self._is_logged_in(page):
                raise RuntimeError("Browser 模式未登录，请先导入 cookie 或执行浏览器登录")
            return page

    async def test_connection(self) -> str:
        async with self._lock:
            async with self._page_session() as page:
                await self._goto(page, HOME_URL)
                username = await self._assert_authenticated_action(
                    page,
                    "连接测试",
                    require_account_available=True,
                    require_username=True,
                )
                await self._save_auth_cookies(page, username)
                return username

    async def check_session_health(self) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []

        async def run_check(name: str, action):
            try:
                result = await action()
                checks.append({
                    "name": name,
                    "ok": True,
                    "detail": result,
                })
            except Exception as exc:
                checks.append({
                    "name": name,
                    "ok": False,
                    "detail": str(exc),
                })

        await run_check("home", self.test_connection)
        await run_check("search", lambda: self._check_search_health())
        await run_check("mentions", lambda: self._check_mentions_health())

        ok = all(item["ok"] for item in checks)
        return {
            "ok": ok,
            "summary": "Browser 会话健康检查通过" if ok else "Browser 会话部分异常，请查看各项检查结果",
            "checks": checks,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _check_search_health(self) -> str:
        results = await self.search_tweets(
            "bitcoin",
            count=max(1, settings.browser_health_check_search_count),
        )
        return f"搜索可用，返回 {len(results)} 条结果"

    async def _check_mentions_health(self) -> str:
        mentions = await self.get_mentions(
            count=max(1, settings.browser_health_check_mentions_count),
        )
        return f"提及页可用，读取到 {len(mentions)} 条记录"

    async def _wait_for_tweet_response(self, page: Page, click_callback):
        async with page.expect_response(lambda resp: "CreateTweet" in resp.url and resp.request.method == "POST", timeout=settings.browser_timeout_ms) as response_info:
            await click_callback()
        response = await response_info.value
        if response.status >= 400:
            raise RuntimeError(f"Browser 发帖请求失败: HTTP {response.status}")
        payload = await response.json()
        graphql_error = _extract_graphql_error(payload)
        if graphql_error:
            raise RuntimeError(f"Browser 发帖失败: {graphql_error}")
        tweet_id = _extract_first_tweet_id(payload)
        if not tweet_id:
            raise RuntimeError("Browser 发帖成功但未识别 tweet id")
        return tweet_id

    async def _wait_for_retweet_response(self, page: Page, click_callback):
        async with page.expect_response(
            lambda resp: (
                resp.request.method == "POST"
                and any(token in resp.url for token in ("CreateRetweet", "retweet", "Retweet"))
            ),
            timeout=settings.browser_timeout_ms,
        ) as response_info:
            await click_callback()
        response = await response_info.value
        if response.status >= 400:
            raise RuntimeError(f"Browser 转推请求失败: HTTP {response.status}")
        return response

    async def _upload_media_files(self, page: Page, media_paths: Iterable[str]):
        paths = [str(Path(item)) for item in media_paths if item]
        if not paths:
            return
        file_input = page.locator("input[data-testid='fileInput']").first
        await file_input.set_input_files(paths)
        attachments = page.locator("div[data-testid='attachments']").first
        with suppress(PlaywrightTimeoutError):
            await attachments.wait_for(state="visible", timeout=60_000)
        with suppress(PlaywrightTimeoutError):
            await page.locator("[role='progressbar']").first.wait_for(state="hidden", timeout=60_000)
        await page.wait_for_timeout(1_500)

    async def _get_active_compose_surface(self, page: Page) -> Locator:
        dialog = page.locator("div[role='dialog']").filter(has=page.locator("[data-testid='tweetTextarea_0']:visible"))
        if await dialog.count():
            return dialog.last
        return page.locator("body")

    async def _fill_compose_text(self, composer: Locator, content: str):
        with suppress(Exception):
            await composer.scroll_into_view_if_needed()
        try:
            await composer.focus()
        except Exception:
            with suppress(Exception):
                await composer.evaluate("(node) => node.focus()")
        with suppress(Exception):
            await composer.evaluate(
                """(node) => {
                    node.focus();
                    if (node.isContentEditable) {
                        node.textContent = '';
                    } else {
                        node.value = '';
                    }
                }"""
            )
        with suppress(Exception):
            await composer.press("Control+A")
            await composer.press("Backspace")
        await composer.press_sequentially(content, delay=20)

    async def _wait_for_reply_appearance(self, page: Page, current_username: str, content: str, timeout_ms: int | None = None) -> str:
        timeout_ms = timeout_ms or settings.browser_timeout_ms
        deadline = asyncio.get_running_loop().time() + (timeout_ms / 1000)
        target_text = _normalize_tweet_text(content)
        while asyncio.get_running_loop().time() < deadline:
            with suppress(Exception):
                await page.locator("div[role='dialog']").last.press("Escape")
            items = await self._collect_tweet_cards(page, 20, max_rounds=2, pause_ms=700, scroll=False)
            for item in items:
                if item.get("author_username", "").lower() != current_username.lower():
                    continue
                item_text = _normalize_tweet_text(item.get("text", ""))
                if item_text == target_text or target_text in item_text:
                    return item["id"]
            await page.wait_for_timeout(1200)
            with suppress(Exception):
                await page.reload(wait_until="domcontentloaded")
                await page.locator("article[data-testid='tweet']").first.wait_for(state="visible", timeout=15_000)
        raise RuntimeError("Browser 回复已提交，但未在线程中确认到新回复")

    async def _submit_compose(self, page: Page, composer: Locator):
        with suppress(Exception):
            await composer.focus()
        await page.keyboard.press("Control+Enter")

    async def publish_tweet(self, tweet: Tweet) -> str:
        media_paths = [media.filepath for media in tweet.media_items] if tweet.media_items else []
        async with self._lock:
            async with self._page_session() as page:
                await self._goto(page, COMPOSE_URL)
                await self._assert_authenticated_action(page, "发帖")
                surface = await self._get_active_compose_surface(page)
                composer = surface.locator("[data-testid='tweetTextarea_0']:visible").last
                await composer.wait_for(state="visible", timeout=settings.browser_timeout_ms)
                await self._fill_compose_text(composer, tweet.content)
                await self._upload_media_files(page, media_paths)
                button = surface.locator("[data-testid='tweetButton']:visible, [data-testid='tweetButtonInline']:visible").last
                await button.wait_for(state="visible", timeout=settings.browser_timeout_ms)
                return await self._wait_for_tweet_response(page, lambda: self._submit_compose(page, composer))

    async def _open_tweet(self, page: Page, tweet_id_or_url: str):
        url = tweet_id_or_url if tweet_id_or_url.startswith("http") else f"https://x.com/i/web/status/{tweet_id_or_url}"
        await self._goto(page, url, wait_for_networkidle=False)
        try:
            await page.locator("article[data-testid='tweet']").first.wait_for(state="visible", timeout=settings.browser_timeout_ms)
        except PlaywrightTimeoutError as exc:
            await self._assert_no_read_page_error(page, "读取推文")
            page_excerpt = await self._get_visible_body_excerpt(page, limit=240)
            if page_excerpt:
                raise RuntimeError(f"Browser 读取推文失败：页面未出现推文内容。当前页面内容: {page_excerpt}") from exc
            raise RuntimeError("Browser 读取推文失败：页面未出现推文内容，可能是推文不存在、会话失效或 X 页面异常。") from exc

    async def reply_tweet(self, tweet_id: str, content: str) -> str:
        async with self._lock:
            async with self._page_session() as page:
                await self._open_tweet(page, tweet_id)
                current_username = await self._assert_authenticated_action(
                    page,
                    "回复",
                    require_account_available=True,
                    require_username=True,
                )
                await page.locator("article[data-testid='tweet'] [data-testid='reply']").first.click()
                surface = await self._get_active_compose_surface(page)
                composer = surface.locator("[data-testid='tweetTextarea_0']:visible").last
                await composer.wait_for(state="visible", timeout=settings.browser_timeout_ms)
                await self._fill_compose_text(composer, content)
                button = surface.locator("[data-testid='tweetButton']:visible, [data-testid='tweetButtonInline']:visible").last
                await button.wait_for(state="visible", timeout=settings.browser_timeout_ms)
                try:
                    return await self._wait_for_tweet_response(page, lambda: self._submit_compose(page, composer))
                except PlaywrightTimeoutError:
                    return await self._wait_for_reply_appearance(page, current_username, content)

    async def retweet_tweet(self, tweet_id: str) -> str:
        async with self._lock:
            async with self._page_session() as page:
                await self._open_tweet(page, tweet_id)
                await self._assert_authenticated_action(page, "转推")
                await page.locator("article[data-testid='tweet'] [data-testid='retweet']").first.click()
                confirm = page.locator("[data-testid='retweetConfirm']").first
                await confirm.wait_for(state="visible", timeout=settings.browser_timeout_ms)
                await self._wait_for_retweet_response(page, confirm.click)
                await page.wait_for_timeout(800)
                return tweet_id

    async def quote_tweet(self, tweet_url: str, content: str, media_paths: List[str] = []) -> str:
        async with self._lock:
            async with self._page_session() as page:
                await self._open_tweet(page, tweet_url)
                await self._assert_authenticated_action(page, "引用")
                await page.locator("article[data-testid='tweet'] [data-testid='retweet']").first.click()
                menu = page.locator("[role='menuitem']")
                await menu.first.wait_for(state="visible", timeout=settings.browser_timeout_ms)
                quote_item = menu.filter(has_text=re.compile(r"^quote$", re.I)).first
                await quote_item.wait_for(state="visible", timeout=settings.browser_timeout_ms)
                await quote_item.click()
                surface = await self._get_active_compose_surface(page)
                composer = surface.locator("[data-testid='tweetTextarea_0']:visible").last
                await composer.wait_for(state="visible", timeout=settings.browser_timeout_ms)
                await self._fill_compose_text(composer, content)
                await self._upload_media_files(page, media_paths)
                button = surface.locator("[data-testid='tweetButton']:visible, [data-testid='tweetButtonInline']:visible").last
                await button.wait_for(state="visible", timeout=settings.browser_timeout_ms)
                return await self._wait_for_tweet_response(page, lambda: self._submit_compose(page, composer))

    async def _collect_tweet_cards(
        self,
        page: Page,
        target_count: int,
        *,
        max_rounds: int = 8,
        pause_ms: int = 1_200,
        scroll: bool = True,
    ) -> list[dict[str, Any]]:
        articles: list[dict[str, Any]] = []
        previous_count = -1
        for _ in range(max_rounds):
            await page.wait_for_timeout(pause_ms)
            articles = await page.eval_on_selector_all(
                "article[data-testid='tweet']",
                r"""
                (nodes) => {
                  const parseCount = (value) => {
                    if (!value) return 0;
                    const raw = value.trim().replace(/,/g, '');
                    if (!raw) return 0;
                    let multiplier = 1;
                    let input = raw;
                    if (input.endsWith('K')) { input = input.slice(0, -1); multiplier = 1000; }
                    if (input.endsWith('M')) { input = input.slice(0, -1); multiplier = 1000000; }
                    if (input.endsWith('B')) { input = input.slice(0, -1); multiplier = 1000000000; }
                    const parsed = Number.parseFloat(input);
                    return Number.isFinite(parsed) ? Math.round(parsed * multiplier) : 0;
                  };
                  return nodes.map((article) => {
                    const statusLink = article.querySelector("a[href*='/status/']");
                    const href = statusLink ? statusLink.getAttribute('href') : null;
                    const textNodes = [...article.querySelectorAll("[data-testid='tweetText']")];
                    const userName = article.querySelector("div[data-testid='User-Name']");
                    const authorName = userName?.querySelector('span')?.textContent || '';
                    const usernameMatch = href ? href.match(/^\/([^/]+)\/status\/(\d+)/) : null;
                    const getCounter = (name) => parseCount(article.querySelector(`[data-testid='${name}']`)?.innerText || '0');
                    const socialContext = article.querySelector("div[data-testid='socialContext']")?.innerText || '';
                    const articleText = article.innerText || '';
                    return {
                      id: usernameMatch ? usernameMatch[2] : null,
                      url: href ? `https://x.com${href}` : null,
                      author_username: usernameMatch ? usernameMatch[1] : '',
                      author_name: authorName,
                      text: textNodes.map((node) => node.innerText).join('\n').trim(),
                      like_count: getCounter('like'),
                      retweet_count: getCounter('retweet'),
                      reply_count: getCounter('reply'),
                      view_count: getCounter('analytics'),
                      created_at: article.querySelector('time')?.getAttribute('datetime') || '',
                      is_pinned: socialContext.includes('Pinned') || articleText.includes('Pinned'),
                    };
                  }).filter((item) => item.id && item.author_username);
                }
                """,
            )
            if len(articles) >= target_count or len(articles) == previous_count:
                break
            previous_count = len(articles)
            if scroll:
                await page.mouse.wheel(0, 1800)
        return articles[:target_count]

    async def search_tweets(self, query: str, count: int = 20) -> List[dict]:
        async with self._lock:
            async with self._page_session() as page:
                search_url = f"https://x.com/search?q={quote(query)}&src=typed_query&f=top"
                await self._goto(page, search_url)
                await self._assert_authenticated_action(page, "搜索")
                await self._assert_no_search_page_error(page)
                await self._assert_no_read_page_error(page, "搜索")
                items = await self._collect_tweet_cards(page, count)
                return [{**item, "author_verified": False} for item in items]

    def _get_cached_in_reply_to(self, tweet_id: str) -> str | None | object:
        cached = self._in_reply_to_cache.get(tweet_id)
        if not cached:
            return _CACHE_MISS
        value, expires_at = cached
        if expires_at <= asyncio.get_running_loop().time():
            self._in_reply_to_cache.pop(tweet_id, None)
            return _CACHE_MISS
        return value

    def _store_in_reply_to(self, tweet_id: str, in_reply_to: str | None, ttl_seconds: int = 600):
        expires_at = asyncio.get_running_loop().time() + ttl_seconds
        self._in_reply_to_cache[tweet_id] = (in_reply_to, expires_at)

    async def _resolve_in_reply_to(self, page: Page, tweet_id: str) -> str | None:
        await self._open_tweet(page, tweet_id)
        thread_items = await self._collect_tweet_cards(page, 8, max_rounds=2, pause_ms=400, scroll=False)
        current_index = next((index for index, item in enumerate(thread_items) if item["id"] == tweet_id), -1)
        if current_index <= 0:
            return None
        parent = thread_items[current_index - 1]
        return parent.get("id")

    async def _resolve_in_reply_to_fresh_page(self, tweet_id: str) -> str | None:
        cached = self._get_cached_in_reply_to(tweet_id)
        if cached is not _CACHE_MISS:
            return cached
        async with self._mention_detail_semaphore:
            cached = self._get_cached_in_reply_to(tweet_id)
            if cached is not _CACHE_MISS:
                return cached
            async with self._page_session() as page:
                resolved = await self._resolve_in_reply_to(page, tweet_id)
                self._store_in_reply_to(tweet_id, resolved)
                return resolved

    async def get_mentions(self, count: int = 40) -> List[dict]:
        async with self._lock:
            async with self._page_session() as page:
                await self._goto(page, "https://x.com/notifications/mentions")
                await self._assert_authenticated_action(page, "读取提及")
                await self._assert_no_mentions_page_error(page)
                await self._assert_no_read_page_error(page, "读取提及")
                items = await self._collect_tweet_cards(page, count)
                mentions = []
                resolution_limit = min(
                    len(items),
                    max(0, settings.browser_mentions_reply_resolution_limit),
                )
                resolved_in_reply_to: list[str | None] = [None] * resolution_limit
                if resolution_limit:
                    results = await asyncio.gather(
                        *(self._resolve_in_reply_to_fresh_page(item["id"]) for item in items[:resolution_limit]),
                        return_exceptions=True,
                    )
                    for index, result in enumerate(results):
                        if not isinstance(result, Exception):
                            resolved_in_reply_to[index] = result
                for index, item in enumerate(items):
                    in_reply_to = resolved_in_reply_to[index] if index < resolution_limit else None
                    mentions.append({
                        "notification_id": item["id"],
                        "tweet_id": item["id"],
                        "tweet_text": item["text"],
                        "in_reply_to": in_reply_to,
                        "from_username": item["author_username"],
                        "from_user_id": None,
                        "from_user_name": item["author_name"],
                        "created_at": item["created_at"],
                        "created_at_datetime": _parse_created_at(item.get("created_at")),
                    })
                return mentions

    async def get_tweet_by_id(self, tweet_id: str) -> dict:
        async with self._lock:
            async with self._page_session() as page:
                await self._open_tweet(page, tweet_id)
                await self._assert_authenticated_action(page, "读取推文", require_account_available=False)
                await self._assert_no_read_page_error(page, "读取推文")
                items = await self._collect_tweet_cards(page, 3, max_rounds=2, pause_ms=400, scroll=False)
                item = next((entry for entry in items if entry["id"] == tweet_id), None)
                if not item:
                    raise RuntimeError(f"未找到推文 {tweet_id}")
                current_index = next((index for index, entry in enumerate(items) if entry["id"] == tweet_id), -1)
                in_reply_to = items[current_index - 1]["id"] if current_index > 0 else None
                self._store_in_reply_to(tweet_id, in_reply_to)
                return {
                    "id": item["id"],
                    "text": item["text"],
                    "in_reply_to": in_reply_to,
                    "author_username": item["author_username"],
                    "author_id": "",
                    "created_at": item["created_at"],
                    "created_at_datetime": _parse_created_at(item.get("created_at")),
                }

    async def get_user_profile(self, username: str) -> dict:
        async with self._lock:
            async with self._page_session() as page:
                await self._goto(page, f"https://x.com/{username}")
                await self._assert_authenticated_action(page, "读取用户资料", require_account_available=False)
                await self._assert_no_read_page_error(page, "读取用户资料")
                display_name = await page.evaluate(
                    """
                    () => {
                      const heading = document.querySelector("div[data-testid='UserName'] span")
                      return heading ? heading.textContent : null
                    }
                    """
                )
                return {
                    "id": username,
                    "username": username,
                    "name": display_name or username,
                }

    async def get_user_timeline(self, username: str, count: int = 5) -> List[dict]:
        async with self._lock:
            async with self._page_session() as page:
                await self._goto(page, f"https://x.com/{username}")
                await self._assert_authenticated_action(page, "读取用户时间线", require_account_available=False)
                await self._assert_no_read_page_error(page, "读取用户时间线")
                items = await self._collect_tweet_cards(page, max(count * 3, count + 5))
                filtered_items = [item for item in items if not item.get("is_pinned") and item.get("author_username", "").lower() == username.lower()][:count]
                for item in filtered_items:
                    item["created_at_datetime"] = _parse_created_at(item.get("created_at"))
                return filtered_items


_browser_instance: TwitterBrowser | None = None


async def get_twitter_browser() -> TwitterBrowser:
    global _browser_instance
    if _browser_instance is None:
        _browser_instance = TwitterBrowser()
    return _browser_instance


def reset_twitter_browser():
    global _browser_instance
    instance = _browser_instance
    _browser_instance = None
    if instance is not None:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(instance.close())
        except RuntimeError:
            pass


async def login_browser(username: str, email: str, password: str) -> str:
    browser = await get_twitter_browser()
    return await browser.login(username, email, password)


async def test_connection_browser() -> str:
    browser = await get_twitter_browser()
    return await browser.test_connection()


async def sync_browser_session() -> str:
    browser = await get_twitter_browser()
    return await browser.sync_session()


async def get_browser_session_status() -> dict[str, Any]:
    browser = await get_twitter_browser()
    account_key = await get_effective_account_key()
    return browser.get_session_status(account_key or "default")


async def start_manual_browser_login(username: str, email: str | None = None) -> dict[str, Any]:
    browser = await get_twitter_browser()
    return await browser.start_manual_login(username, email)


async def complete_manual_browser_login() -> dict[str, Any]:
    browser = await get_twitter_browser()
    return await browser.complete_manual_login()


async def cancel_manual_browser_login():
    browser = await get_twitter_browser()
    await browser.cancel_manual_login()


async def get_manual_browser_login_status() -> dict[str, Any]:
    browser = await get_twitter_browser()
    status = browser.get_manual_login_status()
    account_key = status.get("account_key") or await get_effective_account_key()
    session_status = browser.get_session_status(account_key or "default")
    return {**session_status, **status}


async def check_browser_session_health() -> dict[str, Any]:
    browser = await get_twitter_browser()
    return await browser.check_session_health()


async def publish_tweet_browser(tweet: Tweet) -> str:
    browser = await get_twitter_browser()
    return await browser.publish_tweet(tweet)


async def search_tweets_browser(query: str, count: int = 20) -> List[dict]:
    browser = await get_twitter_browser()
    return await browser.search_tweets(query, count)


async def reply_tweet_browser(tweet_id: str, content: str) -> str:
    browser = await get_twitter_browser()
    return await browser.reply_tweet(tweet_id, content)


async def retweet_tweet_browser(tweet_id: str) -> str:
    browser = await get_twitter_browser()
    return await browser.retweet_tweet(tweet_id)


async def quote_tweet_browser(tweet_url: str, content: str, media_paths: List[str] = []) -> str:
    browser = await get_twitter_browser()
    return await browser.quote_tweet(tweet_url, content, media_paths)


async def get_mentions_browser(count: int = 40) -> List[dict]:
    browser = await get_twitter_browser()
    return await browser.get_mentions(count)


async def get_tweet_by_id_browser(tweet_id: str) -> dict:
    browser = await get_twitter_browser()
    return await browser.get_tweet_by_id(tweet_id)


async def get_user_profile_browser(username: str) -> dict:
    browser = await get_twitter_browser()
    return await browser.get_user_profile(username)


async def get_user_timeline_browser(username: str, count: int = 5) -> List[dict]:
    browser = await get_twitter_browser()
    return await browser.get_user_timeline(username, count)
