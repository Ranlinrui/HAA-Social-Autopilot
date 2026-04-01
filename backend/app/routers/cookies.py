"""
Twitter Cookie Management API

Provides endpoints for managing Twitter authentication cookies.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from typing import Optional
import json
import os
from datetime import datetime, timedelta, timezone

from app.database import get_db
from app.models.setting import Setting
from app.models.twitter_account import TwitterAccount
from app.services.twitter_account_store import (
    GLOBAL_COOKIE_FILE,
    get_account_cookie_file,
    load_cookie_file,
    normalize_account_key,
    save_cookie_file,
    sync_account_cookie_to_global,
)

router = APIRouter(prefix="/api/cookies", tags=["cookies"])


def _error_detail(exc: Exception, fallback: str) -> str:
    message = str(exc).strip()
    return message or fallback


class CookieInput(BaseModel):
    auth_token: str
    ct0: str
    account_name: Optional[str] = "default"


class CookieResponse(BaseModel):
    auth_token: str
    ct0: str
    account_name: str
    is_valid: Optional[bool] = None
    last_validated_at: Optional[str] = None
    expires_at: Optional[str] = None
    validation_mode: Optional[str] = None


class CookieTestResponse(BaseModel):
    is_valid: bool
    message: str
    username: Optional[str] = None


# Cookie storage file path
COOKIE_FILE = GLOBAL_COOKIE_FILE


def load_cookies() -> Optional[dict]:
    """Load cookies from file"""
    return load_cookie_file(COOKIE_FILE)


def save_cookies(cookie_data: dict):
    """Save cookies to file"""
    save_cookie_file(COOKIE_FILE, cookie_data)


async def _upsert_setting(db: AsyncSession, key: str, value: str):
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        db.add(Setting(key=key, value=value))


async def _sync_cookie_account_settings(db: AsyncSession, account_name: str):
    normalized = (account_name or "default").strip() or "default"
    await _upsert_setting(db, "twitter_username", normalized)
    await db.commit()


async def _ensure_cookie_account_record(db: AsyncSession, account_name: str):
    normalized = normalize_account_key(account_name)
    await db.execute(update(TwitterAccount).values(is_active=False))
    result = await db.execute(select(TwitterAccount).where(TwitterAccount.account_key == normalized))
    account = result.scalar_one_or_none()
    if account:
        account.username = normalized
        account.is_active = True
        account.last_login_status = "cookie"
        account.last_login_message = "Cookie 已导入"
        return account

    account = TwitterAccount(
        account_key=normalized,
        username=normalized,
        email=None,
        password=None,
        is_active=True,
        last_login_status="cookie",
        last_login_message="Cookie 已导入",
    )
    db.add(account)
    await db.flush()
    return account


@router.get("/current", response_model=CookieResponse)
async def get_current_cookies():
    """Get currently stored cookies"""
    cookie_data = load_cookies()

    if not cookie_data:
        return CookieResponse(
            auth_token="",
            ct0="",
            account_name="default"
        )

    return CookieResponse(**cookie_data)


@router.post("/update")
async def update_cookies(cookie: CookieInput, db: AsyncSession = Depends(get_db)):
    """Update Twitter cookies"""
    try:
        account_name = (cookie.account_name or "default").strip() or "default"
        normalized_account_key = normalize_account_key(account_name)
        cookie_data = {
            "auth_token": cookie.auth_token,
            "ct0": cookie.ct0,
            "account_name": normalized_account_key,
            "username": normalized_account_key,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "validation_mode": "cookie_only",
        }

        save_cookies(cookie_data)
        save_cookie_file(get_account_cookie_file(normalized_account_key), cookie_data)
        account = await _ensure_cookie_account_record(db, normalized_account_key)
        await _upsert_setting(db, "active_twitter_account_id", str(account.id))
        await _sync_cookie_account_settings(db, normalized_account_key)

        # Reset the in-memory twikit client so it reloads the new cookies
        from app.services.twitter_api import reset_twitter_client
        reset_twitter_client()

        return {
            "success": True,
            "message": "Cookies 已保存",
            "data": cookie_data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=_error_detail(e, "保存 Cookies 失败"))


@router.post("/test", response_model=CookieTestResponse)
async def test_cookies(cookie: CookieInput, db: AsyncSession = Depends(get_db)):
    """Persist cookies and enable cookie-mode auth without live twikit validation."""
    try:
        account_name = (cookie.account_name or "default").strip() or "default"
        normalized_account_key = normalize_account_key(account_name)
        cookie_data = {
            "auth_token": cookie.auth_token,
            "ct0": cookie.ct0,
            "account_name": normalized_account_key,
            "username": normalized_account_key,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "is_valid": True,
            "last_validated_at": datetime.now(timezone.utc).isoformat(),
            "validation_mode": "cookie_only",
        }

        save_cookies(cookie_data)
        save_cookie_file(get_account_cookie_file(normalized_account_key), cookie_data)
        account = await _ensure_cookie_account_record(db, normalized_account_key)
        await _upsert_setting(db, "active_twitter_account_id", str(account.id))
        await _sync_cookie_account_settings(db, normalized_account_key)
        from app.services.twitter_api import reset_twitter_client
        reset_twitter_client()

        return CookieTestResponse(
            is_valid=True,
            message="Cookies 已保存并启用 Cookie 模式，跳过 live twikit transaction 验证",
            username=normalized_account_key,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=_error_detail(e, "测试 Cookies 失败"))


@router.delete("/clear")
async def clear_cookies():
    """Clear stored cookies"""
    try:
        if os.path.exists(COOKIE_FILE):
            os.remove(COOKIE_FILE)
        from app.services.twitter_api import reset_twitter_client
        reset_twitter_client()

        return {"success": True, "message": "Cookies 已清空"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=_error_detail(e, "清空 Cookies 失败"))


@router.get("/status")
async def get_cookie_status():
    """Get cookie status summary"""
    cookie_data = load_cookies()

    if not cookie_data or not cookie_data.get('auth_token'):
        return {
            "configured": False,
            "message": "No cookies configured"
        }

    is_valid = cookie_data.get('is_valid', False)
    last_validated = cookie_data.get('last_validated_at')
    expires_at = cookie_data.get('expires_at')

    # Check if expired
    is_expired = False
    if expires_at:
        try:
            expiry_date = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            is_expired = datetime.now(timezone.utc) > expiry_date
        except:
            pass

    return {
        "configured": True,
        "is_valid": is_valid and not is_expired,
        "is_expired": is_expired,
        "account_name": cookie_data.get('account_name'),
        "username": cookie_data.get('username') or cookie_data.get('account_name'),
        "last_validated_at": last_validated,
        "expires_at": expires_at,
        "validation_mode": cookie_data.get('validation_mode') or "cookie_only",
    }
