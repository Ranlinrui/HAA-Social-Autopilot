"""
Twitter 发布统一入口
所有 Twitter 操作通过 twikit 实现
"""
from app.models.tweet import Tweet


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
