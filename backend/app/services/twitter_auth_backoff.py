from datetime import datetime, timedelta, timezone


AUTH_FAILURE_MARKERS = (
    "could not authenticate you",
    "authorizationerror",
    "status: 401",
    '"code":32',
    "'code': 32",
    "unauthorized",
)

AUTOMATION_FAILURE_MARKERS = (
    "this request looks like it might be automated",
    "authorizationerror",
    "denied by access control",
    "missing twitterusernotsuspended",
    "your account is suspended",
    "账号状态受限",
    "browser 搜索页加载失败",
    "browser 提及页加载失败",
    "javascript 错误页",
    "javascript is not available",
    "[226]",
    "[37]",
    " code 226",
    " code 37",
    "'code': 226",
    "'code': 37",
    '"code":226',
    '"code":37',
    "automated.",
)


def is_auth_failure(exc: Exception | str) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in AUTH_FAILURE_MARKERS)


def is_automation_failure(exc: Exception | str) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in AUTOMATION_FAILURE_MARKERS)


def build_auth_backoff_until(minutes: int = 10) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


def build_automation_backoff_until(hours: int = 12) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def is_backoff_active(backoff_until: datetime | None) -> bool:
    if backoff_until is None:
        return False
    return datetime.now(timezone.utc) < backoff_until


def seconds_until_backoff_expires(backoff_until: datetime | None) -> int:
    if backoff_until is None:
        return 0
    remaining = (backoff_until - datetime.now(timezone.utc)).total_seconds()
    return max(0, int(remaining))
