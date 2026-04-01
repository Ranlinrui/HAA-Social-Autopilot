import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from tempfile import TemporaryDirectory
from pathlib import Path
import json

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
        execute_calls = iter([FakeResult([SimpleNamespace(key="twitter_publish_mode", value="browser")])])

        async def fake_execute(*args, **kwargs):
            try:
                return next(execute_calls)
            except StopIteration:
                return FakeResult([])

        db.execute = AsyncMock(side_effect=fake_execute)

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
        self.assertGreaterEqual(db.add.call_count, 4)
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

    async def test_get_twitter_login_diagnostic_returns_saved_payload(self):
        payload = {"label": "login_failed", "stage": "challenge", "url": "https://x.com/i/flow/login"}
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "twitter_browser_login_diagnostic.json"
            path.write_text(json.dumps(payload))
            with patch.object(settings_router, "LOGIN_DIAGNOSTIC_FILE", str(path)):
                response = await settings_router.get_twitter_login_diagnostic()

        self.assertTrue(response["success"])
        self.assertEqual(response["diagnostic"]["stage"], "challenge")

    async def test_list_twitter_accounts_returns_password_saved_flag(self):
        now = datetime.now(timezone.utc)
        db = AsyncMock()
        db.execute.return_value = FakeResult([
            SimpleNamespace(
                id=1,
                account_key="matrix-a",
                username="matrix_a",
                email="a@example.com",
                is_active=True,
                password="secret",
                last_login_status="success",
                last_login_message="ok",
                created_at=now,
                updated_at=now,
            )
        ])

        response = await settings_router.list_twitter_accounts(db)

        self.assertEqual(len(response), 1)
        self.assertTrue(response[0].password_saved)
        self.assertEqual(response[0].username, "matrix_a")

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

    async def test_check_twitter_account_health_returns_live_probe_summary(self):
        now = datetime.now(timezone.utc)
        account = SimpleNamespace(
            id=1,
            account_key="matrix-a",
            username="matrix_a",
            email="a@example.com",
            is_active=True,
            password="secret",
            last_login_status="cookie",
            last_login_message="Cookie 已导入",
            created_at=now,
            updated_at=now,
        )
        db = AsyncMock()
        db.execute.return_value = FakeResult([account])

        browser = SimpleNamespace(get_session_status=lambda account_key: {"ready": True})
        twikit_instance = AsyncMock()
        twikit_instance.get_me.return_value = {"username": "matrix_a"}

        @asynccontextmanager
        async def fake_using_account(_account_key):
            yield

        with patch.object(settings_router, "load_cookie_file", return_value={"auth_token": "a", "ct0": "b"}), \
             patch.object(settings_router, "using_twitter_account", fake_using_account), \
             patch("app.services.twitter_browser.get_twitter_browser", AsyncMock(return_value=browser)), \
             patch("app.services.twitter_twikit.TwitterTwikit", return_value=twikit_instance):
            response = await settings_router.check_twitter_account_health(1, db)

        self.assertTrue(response.success)
        self.assertTrue(response.cookie_ready)
        self.assertTrue(response.browser_session_ready)
        self.assertTrue(response.twikit_ok)
        self.assertTrue(response.automation_ready)
        self.assertIn("@matrix_a", response.twikit_message)


if __name__ == "__main__":
    unittest.main()
