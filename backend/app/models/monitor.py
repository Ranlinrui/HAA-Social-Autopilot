from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base


class MonitoredAccount(Base):
    """Monitored Twitter accounts for tracking new tweets"""
    __tablename__ = "monitored_accounts"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(String(50), nullable=True)
    display_name = Column(String(100), nullable=True)
    priority = Column(Integer, default=2)  # 1=high (2min), 2=medium (5min), 3=low (15min)
    last_tweet_id = Column(String(50), nullable=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    # Auto-engage config
    auto_engage = Column(Boolean, default=False)       # Whether to auto reply/retweet
    engage_action = Column(String(20), default="reply")  # "reply", "retweet", "both"
    engage_delay = Column(Integer, default=90)         # Seconds to wait before acting
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class MonitorNotification(Base):
    """Notifications for new tweets from monitored accounts"""
    __tablename__ = "monitor_notifications"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, nullable=False, index=True)
    tweet_id = Column(String(50), unique=True, nullable=False, index=True)
    tweet_text = Column(Text, nullable=False)
    tweet_url = Column(String(200), nullable=False)
    author_username = Column(String(50), nullable=False)
    author_name = Column(String(100), nullable=False)
    tweet_created_at = Column(DateTime(timezone=True), nullable=False)
    notified_at = Column(DateTime(timezone=True), server_default=func.now())
    is_commented = Column(Boolean, default=False)
    comment_text = Column(Text, nullable=True)
    commented_at = Column(DateTime(timezone=True), nullable=True)
    # Auto-engage tracking
    auto_engage_status = Column(String(20), default="pending")  # pending/scheduled/done/failed/skipped
    auto_engage_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
