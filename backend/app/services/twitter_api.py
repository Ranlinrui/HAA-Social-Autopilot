"""
Twitter unified facade.
All Twitter operations go through here — routers and services never import twikit directly.
"""
from app.models.tweet import Tweet


async def get_twitter_client():
    from app.services.twitter_twikit import get_twitter_twikit
    instance = await get_twitter_twikit()
    return instance.client


async def test_connection() -> str:
    from app.services.twitter_twikit import test_connection_twikit
    return await test_connection_twikit()


async def publish_tweet(tweet: Tweet) -> str:
    from app.services.twitter_twikit import publish_tweet_twikit
    return await publish_tweet_twikit(tweet)


async def search_tweets(query: str, count: int = 20) -> list:
    from app.services.twitter_twikit import search_tweets_twikit
    return await search_tweets_twikit(query, count)


async def reply_tweet(tweet_id: str, content: str) -> str:
    from app.services.twitter_twikit import reply_tweet_twikit
    return await reply_tweet_twikit(tweet_id, content)


async def retweet_tweet(tweet_id: str) -> str:
    from app.services.twitter_twikit import retweet_tweet_twikit
    return await retweet_tweet_twikit(tweet_id)


async def quote_tweet(tweet_url: str, content: str, media_paths: list = []) -> str:
    from app.services.twitter_twikit import quote_tweet_twikit
    return await quote_tweet_twikit(tweet_url, content, media_paths)


def reset_twitter_client():
    from app.services.twitter_twikit import reset_twitter_twikit
    reset_twitter_twikit()


async def get_mentions(count: int = 40) -> list:
    from app.services.twitter_twikit import get_mentions_twikit
    return await get_mentions_twikit(count)


async def get_tweet_by_id(tweet_id: str) -> dict:
    from app.services.twitter_twikit import get_tweet_by_id_twikit
    return await get_tweet_by_id_twikit(tweet_id)
