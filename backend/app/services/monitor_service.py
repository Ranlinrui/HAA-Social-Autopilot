"""
Twitter Account Monitoring Service

Monitors specified Twitter accounts for new tweets and sends notifications.
Uses twikit to fetch user tweets with incremental ID comparison.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.monitor import MonitoredAccount, MonitorNotification
from app.services.twitter_api import get_twitter_client

logger = logging.getLogger(__name__)


class TwitterMonitorService:
    """Service for monitoring Twitter accounts"""

    def __init__(self):
        self.is_running = False
        self.monitor_task = None

    async def start(self):
        """Start the monitoring service"""
        if self.is_running:
            logger.warning("Monitor service already running")
            return

        self.is_running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Twitter monitor service started")

    async def stop(self):
        """Stop the monitoring service"""
        self.is_running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Twitter monitor service stopped")

    async def _monitor_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                async for db in get_db():
                    await self._check_all_accounts(db)
                    break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")

            # Wait before next cycle (60 seconds)
            await asyncio.sleep(60)

    async def _check_all_accounts(self, db: AsyncSession):
        """Check all active monitored accounts"""
        # Get all active accounts
        result = await db.execute(
            select(MonitoredAccount).where(MonitoredAccount.is_active == True)
        )
        accounts = result.scalars().all()

        if not accounts:
            return

        # Calculate interval per account to spread requests
        interval_per_account = 60 / len(accounts) if len(accounts) > 0 else 60

        for account in accounts:
            try:
                # Check if it's time to poll this account based on priority
                if not self._should_check_account(account):
                    continue

                await self._check_account(db, account)

                # Update last checked time
                account.last_checked_at = datetime.now(timezone.utc)
                await db.commit()

            except Exception as e:
                logger.error(f"Error checking account @{account.username}: {e}")

            # Spread requests evenly
            await asyncio.sleep(interval_per_account)

    def _should_check_account(self, account: MonitoredAccount) -> bool:
        """Determine if account should be checked based on priority and last check time"""
        if not account.last_checked_at:
            return True

        now = datetime.now(timezone.utc)
        last_checked = account.last_checked_at
        # Handle naive datetime from SQLite (no timezone info)
        if last_checked.tzinfo is None:
            last_checked = last_checked.replace(tzinfo=timezone.utc)
        elapsed = (now - last_checked).total_seconds()

        # Priority intervals: 1=120s, 2=300s, 3=900s
        intervals = {1: 120, 2: 300, 3: 900}
        required_interval = intervals.get(account.priority, 300)

        return elapsed >= required_interval

    async def _check_account(self, db: AsyncSession, account: MonitoredAccount):
        """Check a single account for new tweets"""
        try:
            client = await get_twitter_client()

            # Get user info if we don't have user_id yet
            if not account.user_id:
                user = await client.get_user_by_screen_name(account.username)
                account.user_id = user.id
                account.display_name = user.name
                await db.commit()

            # Fetch latest tweets
            tweets = await client.get_user_tweets(account.user_id, 'Tweets', count=5)

            if not tweets:
                return

            # Find new tweets (compare with last_tweet_id)
            new_tweets = []
            for tweet in tweets:
                if account.last_tweet_id and tweet.id == account.last_tweet_id:
                    break
                new_tweets.append(tweet)

            # Update last_tweet_id to the latest
            if tweets:
                account.last_tweet_id = tweets[0].id

            # Create notifications for new tweets
            for tweet in reversed(new_tweets):  # Process oldest first
                await self._create_notification(db, account, tweet)

            if new_tweets:
                logger.info(f"Found {len(new_tweets)} new tweets from @{account.username}")

        except Exception as e:
            logger.error(f"Error fetching tweets for @{account.username}: {e}")
            raise

    async def _create_notification(self, db: AsyncSession, account: MonitoredAccount, tweet):
        """Create a notification for a new tweet"""
        try:
            # Check if notification already exists
            result = await db.execute(
                select(MonitorNotification).where(MonitorNotification.tweet_id == tweet.id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                return

            # Create notification
            notification = MonitorNotification(
                account_id=account.id,
                tweet_id=tweet.id,
                tweet_text=tweet.text or tweet.full_text or "",
                tweet_url=f"https://twitter.com/{account.username}/status/{tweet.id}",
                author_username=account.username,
                author_name=account.display_name or account.username,
                tweet_created_at=tweet.created_at_datetime,
            )

            db.add(notification)
            await db.commit()

            logger.info(f"Created notification for tweet {tweet.id} from @{account.username}")

            # TODO: Send Telegram notification here

        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            await db.rollback()


# Global monitor service instance
monitor_service = TwitterMonitorService()
