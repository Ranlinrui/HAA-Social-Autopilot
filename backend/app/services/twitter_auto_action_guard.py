from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


DEFAULT_ACCOUNT_KEY = "__default__"


@dataclass
class AutoActionState:
    last_action_at: datetime | None = None
    history: dict[str, deque[datetime]] | None = None

    def __post_init__(self):
        if self.history is None:
            self.history = defaultdict(deque)


class TwitterAutoActionGuard:
    def __init__(self):
        self._accounts: dict[str, AutoActionState] = {}

    def _normalize_account_key(self, account_key: str | None) -> str:
        key = (account_key or "").strip()
        return key or DEFAULT_ACCOUNT_KEY

    def _get_state(self, account_key: str | None) -> AutoActionState:
        key = self._normalize_account_key(account_key)
        state = self._accounts.get(key)
        if state is None:
            state = AutoActionState()
            self._accounts[key] = state
        return state

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _trim(self, state: AutoActionState, action: str, window: timedelta) -> None:
        now = self._now()
        timestamps = state.history[action]
        while timestamps and now - timestamps[0] > window:
            timestamps.popleft()

    def check_allowed(
        self,
        *,
        account_key: str | None,
        action: str,
        min_interval_seconds: int,
        per_hour_limit: int,
        per_day_limit: int,
    ) -> str | None:
        state = self._get_state(account_key)
        now = self._now()

        if state.last_action_at is not None:
            elapsed = (now - state.last_action_at).total_seconds()
            if elapsed < min_interval_seconds:
                remaining = max(1, int(min_interval_seconds - elapsed))
                return f"自动动作冷却中，还需等待约 {remaining} 秒"

        hour_window = timedelta(hours=1)
        day_window = timedelta(hours=24)
        self._trim(state, action, hour_window)
        self._trim(state, "__all__", day_window)

        if len(state.history[action]) >= per_hour_limit:
            return f"自动 {action} 已达到每小时上限 {per_hour_limit} 次"
        if len(state.history["__all__"]) >= per_day_limit:
            return f"自动动作已达到 24 小时上限 {per_day_limit} 次"
        return None

    def get_total_actions_last_24h(self, account_key: str | None) -> int:
        state = self._get_state(account_key)
        day_window = timedelta(hours=24)
        self._trim(state, "__all__", day_window)
        return len(state.history["__all__"])

    def record_success(self, *, account_key: str | None, action: str) -> None:
        state = self._get_state(account_key)
        now = self._now()
        state.last_action_at = now
        state.history[action].append(now)
        state.history["__all__"].append(now)


_guard = TwitterAutoActionGuard()


def get_twitter_auto_action_guard() -> TwitterAutoActionGuard:
    return _guard
