from typing import List

from app.logger import setup_logger
from app.models.tweet import Tweet

logger = setup_logger("twitter_browser")


def _not_ready(feature: str) -> RuntimeError:
    return RuntimeError(
        f"Browser 模式尚未完成 {feature} 能力，请先切回 Twikit 模式，或继续开发 BrowserEngine 后再启用该模式。"
    )


async def test_connection_browser() -> str:
    raise _not_ready("连接测试")


async def publish_tweet_browser(tweet: Tweet) -> str:
    raise _not_ready("发帖")


async def search_tweets_browser(query: str, count: int = 20) -> List[dict]:
    raise _not_ready("搜索")


async def reply_tweet_browser(tweet_id: str, content: str) -> str:
    raise _not_ready("回复")


async def retweet_tweet_browser(tweet_id: str) -> str:
    raise _not_ready("转推")


async def quote_tweet_browser(tweet_url: str, content: str, media_paths: List[str] = []) -> str:
    raise _not_ready("引用推文")


async def get_mentions_browser(count: int = 40) -> List[dict]:
    raise _not_ready("提及读取")


async def get_tweet_by_id_browser(tweet_id: str) -> dict:
    raise _not_ready("推文读取")
