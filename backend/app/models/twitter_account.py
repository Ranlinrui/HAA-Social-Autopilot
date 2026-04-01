from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.database import Base


class TwitterAccount(Base):
    __tablename__ = "twitter_accounts"

    id = Column(Integer, primary_key=True, index=True)
    account_key = Column(String(100), unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=False, index=True)
    email = Column(String(255), nullable=True)
    password = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=False, index=True)
    last_login_status = Column(String(50), nullable=True)
    last_login_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
