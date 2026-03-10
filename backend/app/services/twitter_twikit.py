from typing import Optional, List
import os
from twikit import Client
from app.config import settings
from app.models.tweet import Tweet
from app.logger import setup_logger

logger = setup_logger("twikit")


class TwitterTwikit:
    def __init__(self):
        self.client: Optional[Client] = None
        self.cookies_file = "./data/twitter_cookies.json"

    def _create_client(self) -> Client:
        client = Client(language='en-US', proxy=settings.proxy_url)
        # 修复 twikit 2.3.3 bug: onboarding_task 等方法未携带完整 headers
        # 导致 Cloudflare 因缺少 User-Agent 而拦截请求返回 403
        client.http.headers.update({
            'User-Agent': client._user_agent,
            'Referer': 'https://x.com/',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        return client

    async def init_client(self):
        logger.info("初始化 twikit 客户端，代理: %s", settings.proxy_url)
        self.client = self._create_client()

        if os.path.exists(self.cookies_file):
            try:
                self.client.load_cookies(self.cookies_file)
                logger.info("从 cookie 文件恢复登录状态成功")
                return
            except Exception as e:
                logger.warning("加载 cookie 失败，将重新登录: %s", e)

        await self.login()

    async def login(self, username: str = None, email: str = None, password: str = None):
        if not self.client:
            self.client = self._create_client()

        login_username = username or settings.twitter_username
        login_email = email or settings.twitter_email
        login_password = password or settings.twitter_password

        logger.info("开始登录 Twitter (v2.x ui_metrics 已启用)，账号: %s", login_username)
        try:
            await self.client.login(
                auth_info_1=login_username,
                auth_info_2=login_email,
                password=login_password,
                cookies_file=self.cookies_file,
                enable_ui_metrics=True
            )
            self.client.save_cookies(self.cookies_file)
            logger.info("登录成功，cookie 已保存")
        except Exception as e:
            logger.error("登录失败: %s", e)
            raise

    async def get_me(self) -> dict:
        if not self.client:
            await self.init_client()

        user = await self.client.user()
        logger.info("获取当前用户成功: @%s", user.screen_name)
        return {"id": user.id, "username": user.screen_name, "name": user.name}

    async def post_tweet(self, content: str, media_paths: List[str] = []) -> str:
        if not self.client:
            await self.init_client()

        media_ids = []
        if media_paths:
            for path in media_paths:
                logger.info("上传媒体文件: %s", path)
                media_id = await self.client.upload_media(path, wait_for_completion=True)
                media_ids.append(media_id)
                logger.debug("媒体上传成功，media_id: %s", media_id)

        logger.info("发布推文，内容长度: %d 字符，媒体数: %d", len(content), len(media_ids))
        if media_ids:
            tweet = await self.client.create_tweet(text=content, media_ids=media_ids)
        else:
            tweet = await self.client.create_tweet(text=content)

        logger.info("推文发布成功，twitter_id: %s", tweet.id)
        return tweet.id

    async def search_tweets(self, query: str, count: int = 20) -> List[dict]:
        if not self.client:
            await self.init_client()

        logger.info("搜索推文，关键词: %s，数量: %d", query, count)
        try:
            results = await self.client.search_tweet(query, product='Top', count=count)
            tweets = []
            for t in results:
                tweets.append({
                    "id": t.id,
                    "text": t.text,
                    "author_name": t.user.name,
                    "author_username": t.user.screen_name,
                    "author_verified": t.user.is_blue_verified,
                    "like_count": t.favorite_count,
                    "retweet_count": t.retweet_count,
                    "reply_count": t.reply_count,
                    "view_count": t.view_count,
                    "created_at": str(t.created_at),
                    "url": f"https://x.com/{t.user.screen_name}/status/{t.id}",
                })
            logger.info("搜索完成，返回 %d 条结果", len(tweets))
            return tweets
        except Exception as e:
            logger.error("搜索推文失败，关键词: %s，错误: %s", query, e)
            raise

    async def reply_tweet(self, tweet_id: str, content: str) -> str:
        if not self.client:
            await self.init_client()

        logger.info("回复推文 %s，内容长度: %d 字符", tweet_id, len(content))
        try:
            tweet = await self.client.create_tweet(text=content, reply_to=tweet_id)
            logger.info("回复成功，reply_id: %s", tweet.id)
            return tweet.id
        except Exception as e:
            logger.error("回复推文失败，tweet_id: %s，错误: %s", tweet_id, e)
            raise


_twikit_instance: Optional[TwitterTwikit] = None


async def get_twitter_twikit() -> TwitterTwikit:
    global _twikit_instance
    if _twikit_instance is None:
        _twikit_instance = TwitterTwikit()
        await _twikit_instance.init_client()
    return _twikit_instance


def reset_twitter_twikit():
    global _twikit_instance
    _twikit_instance = None


async def test_connection_twikit() -> str:
    twitter = await get_twitter_twikit()
    me = await twitter.get_me()
    return me["username"]


async def publish_tweet_twikit(tweet: Tweet) -> str:
    twitter = await get_twitter_twikit()
    media_paths = [m.filepath for m in tweet.media_items] if tweet.media_items else []
    return await twitter.post_tweet(tweet.content, media_paths)


async def search_tweets_twikit(query: str, count: int = 20) -> List[dict]:
    twitter = await get_twitter_twikit()
    return await twitter.search_tweets(query, count)


async def reply_tweet_twikit(tweet_id: str, content: str) -> str:
    twitter = await get_twitter_twikit()
    return await twitter.reply_tweet(tweet_id, content)
