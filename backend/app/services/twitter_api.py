"""
Twitter unified facade.
All Twitter operations go through here — routers and services never import twikit directly.
"""
import json
import os
from collections.abc import Callable
from typing import Iterable

from sqlalchemy import select

from app.config import settings as app_settings
from app.database import async_session
from app.models.setting import Setting
from app.models.tweet import Tweet
from app.services.twitter_risk_control import get_twitter_risk_control

COOKIE_FILE = "/app/data/twitter_cookies.json"

TWITTER_FEATURE_SETTING_KEYS = {
    "default": "twitter_publish_mode",
    "test_connection": "twitter_mode_test_connection",
    "publish": "twitter_mode_publish",
    "search": "twitter_mode_search",
    "reply": "twitter_mode_reply",
    "retweet": "twitter_mode_retweet",
    "quote": "twitter_mode_quote",
    "mentions": "twitter_mode_mentions",
    "tweet_lookup": "twitter_mode_tweet_lookup",
}


def _normalize_mode(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"", "twikit"}:
        return "twikit"
    if normalized in {"browser", "playwright"}:
        return "browser"
    return "twikit"


async def _load_setting_value(key: str) -> str | None:
    async with async_session() as db:
        result = await db.execute(select(Setting.value).where(Setting.key == key))
        return result.scalar_one_or_none()


async def _load_setting_values(keys: Iterable[str]) -> dict[str, str]:
    unique_keys = [key for key in dict.fromkeys(keys) if key]
    if not unique_keys:
        return {}

    async with async_session() as db:
        result = await db.execute(
            select(Setting.key, Setting.value).where(Setting.key.in_(unique_keys))
        )
        return {key: value for key, value in result.all()}


def _load_cookie_state() -> dict | None:
    if not os.path.exists(COOKIE_FILE):
        return None
    try:
        with open(COOKIE_FILE, "r") as f:
            data = json.load(f)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if not data.get("auth_token") or not data.get("ct0"):
        return None
    if not data.get("username") and data.get("account_name"):
        data["username"] = data["account_name"]
    if not data.get("validation_mode"):
        data["validation_mode"] = "cookie_only"
    return data


async def _get_mode_for_feature(feature: str) -> str:
    feature_key = TWITTER_FEATURE_SETTING_KEYS.get(feature)
    default_key = TWITTER_FEATURE_SETTING_KEYS["default"]
    values = await _load_setting_values([feature_key, default_key])

    if feature_key and feature_key != default_key:
        feature_value = values.get(feature_key)
        if feature_value:
            return _normalize_mode(feature_value)

    default_value = values.get(default_key)
    return _normalize_mode(default_value or app_settings.twitter_publish_mode)


async def _call_engine(
    feature: str,
    twikit_loader: Callable[[], Callable],
    browser_loader: Callable[[], Callable],
    *args,
    **kwargs,
):
    mode = await _get_mode_for_feature(feature)
    if mode == "browser":
        handler = browser_loader()
    else:
        handler = twikit_loader()
    return await handler(*args, **kwargs)


async def get_active_auth_state(feature: str | None = None) -> dict:
    keys = ["twitter_username", "twitter_publish_mode", *TWITTER_FEATURE_SETTING_KEYS.values()]
    values = await _load_setting_values(keys)
    cookie_state = _load_cookie_state()

    feature_name = feature or "default"
    selected_mode = await _get_mode_for_feature(feature_name)
    configured_username = values.get("twitter_username") or ""
    cookie_username = ""
    if cookie_state:
        cookie_username = cookie_state.get("username") or cookie_state.get("account_name") or ""
    active_username = cookie_username or configured_username or None
    risk_state = get_twitter_risk_control().get_state(active_username)

    return {
        "feature": feature_name,
        "selected_mode": selected_mode,
        "default_mode": _normalize_mode(values.get("twitter_publish_mode") or app_settings.twitter_publish_mode),
        "cookie_configured": bool(cookie_state),
        "cookie_validation_mode": (cookie_state or {}).get("validation_mode"),
        "cookie_username": cookie_username or None,
        "configured_username": configured_username or None,
        "active_username": active_username,
        **risk_state,
    }


async def _execute_write_action(
    action: str,
    twikit_loader: Callable[[], Callable],
    browser_loader: Callable[[], Callable],
    *args,
    tweet_type: str | None = None,
    **kwargs,
):
    auth_state = await get_active_auth_state(action)
    account_key = auth_state.get("active_username")
    risk_control = get_twitter_risk_control()
    risk_control.assert_action_allowed(action, account_key=account_key, tweet_type=tweet_type)
    try:
        result = await _call_engine(action, twikit_loader, browser_loader, *args, **kwargs)
    except Exception as exc:
        risk_control.record_failure(action, exc, account_key=account_key)
        raise
    risk_control.record_success(action, account_key=account_key, tweet_type=tweet_type)
    return result


async def get_twitter_client():
    from app.services.twitter_twikit import get_twitter_twikit
    instance = await get_twitter_twikit()
    return instance.client


async def test_connection() -> str:
    from app.services.twitter_browser import test_connection_browser
    from app.services.twitter_twikit import test_connection_twikit
    return await _call_engine(
        "test_connection",
        lambda: test_connection_twikit,
        lambda: test_connection_browser,
    )


async def publish_tweet(tweet: Tweet) -> str:
    from app.services.twitter_browser import publish_tweet_browser
    from app.services.twitter_twikit import publish_tweet_twikit
    return await _execute_write_action(
        "publish",
        lambda: publish_tweet_twikit,
        lambda: publish_tweet_browser,
        tweet,
        tweet_type=getattr(tweet, "tweet_type", None),
    )


async def search_tweets(query: str, count: int = 20) -> list:
    from app.services.twitter_browser import search_tweets_browser
    from app.services.twitter_twikit import search_tweets_twikit
    return await _call_engine(
        "search",
        lambda: search_tweets_twikit,
        lambda: search_tweets_browser,
        query,
        count,
    )


async def reply_tweet(tweet_id: str, content: str) -> str:
    from app.services.twitter_browser import reply_tweet_browser
    from app.services.twitter_twikit import reply_tweet_twikit
    return await _execute_write_action(
        "reply",
        lambda: reply_tweet_twikit,
        lambda: reply_tweet_browser,
        tweet_id,
        content,
    )


async def retweet_tweet(tweet_id: str) -> str:
    from app.services.twitter_browser import retweet_tweet_browser
    from app.services.twitter_twikit import retweet_tweet_twikit
    return await _execute_write_action(
        "retweet",
        lambda: retweet_tweet_twikit,
        lambda: retweet_tweet_browser,
        tweet_id,
    )


async def quote_tweet(tweet_url: str, content: str, media_paths: list = []) -> str:
    from app.services.twitter_browser import quote_tweet_browser
    from app.services.twitter_twikit import quote_tweet_twikit
    return await _execute_write_action(
        "quote",
        lambda: quote_tweet_twikit,
        lambda: quote_tweet_browser,
        tweet_url,
        content,
        media_paths,
    )


def reset_twitter_client():
    from app.services.twitter_browser import reset_twitter_browser
    from app.services.twitter_twikit import reset_twitter_twikit

    reset_twitter_twikit()
    reset_twitter_browser()


async def get_mentions(count: int = 40) -> list:
    from app.services.twitter_browser import get_mentions_browser
    from app.services.twitter_twikit import get_mentions_twikit
    return await _call_engine(
        "mentions",
        lambda: get_mentions_twikit,
        lambda: get_mentions_browser,
        count,
    )


async def get_tweet_by_id(tweet_id: str) -> dict:
    from app.services.twitter_browser import get_tweet_by_id_browser
    from app.services.twitter_twikit import get_tweet_by_id_twikit
    return await _call_engine(
        "tweet_lookup",
        lambda: get_tweet_by_id_twikit,
        lambda: get_tweet_by_id_browser,
        tweet_id,
    )


async def get_user_profile(username: str) -> dict:
    from app.services.twitter_browser import get_user_profile_browser
    from app.services.twitter_twikit import get_user_profile_twikit
    return await _call_engine(
        "tweet_lookup",
        lambda: get_user_profile_twikit,
        lambda: get_user_profile_browser,
        username,
    )


async def get_user_timeline(username: str, count: int = 5) -> list:
    from app.services.twitter_browser import get_user_timeline_browser
    from app.services.twitter_twikit import get_user_timeline_twikit
    return await _call_engine(
        "tweet_lookup",
        lambda: get_user_timeline_twikit,
        lambda: get_user_timeline_browser,
        username,
        count,
    )
