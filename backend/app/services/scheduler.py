from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime
import asyncio

from app.database import async_session
from app.models.tweet import Tweet, TweetStatus
from app.services.twitter_api import publish_tweet
from app.services.tweet_guard import apply_publish_guard, is_publish_restricted_error
from app.logger import setup_logger

logger = setup_logger("scheduler")
scheduler = AsyncIOScheduler()


def should_skip_failed_retry(tweet: Tweet) -> bool:
    return is_publish_restricted_error(getattr(tweet, 'error_message', None))


async def check_scheduled_tweets():
    async with async_session() as db:
        now = datetime.utcnow()
        result = await db.execute(
            select(Tweet)
            .options(selectinload(Tweet.media_items))
            .where(
                Tweet.status == TweetStatus.SCHEDULED,
                Tweet.scheduled_at <= now
            )
        )
        tweets = result.scalars().all()

        if tweets:
            logger.info("发现 %d 条待发布排期推文", len(tweets))

        for tweet in tweets:
            tweet.status = TweetStatus.PUBLISHING
            tweet.error_message = None
            await db.commit()
            logger.info("开始发布排期推文 id=%d，内容: %.50s...", tweet.id, tweet.content)

            try:
                await apply_publish_guard(tweet)
                twitter_id = await publish_tweet(tweet)
                tweet.status = TweetStatus.PUBLISHED
                tweet.published_at = datetime.utcnow()
                tweet.twitter_id = twitter_id
                tweet.error_message = None
                logger.info("排期推文发布成功 id=%d，twitter_id=%s", tweet.id, twitter_id)
            except Exception as e:
                tweet.status = TweetStatus.FAILED
                detail = str(e).strip() or repr(e)
                tweet.error_message = detail
                tweet.retry_count += 1
                logger.exception("排期推文发布失败 id=%d，错误: %s", tweet.id, detail)

            await db.commit()


async def retry_failed_tweets():
    async with async_session() as db:
        result = await db.execute(
            select(Tweet)
            .options(selectinload(Tweet.media_items))
            .where(
                Tweet.status == TweetStatus.FAILED,
                Tweet.retry_count < 3
            )
        )
        tweets = result.scalars().all()

        if tweets:
            logger.info("发现 %d 条失败推文待重试", len(tweets))

        for tweet in tweets:
            if should_skip_failed_retry(tweet):
                logger.warning("跳过重试推文 id=%d，上一轮失败属于账号受限或风控: %s", tweet.id, tweet.error_message)
                continue

            logger.info("重试发布推文 id=%d（第 %d 次）", tweet.id, tweet.retry_count + 1)

            try:
                await apply_publish_guard(tweet)
                tweet.status = TweetStatus.PUBLISHING
                tweet.error_message = None
                await db.commit()
                twitter_id = await publish_tweet(tweet)
                tweet.status = TweetStatus.PUBLISHED
                tweet.published_at = datetime.utcnow()
                tweet.twitter_id = twitter_id
                tweet.error_message = None
                logger.info("重试发布成功 id=%d，twitter_id=%s", tweet.id, twitter_id)
            except Exception as e:
                tweet.status = TweetStatus.FAILED
                detail = str(e).strip() or repr(e)
                tweet.error_message = detail
                tweet.retry_count += 1
                logger.exception("重试发布失败 id=%d（已重试 %d 次），错误: %s", tweet.id, tweet.retry_count, detail)

            await db.commit()
            await asyncio.sleep(5)


def start_scheduler():
    scheduler.add_job(check_scheduled_tweets, IntervalTrigger(minutes=1), id="check_scheduled", replace_existing=True)
    scheduler.add_job(retry_failed_tweets, IntervalTrigger(minutes=15), id="retry_failed", replace_existing=True)
    scheduler.start()
    logger.info("调度器已启动")


def stop_scheduler():
    scheduler.shutdown()
    logger.info("调度器已停止")


