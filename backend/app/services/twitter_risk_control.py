from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.models.tweet import TweetType
from app.services.twitter_auth_backoff import is_auth_failure, is_automation_failure


WRITE_ACTIONS = {"publish", "reply", "retweet", "quote"}
DEFAULT_ACCOUNT_KEY = "__default__"


@dataclass(frozen=True)
class ActionBudget:
    limit: int
    window: timedelta


class AccountRiskState:
    def __init__(self):
        self.history: dict[str, deque[datetime]] = defaultdict(deque)
        self.auth_backoff_until: datetime | None = None
        self.read_only_until: datetime | None = None
        self.recovery_until: datetime | None = None
        self.last_error: str | None = None
        self.last_event_at: datetime | None = None


class TwitterRiskControl:
    def __init__(self):
        self._accounts: dict[str, AccountRiskState] = {}

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _normalize_account_key(self, account_key: str | None) -> str:
        normalized = (account_key or "").strip()
        return normalized or DEFAULT_ACCOUNT_KEY

    def _get_account(self, account_key: str | None, *, create: bool = True) -> AccountRiskState | None:
        key = self._normalize_account_key(account_key)
        account = self._accounts.get(key)
        if account is None and create:
            account = AccountRiskState()
            self._accounts[key] = account
        return account

    def _trim(self, state: AccountRiskState, action: str, window: timedelta) -> None:
        now = self._now()
        timestamps = state.history[action]
        while timestamps and now - timestamps[0] > window:
            timestamps.popleft()

    def _append(self, state: AccountRiskState, action: str) -> None:
        state.history[action].append(self._now())

    def _get_stage(self, state: AccountRiskState) -> str:
        now = self._now()
        if state.auth_backoff_until and now < state.auth_backoff_until:
            return "auth_cooldown"
        if state.read_only_until and now < state.read_only_until:
            return "read_only"
        if state.recovery_until and now < state.recovery_until:
            midpoint = state.read_only_until or state.last_event_at
            if midpoint:
                midpoint = midpoint + (state.recovery_until - midpoint) / 2
                if now < midpoint:
                    return "recovery_cautious"
            return "recovery_limited"
        return "normal"

    def _get_budget(self, state: AccountRiskState, action: str, *, tweet_type: str | None = None) -> ActionBudget | None:
        stage = self._get_stage(state)
        is_video = (tweet_type or "").lower() == TweetType.VIDEO.value

        if stage in {"auth_cooldown", "read_only"}:
            return None

        if stage == "recovery_cautious":
            budgets = {
                "publish": ActionBudget(1, timedelta(hours=6)),
                "reply": ActionBudget(4, timedelta(hours=3)),
                "retweet": ActionBudget(3, timedelta(hours=3)),
                "quote": ActionBudget(1, timedelta(hours=6)),
            }
            if action == "publish" and is_video:
                return ActionBudget(0, timedelta(hours=12))
            return budgets.get(action)

        if stage == "recovery_limited":
            budgets = {
                "publish": ActionBudget(2, timedelta(hours=12)),
                "reply": ActionBudget(10, timedelta(hours=6)),
                "retweet": ActionBudget(8, timedelta(hours=6)),
                "quote": ActionBudget(2, timedelta(hours=12)),
            }
            if action == "publish" and is_video:
                return ActionBudget(1, timedelta(hours=12))
            return budgets.get(action)

        budgets = {
            "publish": ActionBudget(6, timedelta(hours=24)),
            "reply": ActionBudget(20, timedelta(hours=6)),
            "retweet": ActionBudget(15, timedelta(hours=6)),
            "quote": ActionBudget(4, timedelta(hours=24)),
        }
        if action == "publish" and is_video:
            return ActionBudget(2, timedelta(hours=24))
        return budgets.get(action)

    def _seconds_until(self, value: datetime | None) -> int:
        if value is None:
            return 0
        return max(0, int((value - self._now()).total_seconds()))

    def get_state(self, account_key: str | None = None) -> dict[str, Any]:
        key = self._normalize_account_key(account_key)
        existed = key in self._accounts
        account = self._get_account(account_key, create=False)
        if account is None:
            account = AccountRiskState()
        stage = self._get_stage(account)
        write_blocked = stage in {"auth_cooldown", "read_only"}
        reason = None
        resume_seconds = 0

        if stage == "auth_cooldown":
            reason = "登录态异常，写入动作临时冷却中"
            resume_seconds = self._seconds_until(account.auth_backoff_until)
        elif stage == "read_only":
            reason = "账号近期触发自动化风控，当前只保留只读能力"
            resume_seconds = self._seconds_until(account.read_only_until)
        elif stage in {"recovery_cautious", "recovery_limited"}:
            reason = "账号处于恢复期，写入动作已限流"
            resume_seconds = self._seconds_until(account.recovery_until)

        return {
            "risk_account_key": key,
            "risk_stage": stage,
            "write_blocked": write_blocked,
            "write_block_reason": reason,
            "write_resume_seconds": resume_seconds,
            "auth_backoff_until": account.auth_backoff_until,
            "read_only_until": account.read_only_until,
            "recovery_until": account.recovery_until,
            "last_risk_error": account.last_error,
            "last_risk_event_at": account.last_event_at,
            "is_persisted": existed,
        }

    def list_states(self, *, include_normal: bool = True) -> list[dict[str, Any]]:
        self.reset_if_expired()
        rows: list[dict[str, Any]] = []
        for key in sorted(self._accounts.keys()):
            state = self.get_state(key)
            if not include_normal and state["risk_stage"] == "normal":
                continue
            rows.append(state)
        return rows

    def reset_account(self, account_key: str | None) -> bool:
        key = self._normalize_account_key(account_key)
        existed = key in self._accounts
        self._accounts.pop(key, None)
        return existed

    def assert_action_allowed(self, action: str, *, account_key: str | None = None, tweet_type: str | None = None) -> None:
        if action not in WRITE_ACTIONS:
            return

        state = self.get_state(account_key)
        account = self._get_account(account_key)
        assert account is not None
        if state["write_blocked"]:
            minutes = max(1, state["write_resume_seconds"] // 60)
            raise RuntimeError(f"{state['write_block_reason']}，约 {minutes} 分钟后再试")

        budget = self._get_budget(account, action, tweet_type=tweet_type)
        if budget is None:
            return

        if budget.limit <= 0:
            hours = max(1, int(budget.window.total_seconds() // 3600))
            raise RuntimeError(f"当前恢复阶段暂不允许此类动作，建议约 {hours} 小时后再试")

        self._trim(account, action, budget.window)
        count = len(account.history[action])
        if count >= budget.limit:
            earliest = account.history[action][0]
            remaining = int((earliest + budget.window - self._now()).total_seconds())
            minutes = max(1, remaining // 60)
            raise RuntimeError(f"当前账号 {action} 动作已达恢复期配额上限，请约 {minutes} 分钟后再试")

    def record_success(self, action: str, *, account_key: str | None = None, tweet_type: str | None = None) -> None:
        if action not in WRITE_ACTIONS:
            return
        account = self._get_account(account_key)
        assert account is not None
        budget = self._get_budget(account, action, tweet_type=tweet_type)
        if budget is not None:
            self._trim(account, action, budget.window)
        self._append(account, action)

    def record_failure(self, action: str, exc: Exception | str, *, account_key: str | None = None) -> None:
        account = self._get_account(account_key)
        assert account is not None
        message = str(exc).strip()
        account.last_error = message
        account.last_event_at = self._now()

        if is_auth_failure(exc):
            account.auth_backoff_until = self._now() + timedelta(minutes=10)
            return

        if is_automation_failure(exc):
            now = self._now()
            account.read_only_until = now + timedelta(hours=6)
            account.recovery_until = account.read_only_until + timedelta(hours=18)
            return

    def reset_if_expired(self) -> None:
        now = self._now()
        expired_keys: list[str] = []
        for key, account in self._accounts.items():
            if account.auth_backoff_until and now >= account.auth_backoff_until:
                account.auth_backoff_until = None
            if account.recovery_until and now >= account.recovery_until:
                account.read_only_until = None
                account.recovery_until = None
                account.last_error = None
            if (
                not account.history
                and account.auth_backoff_until is None
                and account.read_only_until is None
                and account.recovery_until is None
                and account.last_error is None
                and account.last_event_at is None
            ):
                expired_keys.append(key)
        for key in expired_keys:
            self._accounts.pop(key, None)


_risk_control = TwitterRiskControl()


def get_twitter_risk_control() -> TwitterRiskControl:
    _risk_control.reset_if_expired()
    return _risk_control
