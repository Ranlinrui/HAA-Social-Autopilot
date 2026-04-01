import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

from app.services.twitter_browser import (
    TwitterBrowser,
    _CACHE_MISS,
    _build_button_text_patterns,
    _detect_login_prompt_kind,
    _extract_graphql_error,
    _mask_login_value,
    _select_login_challenge_value,
)


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

    def test_select_login_challenge_value_prefers_username_for_username_prompt(self):
        value = _select_login_challenge_value(
            "Enter your phone number or username",
            "user_abc",
            "user@example.com",
        )
        self.assertEqual(value, "user_abc")

    def test_select_login_challenge_value_prefers_email_for_email_prompt(self):
        value = _select_login_challenge_value(
            "Confirm your email address",
            "user_abc",
            "user@example.com",
        )
        self.assertEqual(value, "user@example.com")

    def test_detect_login_prompt_kind_identifies_identifier_page(self):
        self.assertEqual(
            _detect_login_prompt_kind(
                "View keyboard shortcuts Sign in to X Phone, email, or username Next Forgot password?"
            ),
            "identifier",
        )

    def test_detect_login_prompt_kind_identifies_challenge_page(self):
        self.assertEqual(
            _detect_login_prompt_kind("We found more than one account. Enter your phone number or username"),
            "challenge",
        )

    def test_detect_login_prompt_kind_identifies_email_or_phone_check_page(self):
        self.assertEqual(_detect_login_prompt_kind("Check your email to continue"), "challenge")
        self.assertEqual(_detect_login_prompt_kind("Check your phone before signing in"), "challenge")

    def test_detect_login_prompt_kind_identifies_password_page(self):
        self.assertEqual(
            _detect_login_prompt_kind("Enter your password to continue"),
            "password",
        )

    def test_build_button_text_patterns_adds_expected_aliases(self):
        next_patterns = [pattern.pattern for pattern in _build_button_text_patterns("next")]
        login_patterns = [pattern.pattern for pattern in _build_button_text_patterns("log in")]

        self.assertEqual(len(next_patterns), 3)
        self.assertEqual(len(login_patterns), 3)

    def test_mask_login_value_masks_email_and_username(self):
        self.assertEqual(_mask_login_value("user@example.com"), "us**@example.com")
        self.assertEqual(_mask_login_value("linrui0203"), "li******03")



if __name__ == "__main__":
    unittest.main()
