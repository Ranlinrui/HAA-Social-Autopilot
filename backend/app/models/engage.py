from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from app.database import Base


class EngageReply(Base):
    __tablename__ = "engage_replies"

    id = Column(Integer, primary_key=True, index=True)
    tweet_id = Column(String(50), unique=True, nullable=False, index=True)
    reply_id = Column(String(50), nullable=True)  # Twitter reply tweet ID
    tweet_text = Column(Text, nullable=True)
    author_username = Column(String(100), nullable=True)
    reply_content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
