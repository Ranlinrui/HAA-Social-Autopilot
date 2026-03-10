from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SQLEnum, ForeignKey, Table
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base


class TweetStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class TweetType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"


# 推文和素材的多对多关系表
tweet_media = Table(
    "tweet_media",
    Base.metadata,
    Column("tweet_id", Integer, ForeignKey("tweets.id"), primary_key=True),
    Column("media_id", Integer, ForeignKey("media.id"), primary_key=True)
)


class Tweet(Base):
    __tablename__ = "tweets"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    tweet_type = Column(SQLEnum(TweetType), default=TweetType.TEXT)
    status = Column(SQLEnum(TweetStatus), default=TweetStatus.DRAFT)

    scheduled_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    twitter_id = Column(String(50), nullable=True)  # 发布后的Twitter推文ID

    error_message = Column(Text, nullable=True)  # 发布失败的错误信息
    retry_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联素材
    media_items = relationship("Media", secondary=tweet_media, back_populates="tweets")
