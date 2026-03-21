import asyncio
import random
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.logger import setup_logger
from app.models.tweet import Tweet, TweetStatus

logger = setup_logger('tweet_guard')

TEXT_COOLDOWN_SECONDS = 45 * 60
MEDIA_COOLDOWN_SECONDS = 120 * 60
RANDOM_DELAY_RANGE = (30, 120)
SIMILARITY_THRESHOLD = 0.92
SIMILAR_LOOKBACK_HOURS = 24
PENALTY_226_HOURS = 12


@dataclass
class GuardDecision:
    allowed: bool
    reason: str | None = None
    delay_seconds: int = 0


def _normalize_content(content: str) -> str:
    lowered = content.lower().strip()
    lowered = re.sub(r'https?://\S+', ' ', lowered)
    lowered = re.sub(r'[@#][\w_]+', ' ', lowered)
    lowered = re.sub(r'\s+', ' ', lowered)
    return lowered.strip()


def _is_similar(content_a: str, content_b: str) -> bool:
    if not content_a or not content_b:
        return False
    return SequenceMatcher(None, _normalize_content(content_a), _normalize_content(content_b)).ratio() >= SIMILARITY_THRESHOLD


def _has_media(tweet: Tweet) -> bool:
    return bool(getattr(tweet, 'media_items', None))


async def evaluate_publish_guard(tweet: Tweet) -> GuardDecision:
    async with async_session() as db:
        now = datetime.utcnow()
        cooldown_seconds = MEDIA_COOLDOWN_SECONDS if _has_media(tweet) else TEXT_COOLDOWN_SECONDS

        last_published = await db.execute(
            select(Tweet)
            .where(Tweet.status == TweetStatus.PUBLISHED)
            .order_by(Tweet.published_at.desc())
            .limit(1)
        )
        last_published_tweet = last_published.scalar_one_or_none()
        if last_published_tweet and last_published_tweet.published_at:
            elapsed = (now - last_published_tweet.published_at).total_seconds()
            if elapsed < cooldown_seconds:
                remaining = int(cooldown_seconds - elapsed)
                return GuardDecision(False, f'发帖冷却中，还需等待约 {remaining // 60 + 1} 分钟')

        recent_failed = await db.execute(
            select(Tweet)
            .where(
                Tweet.status == TweetStatus.FAILED,
                Tweet.updated_at >= now - timedelta(hours=PENALTY_226_HOURS)
            )
            .order_by(Tweet.updated_at.desc())
            .limit(5)
        )
        for failed in recent_failed.scalars().all():
            msg = (failed.error_message or '').lower()
            if '226' in msg or 'automated' in msg or 'authorizationerror' in msg:
                return GuardDecision(False, '账号近期触发 226 风控，建议至少等待 12 小时后再发帖')

        recent_published = await db.execute(
            select(Tweet)
            .options(selectinload(Tweet.media_items))
            .where(
                Tweet.status == TweetStatus.PUBLISHED,
                Tweet.published_at >= now - timedelta(hours=SIMILAR_LOOKBACK_HOURS)
            )
            .order_by(Tweet.published_at.desc())
            .limit(20)
        )
        for published in recent_published.scalars().all():
            if _is_similar(tweet.content, published.content):
                return GuardDecision(False, '检测到与最近已发布推文高度相似，已拦截以降低风控概率')

        delay_seconds = random.randint(*RANDOM_DELAY_RANGE)
        return GuardDecision(True, delay_seconds=delay_seconds)


async def apply_publish_guard(tweet: Tweet) -> None:
    decision = await evaluate_publish_guard(tweet)
    if not decision.allowed:
        raise ValueError(decision.reason)
    if decision.delay_seconds > 0:
        logger.info('发帖保护延迟 %d 秒后继续，tweet_id=%s', decision.delay_seconds, tweet.id)
        await asyncio.sleep(decision.delay_seconds)
