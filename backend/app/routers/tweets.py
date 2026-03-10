from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models.tweet import Tweet, TweetStatus
from app.models.media import Media
from app.schemas.tweet import (
    TweetCreate, TweetUpdate, TweetResponse, TweetListResponse, TweetSchedule
)
from app.logger import setup_logger

router = APIRouter(prefix="/api/tweets", tags=["tweets"])
logger = setup_logger("tweets")


@router.get("", response_model=TweetListResponse)
async def get_tweets(
    status: Optional[TweetStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    query = select(Tweet).options(selectinload(Tweet.media_items))

    if status:
        query = query.where(Tweet.status == status)

    query = query.order_by(Tweet.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    tweets = result.scalars().all()

    # 获取总数
    count_query = select(func.count(Tweet.id))
    if status:
        count_query = count_query.where(Tweet.status == status)
    total = await db.execute(count_query)
    total = total.scalar()

    return TweetListResponse(total=total, items=tweets)


@router.post("", response_model=TweetResponse)
async def create_tweet(
    tweet_data: TweetCreate,
    db: AsyncSession = Depends(get_db)
):
    tweet = Tweet(
        content=tweet_data.content,
        tweet_type=tweet_data.tweet_type,
        status=TweetStatus.DRAFT
    )

    # 关联素材
    if tweet_data.media_ids:
        result = await db.execute(
            select(Media).where(Media.id.in_(tweet_data.media_ids))
        )
        media_items = result.scalars().all()
        tweet.media_items = list(media_items)

    db.add(tweet)
    await db.commit()
    await db.refresh(tweet)

    # 重新加载关联数据
    result = await db.execute(
        select(Tweet).options(selectinload(Tweet.media_items)).where(Tweet.id == tweet.id)
    )
    tweet = result.scalar_one()

    return tweet


@router.get("/{tweet_id}", response_model=TweetResponse)
async def get_tweet(
    tweet_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Tweet).options(selectinload(Tweet.media_items)).where(Tweet.id == tweet_id)
    )
    tweet = result.scalar_one_or_none()

    if not tweet:
        raise HTTPException(status_code=404, detail="Tweet not found")

    return tweet


@router.put("/{tweet_id}", response_model=TweetResponse)
async def update_tweet(
    tweet_id: int,
    tweet_data: TweetUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Tweet).options(selectinload(Tweet.media_items)).where(Tweet.id == tweet_id)
    )
    tweet = result.scalar_one_or_none()

    if not tweet:
        raise HTTPException(status_code=404, detail="Tweet not found")

    if tweet.status == TweetStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="Cannot edit published tweet")

    if tweet_data.content is not None:
        tweet.content = tweet_data.content
    if tweet_data.tweet_type is not None:
        tweet.tweet_type = tweet_data.tweet_type
    if tweet_data.media_ids is not None:
        result = await db.execute(
            select(Media).where(Media.id.in_(tweet_data.media_ids))
        )
        media_items = result.scalars().all()
        tweet.media_items = list(media_items)

    await db.commit()
    await db.refresh(tweet)

    return tweet


@router.delete("/{tweet_id}")
async def delete_tweet(
    tweet_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Tweet).where(Tweet.id == tweet_id)
    )
    tweet = result.scalar_one_or_none()

    if not tweet:
        raise HTTPException(status_code=404, detail="Tweet not found")

    await db.delete(tweet)
    await db.commit()

    return {"message": "Tweet deleted"}


@router.post("/{tweet_id}/schedule", response_model=TweetResponse)
async def schedule_tweet(
    tweet_id: int,
    schedule_data: TweetSchedule,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Tweet).options(selectinload(Tweet.media_items)).where(Tweet.id == tweet_id)
    )
    tweet = result.scalar_one_or_none()

    if not tweet:
        raise HTTPException(status_code=404, detail="Tweet not found")

    if tweet.status == TweetStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="Tweet already published")

    if schedule_data.scheduled_at <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="Scheduled time must be in the future")

    tweet.scheduled_at = schedule_data.scheduled_at
    tweet.status = TweetStatus.SCHEDULED

    await db.commit()
    await db.refresh(tweet)

    return tweet


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
        raise HTTPException(status_code=404, detail="Tweet not found")

    if tweet.status == TweetStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="Tweet already published")

    tweet.status = TweetStatus.PUBLISHING
    await db.commit()
    logger.info("开始发布推文 id=%d，内容: %.50s...", tweet_id, tweet.content)

    try:
        twitter_id = await publish_tweet(tweet)
        tweet.status = TweetStatus.PUBLISHED
        tweet.published_at = datetime.utcnow()
        tweet.twitter_id = twitter_id
        tweet.error_message = None
        logger.info("推文发布成功 id=%d，twitter_id=%s", tweet_id, twitter_id)
    except Exception as e:
        tweet.status = TweetStatus.FAILED
        tweet.error_message = str(e)
        tweet.retry_count += 1
        logger.error("推文发布失败 id=%d，错误: %s", tweet_id, e)

    await db.commit()
    await db.refresh(tweet)

    return tweet
