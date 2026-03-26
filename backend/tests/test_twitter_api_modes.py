import unittest
from unittest.mock import AsyncMock, patch

from app.services import twitter_api


class TwitterApiModeTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_mode_prefers_feature_override(self):
        with patch.object(
            twitter_api,
            "_load_setting_values",
            AsyncMock(return_value={
                "twitter_mode_publish": "browser",
                "twitter_publish_mode": "twikit",
            }),
        ):
            mode = await twitter_api._get_mode_for_feature("publish")

        self.assertEqual(mode, "browser")

    async def test_get_mode_falls_back_to_global_default(self):
        with patch.object(
            twitter_api,
            "_load_setting_values",
            AsyncMock(return_value={"twitter_publish_mode": "browser"}),
        ):
            mode = await twitter_api._get_mode_for_feature("reply")

        self.assertEqual(mode, "browser")

    async def test_get_mode_uses_app_default_when_db_empty(self):
        with patch.object(
            twitter_api,
            "_load_setting_values",
            AsyncMock(return_value={}),
        ), patch.object(twitter_api.app_settings, "twitter_publish_mode", "twikit"):
            mode = await twitter_api._get_mode_for_feature("search")

        self.assertEqual(mode, "twikit")

    async def test_call_engine_routes_to_browser(self):
        with patch.object(twitter_api, "_get_mode_for_feature", AsyncMock(return_value="browser")):
            twikit_handler = AsyncMock(return_value="twikit")
            browser_handler = AsyncMock(return_value="browser")

            result = await twitter_api._call_engine(
                "publish",
                lambda: twikit_handler,
                lambda: browser_handler,
                "payload",
            )

        self.assertEqual(result, "browser")
        twikit_handler.assert_not_awaited()
        browser_handler.assert_awaited_once_with("payload")

    async def test_call_engine_routes_to_twikit(self):
        with patch.object(twitter_api, "_get_mode_for_feature", AsyncMock(return_value="twikit")):
            twikit_handler = AsyncMock(return_value="twikit")
            browser_handler = AsyncMock(return_value="browser")

            result = await twitter_api._call_engine(
                "publish",
                lambda: twikit_handler,
                lambda: browser_handler,
                "payload",
            )

        self.assertEqual(result, "twikit")
        browser_handler.assert_not_awaited()
        twikit_handler.assert_awaited_once_with("payload")

    async def test_get_active_auth_state_prefers_cookie_username(self):
        with patch.object(
            twitter_api,
            "_load_setting_values",
            AsyncMock(return_value={"twitter_username": "configured_user", "twitter_publish_mode": "twikit"}),
        ), patch.object(
            twitter_api,
            "_get_mode_for_feature",
            AsyncMock(return_value="browser"),
        ), patch.object(
            twitter_api,
            "_load_cookie_state",
            return_value={"username": "cookie_user", "validation_mode": "cookie_only"},
        ):
            state = await twitter_api.get_active_auth_state("publish")

        self.assertEqual(state["selected_mode"], "browser")
        self.assertEqual(state["active_username"], "cookie_user")
        self.assertEqual(state["configured_username"], "configured_user")
        self.assertTrue(state["cookie_configured"])

    async def test_get_active_auth_state_falls_back_to_configured_username(self):
        with patch.object(
            twitter_api,
            "_load_setting_values",
            AsyncMock(return_value={"twitter_username": "configured_user", "twitter_publish_mode": "twikit"}),
        ), patch.object(
            twitter_api,
            "_get_mode_for_feature",
            AsyncMock(return_value="twikit"),
        ), patch.object(
            twitter_api,
            "_load_cookie_state",
            return_value=None,
        ):
            state = await twitter_api.get_active_auth_state()

        self.assertEqual(state["active_username"], "configured_user")
        self.assertFalse(state["cookie_configured"])


if __name__ == "__main__":
    unittest.main()
