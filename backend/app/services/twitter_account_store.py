import json
import os
import re
import shutil
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.database import async_session
from app.models.setting import Setting
from app.models.twitter_account import TwitterAccount

GLOBAL_COOKIE_FILE = "/app/data/twitter_cookies.json"
ACCOUNT_COOKIE_DIR = "/app/data/twitter_cookies"
ACCOUNT_BROWSER_STATE_DIR = "/app/data/twitter_browser_state"
ACTIVE_TWITTER_ACCOUNT_KEY = "active_twitter_account_id"
_CURRENT_ACCOUNT_KEY: ContextVar[str | None] = ContextVar("twitter_account_key", default=None)


def normalize_account_key(value: str | None) -> str:
    raw = (value or "").strip().lstrip("@")
    if not raw:
        return "default"
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)
    return normalized or "default"


def get_account_cookie_file(account_key: str | None) -> str:
    normalized = normalize_account_key(account_key)
    return str(Path(ACCOUNT_COOKIE_DIR) / f"{normalized}.json")


def get_account_browser_storage_file(account_key: str | None) -> str:
    normalized = normalize_account_key(account_key)
    return str(Path(ACCOUNT_BROWSER_STATE_DIR) / f"{normalized}.json")


def load_cookie_file(path: str) -> dict[str, Any] | None:
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        if not data.get("auth_token") or not data.get("ct0"):
            return None
        if not data.get("username") and data.get("account_name"):
            data["username"] = data["account_name"]
        if not data.get("validation_mode"):
            data["validation_mode"] = "cookie_only"
        return data
    except Exception:
        return None


def save_cookie_file(path: str, payload: dict[str, Any]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)


def sync_account_cookie_to_global(account_key: str | None) -> bool:
    source = get_account_cookie_file(account_key)
    if not os.path.exists(source):
        return False
    os.makedirs(os.path.dirname(GLOBAL_COOKIE_FILE), exist_ok=True)
    shutil.copyfile(source, GLOBAL_COOKIE_FILE)
    return True


def sync_global_cookie_to_account(account_key: str | None) -> bool:
    if not os.path.exists(GLOBAL_COOKIE_FILE):
        return False
    target = get_account_cookie_file(account_key)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    shutil.copyfile(GLOBAL_COOKIE_FILE, target)
    return True


async def get_active_twitter_account() -> TwitterAccount | None:
    try:
        async with async_session() as db:
            result = await db.execute(select(TwitterAccount).where(TwitterAccount.is_active.is_(True)))
            account = result.scalar_one_or_none()
            if account is not None:
                return account

            setting_result = await db.execute(select(Setting.value).where(Setting.key == ACTIVE_TWITTER_ACCOUNT_KEY))
            active_id = setting_result.scalar_one_or_none()
            if not active_id:
                return None
            fallback_result = await db.execute(select(TwitterAccount).where(TwitterAccount.id == int(active_id)))
            return fallback_result.scalar_one_or_none()
    except OperationalError:
        return None


async def get_active_account_key() -> str | None:
    account = await get_active_twitter_account()
    if account is None:
        return None
    return account.account_key or account.username


async def get_effective_account_key() -> str | None:
    scoped = _CURRENT_ACCOUNT_KEY.get()
    if scoped:
        return scoped
    return await get_active_account_key()


@asynccontextmanager
async def using_twitter_account(account_key: str | None):
    normalized = normalize_account_key(account_key) if account_key else None
    token = _CURRENT_ACCOUNT_KEY.set(normalized)
    try:
        yield
    finally:
        _CURRENT_ACCOUNT_KEY.reset(token)
