from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.database import Base


class ConversationThread(Base):
    """
    Tracks reply threads where someone replied to our comment.
    Supports multi-turn conversations with auto/manual mode switching.
    """
    __tablename__ = "conversation_threads"

    id = Column(Integer, primary_key=True, index=True)
    account_key = Column(String(100), nullable=True, index=True)

    # The tweet we originally replied to
    root_tweet_id = Column(String(50), nullable=False, index=True)
    root_tweet_text = Column(Text, nullable=True)

    # Our original reply that started this thread
    our_reply_id = Column(String(50), nullable=False, index=True)
    our_reply_text = Column(Text, nullable=True)

    # The latest incoming mention we need to respond to
    latest_mention_id = Column(String(50), unique=True, nullable=False, index=True)
    latest_mention_text = Column(Text, nullable=False)
    from_username = Column(String(50), nullable=False)
    from_user_id = Column(String(50), nullable=True)
    mention_created_at = Column(DateTime(timezone=True), nullable=True)

    # Full conversation history as JSON array
    # Each item: {role: "us"|"them", text: str, tweet_id: str, at: ISO str}
    history = Column(JSON, default=list)

    # Status: pending / auto_replied / manual_replied / ignored
    status = Column(String(20), default="pending", index=True)

    # Mode: "auto" or "manual" (can override global setting per thread)
    mode = Column(String(10), default="manual")

    # Pre-generated reply for review (auto mode stages it here first)
    draft_reply = Column(Text, nullable=True)

    # The tweet id of our follow-up reply (after we respond)
    replied_tweet_id = Column(String(50), nullable=True)
    replied_text = Column(Text, nullable=True)
    replied_at = Column(DateTime(timezone=True), nullable=True)

    # Error info if auto reply failed
    auto_error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ConversationSetting(Base):
    """Global settings for the conversation follow-up system."""
    __tablename__ = "conversation_settings"

    id = Column(Integer, primary_key=True)
    # Global mode: "auto" or "manual"
    mode = Column(String(10), default="manual")
    # Poll interval in seconds
    poll_interval = Column(Integer, default=180)
    # Auto reply base delay in seconds
    auto_reply_delay = Column(Integer, default=120)
    # Whether the conversation poller is enabled
    enabled = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
