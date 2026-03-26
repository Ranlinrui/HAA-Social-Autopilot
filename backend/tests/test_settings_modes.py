import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from app.routers import settings as settings_router


class FakeScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return FakeScalarResult(self._items)

    def scalar_one_or_none(self):
        if not self._items:
            return None
        return self._items[0]


class SettingsModeTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_settings_includes_mode_defaults_and_masks_secrets(self):
        db = AsyncMock()
        db.execute.return_value = FakeResult([
            SimpleNamespace(key="twitter_password", value="secret-pass"),
            SimpleNamespace(key="llm_api_key", value="sk-test-12345678"),
        ])

        response = await settings_router.get_settings(db)
        payload = response.model_dump()["settings"]

        self.assertEqual(payload["twitter_publish_mode"], "twikit")
        self.assertEqual(payload["twitter_mode_search"], "twikit")
        self.assertTrue(payload["twitter_password_saved"])
        self.assertTrue(payload["llm_api_key_saved"])
        self.assertNotIn("twitter_password", payload)
        self.assertNotEqual(payload["llm_api_key"], "sk-test-12345678")

    async def test_twitter_login_in_browser_mode_uses_browser_engine(self):
        db = AsyncMock()
        db.add = Mock()
        db.execute = AsyncMock(side_effect=[
            FakeResult([SimpleNamespace(key="twitter_publish_mode", value="browser")]),
            FakeResult([]),
            FakeResult([]),
            FakeResult([]),
        ])

        request = settings_router.TwitterLoginRequest(
            username="user1",
            email="user1@example.com",
            password="pass123",
        )

        with patch("app.services.twitter_browser.login_browser", AsyncMock(return_value="browser_user")) as login_mock, \
             patch("app.services.twitter_twikit.TwitterTwikit") as twikit_cls:
            response = await settings_router.twitter_login(request, db)

        self.assertTrue(response.success)
        self.assertIn("Browser 模式登录成功", response.message)
        self.assertEqual(response.username, "browser_user")
        self.assertEqual(db.add.call_count, 3)
        db.commit.assert_awaited_once()
        login_mock.assert_awaited_once_with("user1", "user1@example.com", "pass123")
        twikit_cls.assert_not_called()

    async def test_test_twitter_connection_calls_browser_engine_in_browser_mode(self):
        db = AsyncMock()
        db.execute.return_value = FakeResult([SimpleNamespace(key="twitter_publish_mode", value="browser")])

        with patch("app.services.twitter_api.test_connection", AsyncMock(return_value="browser_user")) as test_mock:
            response = await settings_router.test_twitter_connection(db)

        self.assertTrue(response.success)
        self.assertEqual(response.username, "browser_user")
        self.assertIn("Browser 模式连接成功", response.message)
        test_mock.assert_awaited_once()

    async def test_test_twitter_connection_prefers_feature_mode_override(self):
        db = AsyncMock()
        db.execute.return_value = FakeResult([
            SimpleNamespace(key="twitter_publish_mode", value="twikit"),
            SimpleNamespace(key="twitter_mode_test_connection", value="browser"),
        ])

        with patch("app.services.twitter_api.test_connection", AsyncMock(return_value="browser_user")) as test_mock:
            response = await settings_router.test_twitter_connection(db)

        self.assertTrue(response.success)
        self.assertEqual(response.username, "browser_user")
        self.assertIn("Browser 模式连接成功", response.message)
        test_mock.assert_awaited_once()

    async def test_test_twitter_connection_short_circuits_when_cookie_configured(self):
        db = AsyncMock()

        with patch("app.services.twitter_api.get_active_auth_state", AsyncMock(return_value={
            "feature": "test_connection",
            "selected_mode": "twikit",
            "default_mode": "twikit",
            "cookie_configured": True,
            "cookie_validation_mode": "cookie_only",
            "cookie_username": "cookie_user",
            "configured_username": "configured_user",
            "active_username": "cookie_user",
        })), patch("app.services.twitter_api.test_connection", AsyncMock()) as test_mock:
            response = await settings_router.test_twitter_connection(db)

        self.assertTrue(response.success)
        self.assertEqual(response.username, "cookie_user")
        self.assertIn("Cookie 模式", response.message)
        test_mock.assert_not_awaited()

    async def test_get_twitter_auth_state_returns_service_payload(self):
        payload = {
            "feature": "default",
            "selected_mode": "twikit",
            "default_mode": "twikit",
            "cookie_configured": True,
            "cookie_validation_mode": "cookie_only",
            "cookie_username": "cookie_user",
            "configured_username": "configured_user",
            "active_username": "cookie_user",
        }

        with patch("app.services.twitter_api.get_active_auth_state", AsyncMock(return_value=payload)):
            response = await settings_router.get_twitter_auth_state()

        self.assertEqual(
            response.model_dump(exclude_none=True, exclude_defaults=True),
            payload,
        )


if __name__ == "__main__":
    unittest.main()
