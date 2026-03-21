"""
Twitter unified facade.
All Twitter operations go through here — routers and services never import twikit directly.
"""
from collections.abc import Callable

from sqlalchemy import select

from app.config import settings as app_settings
from app.database import async_session
from app.models.setting import Setting
from app.models.tweet import Tweet

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


async def _get_mode_for_feature(feature: str) -> str:
    feature_key = TWITTER_FEATURE_SETTING_KEYS.get(feature)
    default_key = TWITTER_FEATURE_SETTING_KEYS["default"]

    if feature_key and feature_key != default_key:
        feature_value = await _load_setting_value(feature_key)
        if feature_value:
            return _normalize_mode(feature_value)

    default_value = await _load_setting_value(default_key)
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
    return await _call_engine(
        "publish",
        lambda: publish_tweet_twikit,
        lambda: publish_tweet_browser,
        tweet,
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
    return await _call_engine(
        "reply",
        lambda: reply_tweet_twikit,
        lambda: reply_tweet_browser,
        tweet_id,
        content,
    )


async def retweet_tweet(tweet_id: str) -> str:
    from app.services.twitter_browser import retweet_tweet_browser
    from app.services.twitter_twikit import retweet_tweet_twikit
    return await _call_engine(
        "retweet",
        lambda: retweet_tweet_twikit,
        lambda: retweet_tweet_browser,
        tweet_id,
    )


async def quote_tweet(tweet_url: str, content: str, media_paths: list = []) -> str:
    from app.services.twitter_browser import quote_tweet_browser
    from app.services.twitter_twikit import quote_tweet_twikit
    return await _call_engine(
        "quote",
        lambda: quote_tweet_twikit,
        lambda: quote_tweet_browser,
        tweet_url,
        content,
        media_paths,
    )


def reset_twitter_client():
    from app.services.twitter_twikit import reset_twitter_twikit
    reset_twitter_twikit()


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
