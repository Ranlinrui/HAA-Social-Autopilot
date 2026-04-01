from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import datetime, timezone

from app.database import get_db
from app.models.tweet import Tweet, TweetStatus, TweetType
from app.models.media import Media, MediaType
from app.schemas.tweet import (
    TweetCreate, TweetUpdate, TweetResponse, TweetListResponse, TweetSchedule
)
from app.logger import setup_logger
from app.services.twitter_account_store import get_effective_account_key
from app.services.tweet_guard import apply_publish_guard

router = APIRouter(prefix="/api/tweets", tags=["tweets"])
logger = setup_logger("tweets")


def _error_detail(exc: Exception, fallback: str) -> str:
    detail = str(exc).strip()
    return detail or fallback


def infer_tweet_type(media_items: list[Media]) -> TweetType:
    if any(media.media_type == MediaType.VIDEO for media in media_items):
        return TweetType.VIDEO
    if media_items:
        return TweetType.IMAGE
    return TweetType.TEXT

@router.get("", response_model=TweetListResponse)
async def get_tweets(
    status: Optional[TweetStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    try:
        account_key = await get_effective_account_key()
        query = select(Tweet).options(selectinload(Tweet.media_items))
        if account_key:
            query = query.where(Tweet.account_key == account_key)

        if status:
            query = query.where(Tweet.status == status)

        query = query.order_by(Tweet.created_at.desc()).offset(skip).limit(limit)

        result = await db.execute(query)
        tweets = result.scalars().all()

        count_query = select(func.count(Tweet.id))
        if account_key:
            count_query = count_query.where(Tweet.account_key == account_key)
        if status:
            count_query = count_query.where(Tweet.status == status)
        total = await db.execute(count_query)
        total = total.scalar()

        return TweetListResponse(total=total, items=tweets)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "加载推文列表失败"))


@router.post("", response_model=TweetResponse)
async def create_tweet(
    tweet_data: TweetCreate,
    db: AsyncSession = Depends(get_db)
):
    try:
        account_key = await get_effective_account_key()
        tweet = Tweet(
            account_key=account_key,
            content=tweet_data.content,
            tweet_type=tweet_data.tweet_type,
            status=TweetStatus.DRAFT
        )

        media_items: list[Media] = []

        if tweet_data.media_ids:
            result = await db.execute(
                select(Media).where(Media.id.in_(tweet_data.media_ids))
            )
            media_items = list(result.scalars().all())
            tweet.media_items = media_items

        tweet.tweet_type = infer_tweet_type(media_items) if media_items else tweet_data.tweet_type

        db.add(tweet)
        await db.commit()
        await db.refresh(tweet)

        result = await db.execute(
            select(Tweet).options(selectinload(Tweet.media_items)).where(Tweet.id == tweet.id)
        )
        tweet = result.scalar_one()

        return tweet
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "创建推文失败"))


@router.get("/{tweet_id}", response_model=TweetResponse)
async def get_tweet(
    tweet_id: int,
    db: AsyncSession = Depends(get_db)
):
    try:
        result = await db.execute(
            select(Tweet).options(selectinload(Tweet.media_items)).where(Tweet.id == tweet_id)
        )
        tweet = result.scalar_one_or_none()

        if not tweet:
            raise HTTPException(status_code=404, detail="推文不存在")

        return tweet
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "加载推文详情失败"))


@router.put("/{tweet_id}", response_model=TweetResponse)
async def update_tweet(
    tweet_id: int,
    tweet_data: TweetUpdate,
    db: AsyncSession = Depends(get_db)
):
    try:
        result = await db.execute(
            select(Tweet).options(selectinload(Tweet.media_items)).where(Tweet.id == tweet_id)
        )
        tweet = result.scalar_one_or_none()

        if not tweet:
            raise HTTPException(status_code=404, detail="推文不存在")

        if tweet.status == TweetStatus.PUBLISHED:
            raise HTTPException(status_code=400, detail="已发布推文不能编辑")

        if tweet_data.content is not None:
            tweet.content = tweet_data.content
        if tweet_data.tweet_type is not None:
            tweet.tweet_type = tweet_data.tweet_type
        if tweet_data.media_ids is not None:
            result = await db.execute(
                select(Media).where(Media.id.in_(tweet_data.media_ids))
            )
            media_items = list(result.scalars().all())
            tweet.media_items = media_items
            tweet.tweet_type = infer_tweet_type(media_items) if media_items else TweetType.TEXT

        await db.commit()
        await db.refresh(tweet)

        return tweet
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "更新推文失败"))


@router.delete("/{tweet_id}")
async def delete_tweet(
    tweet_id: int,
    db: AsyncSession = Depends(get_db)
):
    try:
        result = await db.execute(
            select(Tweet).where(Tweet.id == tweet_id)
        )
        tweet = result.scalar_one_or_none()

        if not tweet:
            raise HTTPException(status_code=404, detail="推文不存在")

        await db.delete(tweet)
        await db.commit()

        return {"message": "推文已删除"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "删除推文失败"))


@router.post("/{tweet_id}/schedule", response_model=TweetResponse)
async def schedule_tweet(
    tweet_id: int,
    schedule_data: TweetSchedule,
    db: AsyncSession = Depends(get_db)
):
    try:
        result = await db.execute(
            select(Tweet).options(selectinload(Tweet.media_items)).where(Tweet.id == tweet_id)
        )
        tweet = result.scalar_one_or_none()

        if not tweet:
            raise HTTPException(status_code=404, detail="推文不存在")

        if tweet.status == TweetStatus.PUBLISHED:
            raise HTTPException(status_code=400, detail="推文已发布")

        if schedule_data.scheduled_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="定时发布时间必须晚于当前时间")

        tweet.scheduled_at = schedule_data.scheduled_at
        tweet.status = TweetStatus.SCHEDULED

        await db.commit()
        await db.refresh(tweet)

        return tweet
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "设置推文排期失败"))


@router.post("/{tweet_id}/publish", response_model=TweetResponse)
async def publish_tweet_now(
    tweet_id: int,
    db: AsyncSession = Depends(get_db)
):
    from app.services.twitter_api import publish_tweet

    result = await db.execute(
        select(Tweet).options(selectinload(Tweet.media_items)).where(Tweet.id == tweet_id)
    )
    tweet = result.scalar_one_or_none()

    if not tweet:
        raise HTTPException(status_code=404, detail="推文不存在")

    if tweet.status == TweetStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="推文已发布")

    tweet.status = TweetStatus.PUBLISHING
    tweet.error_message = None
    await db.commit()
    logger.info("开始发布推文 id=%d，内容: %.50s...", tweet_id, tweet.content)

    try:
        await apply_publish_guard(tweet)
        twitter_id = await publish_tweet(tweet)
        tweet.status = TweetStatus.PUBLISHED
        tweet.published_at = datetime.now(timezone.utc)
        tweet.twitter_id = twitter_id
        tweet.error_message = None
        logger.info("推文发布成功 id=%d，twitter_id=%s", tweet_id, twitter_id)
    except Exception as e:
        tweet.status = TweetStatus.FAILED
        detail = str(e).strip() or repr(e)
        tweet.error_message = detail
        tweet.retry_count += 1
        logger.exception("推文发布失败 id=%d，错误: %s", tweet_id, detail)

    await db.commit()
    await db.refresh(tweet)

    return tweet
