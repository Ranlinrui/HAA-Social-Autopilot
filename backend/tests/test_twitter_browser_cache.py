import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

from app.services.twitter_browser import TwitterBrowser, _CACHE_MISS, _extract_graphql_error


class TwitterBrowserCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_cached_in_reply_to_returns_stored_value(self):
        browser = TwitterBrowser()
        browser._store_in_reply_to("123", "456", ttl_seconds=60)

        self.assertEqual(browser._get_cached_in_reply_to("123"), "456")

    async def test_get_cached_in_reply_to_expires_entry(self):
        browser = TwitterBrowser()
        browser._store_in_reply_to("123", "456", ttl_seconds=-1)

        self.assertIs(browser._get_cached_in_reply_to("123"), _CACHE_MISS)
        self.assertNotIn("123", browser._in_reply_to_cache)

    async def test_resolve_in_reply_to_fresh_page_uses_cache(self):
        browser = TwitterBrowser()
        browser._store_in_reply_to("123", "456", ttl_seconds=60)

        @asynccontextmanager
        async def fail_page_session():
            raise AssertionError("page session should not be opened for cached entries")
            yield

        browser._page_session = fail_page_session

        result = await browser._resolve_in_reply_to_fresh_page("123")

        self.assertEqual(result, "456")

    async def test_resolve_in_reply_to_fresh_page_stores_result(self):
        browser = TwitterBrowser()
        browser._resolve_in_reply_to = AsyncMock(return_value="789")

        @asynccontextmanager
        async def fake_page_session():
            yield object()

        browser._page_session = fake_page_session

        result = await browser._resolve_in_reply_to_fresh_page("123")

        self.assertEqual(result, "789")
        self.assertEqual(browser._get_cached_in_reply_to("123"), "789")
        browser._resolve_in_reply_to.assert_awaited_once()

    async def test_extract_graphql_error_returns_message_and_code(self):
        payload = {
            "data": {},
            "errors": [
                {
                    "code": 226,
                    "message": "Authorization: This request looks like it might be automated.",
                }
            ],
        }

        self.assertEqual(
            _extract_graphql_error(payload),
            "Authorization: This request looks like it might be automated. [226]",
        )

    async def test_assert_authenticated_action_raises_login_error_when_not_logged_in(self):
        browser = TwitterBrowser()
        page = object()
        browser._has_error_page = AsyncMock(return_value=False)
        browser._is_logged_in = AsyncMock(return_value=False)
        browser._extract_login_error = AsyncMock(return_value="X 当前拒绝此次登录请求：Could not log you in now. Please try again later.")
        browser._get_visible_body_excerpt = AsyncMock(return_value="")

        with self.assertRaisesRegex(RuntimeError, "登录请求"):
            await browser._assert_authenticated_action(page, "发帖")

    async def test_assert_authenticated_action_returns_username_for_valid_session(self):
        browser = TwitterBrowser()
        page = object()
        browser._has_error_page = AsyncMock(return_value=False)
        browser._is_logged_in = AsyncMock(return_value=True)
        browser._assert_account_available = AsyncMock()
        browser._extract_current_username = AsyncMock(return_value="cookie_user")

        username = await browser._assert_authenticated_action(
            page,
            "回复",
            require_account_available=True,
            require_username=True,
        )

        self.assertEqual(username, "cookie_user")
        browser._assert_account_available.assert_awaited_once()



if __name__ == "__main__":
    unittest.main()
