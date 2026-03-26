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

logger = setup_logger("twitter_browser")

COOKIE_FILE = "/app/data/twitter_cookies.json"
HOME_URL = "https://x.com/home"
LOGIN_URL = "https://x.com/i/flow/login"
COMPOSE_URL = "https://x.com/compose/post"
TWEET_URL_RE = re.compile(r"/([^/]+)/status/(\d+)")
CURRENT_USER_SELECTORS = [
    "a[data-testid='AppTabBar_Profile_Link']",
    "a[aria-label*='Profile']",
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


class TwitterBrowser:
    def __init__(self):
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self._lock = asyncio.Lock()
        self._mention_detail_semaphore = asyncio.Semaphore(2)
        self._in_reply_to_cache: dict[str, tuple[str | None, float]] = {}
        self.cookies_file = COOKIE_FILE
        self._browser_major_version = "146"

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
        if "we found more than one account" in body_text:
            return "X 要求进一步确认账号身份：检测到多个候选账号。"
        if "suspicious login prevented" in body_text:
            return "X 阻止了本次可疑登录，请先在网页端人工完成验证。"
        return None

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

    async def _ensure_context(self):
        if self.context is not None:
            return

        executable_path = settings.browser_executable_path if os.path.exists(settings.browser_executable_path) else None
        logger.info("启动 BrowserEngine，browser=%s, proxy=%s", executable_path or "bundled", settings.proxy_url or "无")
        self.playwright = await async_playwright().start()
        launch_kwargs: dict[str, Any] = {
            "headless": settings.browser_headless,
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
        self.context = await self.browser.new_context(
            viewport={"width": 1440, "height": 1024},
            locale="en-US",
            user_agent=self._build_user_agent(),
            extra_http_headers={
                "sec-ch-ua": f'"Chromium";v="{major}", "Google Chrome";v="{major}", "Not=A?Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Linux"',
            },
        )
        cookies = self._cookie_entries_from_file()
        if cookies:
            await self.context.add_cookies(cookies)

    @asynccontextmanager
    async def _page_session(self):
        await self._ensure_context()
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

    async def _maybe_fill_login_step(self, page: Page, selector: str, value: str | None, button_text: str):
        if not value:
            return
        locator = page.locator(selector).first
        if await locator.count() == 0:
            return
        try:
            await locator.wait_for(state="visible", timeout=4_000)
        except PlaywrightTimeoutError:
            return
        await locator.click()
        with suppress(Exception):
            await locator.press("Control+A")
            await locator.press("Backspace")
        await locator.fill("")
        await locator.press_sequentially(value, delay=35)
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

        button = page.locator("button:visible, div[role='button']:visible").filter(
            has_text=re.compile(button_text, re.I)
        ).first
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
                if await button.count():
                    with suppress(Exception):
                        await button.click()
                with suppress(Exception):
                    await locator.press("Enter")
            response = await response_info.value
        except PlaywrightTimeoutError:
            response = None
        if response is not None:
            error = await self._extract_onboarding_response_error(response)
            if error:
                raise RuntimeError(error)
        await self._wait_for_ready(page)

    async def login(self, username: str, email: str, password: str) -> str:
        async with self._lock:
            async with self._page_session() as page:
                await self._goto(page, LOGIN_URL)
                await self._maybe_fill_login_step(page, "input[autocomplete='username'], input[name='text']", username, "next")
                login_error = await self._extract_login_error(page)
                if login_error:
                    raise RuntimeError(login_error)
                await self._maybe_fill_login_step(page, "input[data-testid='ocfEnterTextTextInput'], input[name='text']", email, "next")
                login_error = await self._extract_login_error(page)
                if login_error:
                    raise RuntimeError(login_error)

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
                await password_locator.fill(password)
                login_button = page.get_by_role("button", name=re.compile("log in", re.I)).first
                await login_button.click()
                await page.wait_for_url(re.compile(r"x\.com/(home|i/.*|[^/]+$)"), timeout=settings.browser_timeout_ms)
                await self._wait_for_ready(page)

                if not await self._is_logged_in(page):
                    raise RuntimeError("Browser 模式登录后仍未进入已登录状态")

                username_now = await self._extract_current_username(page)
                await self._save_auth_cookies(page, username_now or username)
                return username_now or username

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
                resolution_limit = min(len(items), 5)
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
