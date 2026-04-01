import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.routers import monitor as monitor_router


class MonitorRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_stats_returns_zero_safe_payload(self):
        db = AsyncMock()
        db.scalar = AsyncMock(side_effect=[None, None, None, None, None])

        with patch("app.services.twitter_api.get_active_auth_state", AsyncMock(return_value={"active_username": "test_user"})):
            with patch("app.routers.monitor.get_twitter_risk_control") as risk_control_mock:
                risk_control_mock.return_value.get_state.return_value = {
                    "risk_account_key": "test_user",
                    "risk_stage": "normal",
                    "write_blocked": False,
                    "write_block_reason": None,
                    "write_resume_seconds": 0,
                    "auth_backoff_until": None,
                    "read_only_until": None,
                    "recovery_until": None,
                    "last_risk_error": None,
                    "last_risk_event_at": None,
                    "is_persisted": False,
                }

                response = await monitor_router.get_stats(db)

        self.assertEqual(response["total_accounts"], 0)
        self.assertEqual(response["active_accounts"], 0)
        self.assertEqual(response["total_notifications"], 0)
        self.assertEqual(response["commented_notifications"], 0)
        self.assertEqual(response["uncommented_notifications"], 0)
        self.assertEqual(response["today_notifications"], 0)
        self.assertEqual(response["risk_account_key"], "test_user")

    async def test_get_stats_wraps_unexpected_error(self):
        db = AsyncMock()
        db.scalar = AsyncMock(side_effect=RuntimeError("db offline"))

        with self.assertRaises(HTTPException) as ctx:
            await monitor_router.get_stats(db)

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(ctx.exception.detail, "db offline")

    async def test_list_accounts_wraps_unexpected_error(self):
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=RuntimeError("broken select"))

        with self.assertRaises(HTTPException) as ctx:
            await monitor_router.list_accounts(db=db)

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(ctx.exception.detail, "broken select")

    async def test_create_account_reuses_existing_username(self):
        db = AsyncMock()
        existing = SimpleNamespace(account_key="old_key", priority=3, is_active=False)
        db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: existing))

        with patch("app.routers.monitor.get_effective_account_key", AsyncMock(return_value="LinRui0203")):
            response = await monitor_router.create_account(
                monitor_router.MonitoredAccountCreate(username="already_exists"),
                db=db,
            )

        self.assertIs(response, existing)
        self.assertEqual(existing.account_key, "LinRui0203")
        self.assertEqual(existing.priority, 2)
        self.assertTrue(existing.is_active)
        db.commit.assert_awaited()
        db.refresh.assert_awaited_with(existing)


if __name__ == "__main__":
    unittest.main()
