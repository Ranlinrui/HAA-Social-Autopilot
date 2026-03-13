"""
Twitter Cookie Management API

Provides endpoints for managing Twitter authentication cookies.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import json
import os
from datetime import datetime, timedelta

from app.database import get_db
from app.models.setting import Setting
from app.config import settings as app_settings

router = APIRouter(prefix="/api/cookies", tags=["cookies"])


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


class CookieTestResponse(BaseModel):
    is_valid: bool
    message: str
    username: Optional[str] = None


# Cookie storage file path
COOKIE_FILE = os.path.join("./data", "twitter_cookies.json")


def load_cookies() -> Optional[dict]:
    """Load cookies from file"""
    try:
        if os.path.exists(COOKIE_FILE):
            with open(COOKIE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading cookies: {e}")
    return None


def save_cookies(cookie_data: dict):
    """Save cookies to file"""
    try:
        os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)
        with open(COOKIE_FILE, 'w') as f:
            json.dump(cookie_data, f, indent=2)
    except Exception as e:
        print(f"Error saving cookies: {e}")
        raise


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
async def update_cookies(cookie: CookieInput):
    """Update Twitter cookies"""
    try:
        cookie_data = {
            "auth_token": cookie.auth_token,
            "ct0": cookie.ct0,
            "account_name": cookie.account_name or "default",
            "updated_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat()
        }

        save_cookies(cookie_data)

        # Reset the in-memory twikit client so it reloads the new cookies
        from app.services.twitter_api import reset_twitter_client
        reset_twitter_client()

        return {
            "success": True,
            "message": "Cookies saved successfully",
            "data": cookie_data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test", response_model=CookieTestResponse)
async def test_cookies(cookie: CookieInput):
    """Test if cookies are valid by making a Twitter API request"""
    try:
        import httpx

        headers = {
            'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
            'x-csrf-token': cookie.ct0,
            'content-type': 'application/json',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }

        cookies_dict = {
            'auth_token': cookie.auth_token,
            'ct0': cookie.ct0
        }

        # Use proxy if configured
        proxies = None
        if app_settings.proxy_url:
            proxies = {
                "http://": app_settings.proxy_url,
                "https://": app_settings.proxy_url
            }

        async with httpx.AsyncClient(proxies=proxies, timeout=10.0) as client:
            response = await client.get(
                'https://api.twitter.com/1.1/account/verify_credentials.json',
                headers=headers,
                cookies=cookies_dict
            )

            if response.status_code == 200:
                user_data = response.json()

                # Save validated cookies
                cookie_data = load_cookies() or {}
                cookie_data.update({
                    "auth_token": cookie.auth_token,
                    "ct0": cookie.ct0,
                    "account_name": cookie.account_name or user_data.get('screen_name', 'default'),
                    "is_valid": True,
                    "last_validated_at": datetime.utcnow().isoformat(),
                    "username": user_data.get('screen_name'),
                    "user_id": user_data.get('id_str')
                })
                save_cookies(cookie_data)

                return CookieTestResponse(
                    is_valid=True,
                    message="Cookies are valid!",
                    username=user_data.get('screen_name')
                )

            elif response.status_code == 401:
                return CookieTestResponse(
                    is_valid=False,
                    message="Authentication failed. Cookies may be expired."
                )

            elif response.status_code == 429:
                return CookieTestResponse(
                    is_valid=False,
                    message="Rate limited. Please wait a few minutes."
                )

            else:
                return CookieTestResponse(
                    is_valid=False,
                    message=f"Unexpected response: {response.status_code}"
                )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear")
async def clear_cookies():
    """Clear stored cookies"""
    try:
        if os.path.exists(COOKIE_FILE):
            os.remove(COOKIE_FILE)

        return {"success": True, "message": "Cookies cleared"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
            is_expired = datetime.utcnow() > expiry_date
        except:
            pass

    return {
        "configured": True,
        "is_valid": is_valid and not is_expired,
        "is_expired": is_expired,
        "account_name": cookie_data.get('account_name'),
        "username": cookie_data.get('username'),
        "last_validated_at": last_validated,
        "expires_at": expires_at
    }
