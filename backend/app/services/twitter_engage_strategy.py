from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models.twitter_account import TwitterAccount
from app.services.twitter_account_store import get_account_cookie_file, get_active_account_key
from app.services.twitter_auto_action_guard import get_twitter_auto_action_guard


@dataclass
class EngageAccountChoice:
    account_key: str
    pool_size: int


class TwitterEngageStrategy:
    def __init__(self):
        self._cursor = 0

    async def list_ready_account_keys(self) -> list[str]:
        async with async_session() as db:
            result = await db.execute(
                select(TwitterAccount).order_by(
                    TwitterAccount.is_active.desc(),
                    TwitterAccount.updated_at.desc(),
                    TwitterAccount.id.asc(),
                )
            )
            rows = result.scalars().all()

        ready: list[str] = []
        for row in rows:
            account_key = (row.account_key or row.username or "").strip()
            if not account_key:
                continue
            if Path(get_account_cookie_file(account_key)).exists():
                ready.append(account_key)

        if ready:
            return ready

        fallback = await get_active_account_key()
        return [fallback] if fallback else []

    async def choose_account_for_auto_engage(self) -> EngageAccountChoice | None:
        keys = await self.list_ready_account_keys()
        if not keys:
            return None
        index = self._cursor % len(keys)
        self._cursor += 1
        return EngageAccountChoice(account_key=keys[index], pool_size=len(keys))

    def should_skip_auto_engage(
        self,
        *,
        account_key: str,
        pool_size: int,
        action: str,
    ) -> str | None:
        guard = get_twitter_auto_action_guard()
        total_24h = guard.get_total_actions_last_24h(account_key)
        if total_24h >= settings.auto_engage_high_load_threshold_24h:
            ratio = settings.auto_engage_high_load_skip_ratio
        elif pool_size <= 1:
            ratio = settings.auto_engage_skip_ratio_single_account
        else:
            ratio = settings.auto_engage_skip_ratio_multi_account

        ratio = max(0.0, min(0.95, float(ratio)))
        if random.random() < ratio:
            return (
                f"为降低检测风险，本次自动{action}已随机跳过"
                f"（账号池 {pool_size} 个，近24小时动作 {total_24h} 次）"
            )
        return None


_strategy = TwitterEngageStrategy()


def get_twitter_engage_strategy() -> TwitterEngageStrategy:
    return _strategy
