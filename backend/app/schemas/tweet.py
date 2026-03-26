from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime
from app.models.tweet import TweetStatus, TweetType


class TweetBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=280)
    tweet_type: TweetType = TweetType.TEXT


class TweetCreate(TweetBase):
    media_ids: List[int] = []


class TweetUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=280)
    tweet_type: Optional[TweetType] = None
    media_ids: Optional[List[int]] = None


class TweetSchedule(BaseModel):
    scheduled_at: datetime


class MediaInTweet(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    filepath: str
    media_type: str


class TweetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    tweet_type: TweetType
    status: TweetStatus
    scheduled_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    twitter_id: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int
    created_at: datetime
    updated_at: datetime
    media_items: List[MediaInTweet] = []


class TweetListResponse(BaseModel):
    total: int
    items: List[TweetResponse]
