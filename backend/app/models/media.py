from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base
from app.models.tweet import tweet_media


class MediaType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"


class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    filepath = Column(String(500), nullable=False)
    media_type = Column(SQLEnum(MediaType), nullable=False)

    mime_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)  # bytes
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)

    tags = Column(String(500), nullable=True)  # 逗号分隔的标签

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联推文
    tweets = relationship("Tweet", secondary=tweet_media, back_populates="media_items")
