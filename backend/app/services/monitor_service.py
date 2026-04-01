"""
Twitter Account Monitoring Service

Monitors specified Twitter accounts for new tweets.
When auto_engage is enabled on an account, new tweets are queued for
automatic reply/retweet after a configurable delay (default 90s).
"""

import asyncio
import logging
import random
from datetime import datetime, timezone

from app.config import settings
from app.services.twitter_auth_backoff import (
    build_auth_backoff_until,
    build_automation_backoff_until,
    is_auth_failure,
    is_automation_failure,
    is_backoff_active,
    seconds_until_backoff_expires,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.monitor import MonitoredAccount, MonitorNotification
from app.services.twitter_account_store import using_twitter_account
from app.services.twitter_auto_action_guard import get_twitter_auto_action_guard
from app.services.twitter_engage_strategy import get_twitter_engage_strategy
from app.services.twitter_api import get_user_profile, get_user_timeline, reply_tweet, retweet_tweet

logger = logging.getLogger(__name__)


def _human_like_delay(base_delay: int) -> int:
    """
    Generate a human-like delay to avoid bot detection patterns.

    Strategy:
    - Apply a random multiplier (0.6x to 2.0x) to the base delay
    - Add gaussian noise for natural variation
    - Occasionally add a longer pause (simulating distraction)
    - Clamp to [30, 600] seconds
    """
    # Random multiplier: most of the time near 1x, occasionally much longer
    multiplier = random.triangular(0.6, 2.0, 1.0)
    delay = base_delay * multiplier

    # Add gaussian noise (std = 20% of base)
    noise = random.gauss(0, base_delay * 0.2)
    delay += noise

    # 15% chance of a longer "distracted human" pause (extra 60-180s)
    if random.random() < 0.15:
        delay += random.uniform(60, 180)

    return max(30, min(600, int(delay)))


async def _generate_reply_content(tweet_text: str, author_username: str) -> str:
    """Generate reply content using the same prompt logic as engage router."""
    from app.services.llm_service import generate_tweet_content

    has_chinese = any('\u4e00' <= c <= '\u9fff' for c in tweet_text)
    language = "zh" if has_chinese else "en"

    if language == "zh":
        prompt = f"""你是一个在 Twitter 上活跃的加密货币玩家，有自己的交易经历和观点，偶尔会提到自己用过的工具。

原推文：
@{author_username}：{tweet_text}

---

写一条回复。要求：

**风格**
- 口语化，像发微博/朋友圈那种随手一写的感觉
- 有态度，不是复读机，可以赞同、可以反驳、可以调侃、可以共情
- 短句为主，可以有语气词（哈、确实、emmm、说真的、不过、唉）
- 偶尔用表情，但不堆砌（😅🙄😂👀 这类真人常用的）

**关于产品植入（Hyper Alpha Arena）**
- 大多数时候不需要提，先把互动做好
- 只有当推文明确在聊：爆仓/风控/回测/量化策略/AI交易工具，才考虑带一句
- 带的时候要像随口一提，不是广告词：
  - 好："回测这块 Hyper Alpha Arena 做得还行，数据挺全的"
  - 好："我之前也踩过这坑，后来用 Hyper Alpha Arena 跑了下回测才搞清楚"
  - 差："你可以试试 Hyper Alpha Arena，它有自动风控功能！"
  - 差："建议用用 Hyper Alpha Arena，功能很强大"
- 绝对不要每条都提，不要用感叹号推荐，不要列功能点

**硬规则**
- 230字符以内，句子要完整
- 提到产品时必须写完整名字 "Hyper Alpha Arena"，不能缩写成 HAA，不能用"这个平台""这个工具"等模糊代称
- 不用 🤖💡🚀✨ 这类营销号表情

直接输出回复内容，不要任何说明。"""
    else:
        prompt = f"""You're a crypto trader on Twitter — opinionated, been around, occasionally mention tools you've used.

Tweet:
@{author_username}: {tweet_text}

---

Write a reply. Requirements:

**Tone**
- Casual, like something you'd actually type on your phone
- Have a real take — agree, push back, joke around, or just relate
- Short sentences, natural rhythm, maybe a filler word or two (honestly, ngl, tbh, lol)
- Emoji if it fits, but don't overdo it (😅🙄😂👀 type, not 🚀💡✨)

**On product mentions (Hyper Alpha Arena)**
- Most replies don't need it — focus on the conversation first
- Only bring it up if the tweet is specifically about: liquidation, risk management, backtesting, quant strategies, AI trading tools
- When you do mention it, make it sound offhand, not like an ad:
  - Good: "backtesting on Hyper Alpha Arena actually helped me figure this out"
  - Good: "ngl Hyper Alpha Arena's risk controls saved me from a few dumb trades"
  - Bad: "You could try Hyper Alpha Arena, it has automated risk management!"
  - Bad: "I recommend checking out Hyper Alpha Arena for its powerful features"
- Never mention it in every reply, no exclamation point pitches, no feature lists

**Hard rules**
- Under 230 characters, complete sentence
- When mentioning the product, always use the full name "Hyper Alpha Arena" — never abbreviate to HAA, never use vague references like "the platform" or "this tool"
- No 🤖💡🚀✨ marketing emojis

Output only the reply, nothing else."""

    content, _ = await generate_tweet_content(
        topic=prompt,
        language=language,
        max_length=250,
        template_prompt="{topic}"
    )
    return content


class TwitterMonitorService:
    """Service for monitoring Twitter accounts and auto-engaging with new tweets."""

    def __init__(self):
        self.is_running = False
        self.monitor_task = None
        self.auth_backoff_until = None
        self._active_auto_engage_tasks: set[int] = set()

    async def start(self):
        if self.is_running:
            logger.warning("Monitor service already running")
            return
        self.is_running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Twitter monitor service started")

    async def stop(self):
        self.is_running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Twitter monitor service stopped")

    async def _monitor_loop(self):
        while self.is_running:
            if is_backoff_active(self.auth_backoff_until):
                remaining = seconds_until_backoff_expires(self.auth_backoff_until)
                await asyncio.sleep(min(settings.monitor_loop_interval_seconds, max(30, remaining)))
                continue

            try:
                async for db in get_db():
                    await self._check_all_accounts(db)
                    break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
            await asyncio.sleep(settings.monitor_loop_interval_seconds)

    async def _check_all_accounts(self, db: AsyncSession):
        await self._recover_scheduled_notifications(db)

        result = await db.execute(
            select(MonitoredAccount).where(MonitoredAccount.is_active == True)
        )
        accounts = result.scalars().all()
        if not accounts:
            return

        interval_per_account = max(15, settings.monitor_loop_interval_seconds / max(len(accounts), 1))

        for account in accounts:
            try:
                if not self._should_check_account(account):
                    continue
                await self._check_account(db, account)
                account.last_checked_at = datetime.now(timezone.utc)
                await db.commit()
            except Exception as e:
                if is_auth_failure(e):
                    self.auth_backoff_until = build_auth_backoff_until()
                    logger.warning(
                        "Twitter auth failed while checking @%s, entering monitor backoff until %s",
                        account.username,
                        self.auth_backoff_until.isoformat(),
                    )
                    break
                if is_automation_failure(e):
                    self.auth_backoff_until = build_automation_backoff_until()
                    logger.warning(
                        "Twitter automation risk triggered while checking @%s, entering monitor backoff until %s",
                        account.username,
                        self.auth_backoff_until.isoformat(),
                    )
                    break
                logger.error(f"Error checking account @{account.username}: {e}")
            await asyncio.sleep(interval_per_account)

    def _schedule_auto_engage_task(self, notification_id: int, action: str, delay: int):
        if notification_id in self._active_auto_engage_tasks:
            return

        self._active_auto_engage_tasks.add(notification_id)
        task = asyncio.create_task(self._auto_engage(notification_id, action, delay))

        def _cleanup(_task):
            self._active_auto_engage_tasks.discard(notification_id)

        task.add_done_callback(_cleanup)

    async def _recover_scheduled_notifications(self, db: AsyncSession):
        result = await db.execute(
            select(MonitorNotification, MonitoredAccount)
            .join(MonitoredAccount, MonitoredAccount.id == MonitorNotification.account_id)
            .where(
                MonitorNotification.auto_engage_status == "scheduled",
                MonitorNotification.is_commented == False,
                MonitoredAccount.auto_engage == True,
                MonitoredAccount.is_active == True,
            )
            .order_by(MonitorNotification.notified_at.desc())
            .limit(100)
        )
        rows = result.all()
        if not rows:
            return

        now = datetime.now(timezone.utc)
        dirty = False
        for notif, account in rows:
            if notif.id in self._active_auto_engage_tasks:
                continue

            notified_at = notif.notified_at or now
            if notified_at.tzinfo is None:
                notified_at = notified_at.replace(tzinfo=timezone.utc)
            age_seconds = max(0, int((now - notified_at).total_seconds()))

            if age_seconds > 6 * 3600:
                notif.auto_engage_status = "skipped"
                notif.auto_engage_error = "自动互动任务在服务重启后已过期，已跳过"
                dirty = True
                continue

            remaining = max(0, int(account.engage_delay or 0) - age_seconds)
            self._schedule_auto_engage_task(notif.id, account.engage_action, remaining)
            logger.info(
                "Recovered scheduled auto-engage for notification %s in %ss (action=%s)",
                notif.id,
                remaining,
                account.engage_action,
            )

        if dirty:
            await db.commit()

    def _should_check_account(self, account: MonitoredAccount) -> bool:
        if not account.last_checked_at:
            return True
        now = datetime.now(timezone.utc)
        last = account.last_checked_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        elapsed = (now - last).total_seconds()
        # Priority intervals are deliberately stretched in low-traffic mode.
        intervals = {
            1: settings.monitor_priority_high_interval_seconds,
            2: settings.monitor_priority_medium_interval_seconds,
            3: settings.monitor_priority_low_interval_seconds,
        }
        return elapsed >= intervals.get(account.priority, 180)

    async def _check_account(self, db: AsyncSession, account: MonitoredAccount):
        async with using_twitter_account(account.account_key):
            if not account.user_id or not account.display_name:
                user = await get_user_profile(account.username)
                account.user_id = user.get("id") or account.username
                account.display_name = user.get("name") or account.username
                await db.commit()

            tweets = await get_user_timeline(account.username, count=settings.monitor_timeline_fetch_count)
        if not tweets:
            return

        new_tweets = []
        for tweet in tweets:
            if account.last_tweet_id and tweet["id"] == account.last_tweet_id:
                break
            new_tweets.append(tweet)

        if tweets:
            account.last_tweet_id = tweets[0]["id"]

        for tweet in reversed(new_tweets):
            notif = await self._create_notification(db, account, tweet)
            if notif and account.auto_engage:
                delay = _human_like_delay(account.engage_delay)
                self._schedule_auto_engage_task(notif.id, account.engage_action, delay)
                logger.info(
                    f"Scheduled auto-engage for tweet {tweet['id']} from @{account.username} "
                    f"in {delay}s (action={account.engage_action})"
                )

        if new_tweets:
            logger.info(f"Found {len(new_tweets)} new tweets from @{account.username}")

    async def _create_notification(
        self, db: AsyncSession, account: MonitoredAccount, tweet
    ):
        result = await db.execute(
            select(MonitorNotification).where(MonitorNotification.tweet_id == tweet["id"])
        )
        if result.scalar_one_or_none():
            return None

        tweet_created_at = tweet.get("created_at_datetime") or datetime.now(timezone.utc)

        notif = MonitorNotification(
            account_key=account.account_key,
            account_id=account.id,
            tweet_id=tweet["id"],
            tweet_text=tweet.get("text", ""),
            tweet_url=tweet.get("url") or f"https://x.com/{account.username}/status/{tweet['id']}",
            author_username=tweet.get("author_username") or account.username,
            author_name=tweet.get("author_name") or account.display_name or account.username,
            tweet_created_at=tweet_created_at,
            auto_engage_status="scheduled" if account.auto_engage else "skipped",
        )
        db.add(notif)
        await db.commit()
        await db.refresh(notif)
        logger.info(f"Created notification for tweet {tweet['id']} from @{account.username}")
        return notif

    async def _auto_engage(self, notification_id: int, action: str, delay: int):
        """Wait for delay then execute reply/retweet. Runs as a background task."""
        await asyncio.sleep(delay)

        async for db in get_db():
            try:
                result = await db.execute(
                    select(MonitorNotification).where(MonitorNotification.id == notification_id)
                )
                notif = result.scalar_one_or_none()
                if not notif:
                    return
                # Skip if already manually handled
                if notif.is_commented:
                    notif.auto_engage_status = "skipped"
                    notif.auto_engage_error = "已被人工处理，自动互动已跳过"
                    await db.commit()
                    return

                guard = get_twitter_auto_action_guard()
                strategy = get_twitter_engage_strategy()
                choice = await strategy.choose_account_for_auto_engage()
                if choice is None:
                    notif.auto_engage_status = "skipped"
                    notif.auto_engage_error = "当前没有可用的矩阵账号可执行自动互动"
                    await db.commit()
                    return
                actor_account_key = choice.account_key
                notif.account_key = actor_account_key

                if action in ("reply", "both"):
                    strategy_skip = strategy.should_skip_auto_engage(
                        account_key=actor_account_key,
                        pool_size=choice.pool_size,
                        action="reply",
                    )
                    if strategy_skip:
                        notif.auto_engage_status = "skipped"
                        notif.auto_engage_error = strategy_skip
                        await db.commit()
                        logger.info(
                            "Skipped auto-reply for notification %s: %s",
                            notification_id,
                            strategy_skip,
                        )
                        return
                    guard_error = guard.check_allowed(
                        account_key=actor_account_key,
                        action="reply",
                        min_interval_seconds=settings.auto_action_min_interval_seconds,
                        per_hour_limit=settings.auto_reply_hourly_limit,
                        per_day_limit=settings.auto_action_daily_limit,
                    )
                    if guard_error:
                        notif.auto_engage_status = "skipped"
                        notif.auto_engage_error = guard_error
                        await db.commit()
                        logger.info(
                            "Skipped auto-reply for notification %s: %s",
                            notification_id,
                            guard_error,
                        )
                        return
                    async with using_twitter_account(actor_account_key):
                        content = await _generate_reply_content(
                            notif.tweet_text, notif.author_username
                        )
                        reply_id = await reply_tweet(notif.tweet_id, content)
                    guard.record_success(account_key=actor_account_key, action="reply")
                    notif.is_commented = True
                    notif.comment_text = content
                    notif.commented_at = datetime.now(timezone.utc)
                    logger.info(
                        f"Auto-replied to tweet {notif.tweet_id} "
                        f"from @{notif.author_username}, reply_id={reply_id}"
                    )

                if action in ("retweet", "both"):
                    strategy_skip = strategy.should_skip_auto_engage(
                        account_key=actor_account_key,
                        pool_size=choice.pool_size,
                        action="retweet",
                    )
                    if strategy_skip and action == "retweet":
                        notif.auto_engage_status = "skipped"
                        notif.auto_engage_error = strategy_skip
                        await db.commit()
                        logger.info(
                            "Skipped auto-retweet for notification %s: %s",
                            notification_id,
                            strategy_skip,
                        )
                        return
                    guard_error = guard.check_allowed(
                        account_key=actor_account_key,
                        action="retweet",
                        min_interval_seconds=settings.auto_action_min_interval_seconds,
                        per_hour_limit=settings.auto_retweet_hourly_limit,
                        per_day_limit=settings.auto_action_daily_limit,
                    )
                    if guard_error:
                        if action == "retweet":
                            notif.auto_engage_status = "skipped"
                            notif.auto_engage_error = guard_error
                            await db.commit()
                            logger.info(
                                "Skipped auto-retweet for notification %s: %s",
                                notification_id,
                                guard_error,
                            )
                            return
                        notif.auto_engage_error = guard_error
                    elif strategy_skip:
                        notif.auto_engage_error = strategy_skip
                    else:
                        async with using_twitter_account(actor_account_key):
                            await retweet_tweet(notif.tweet_id)
                        guard.record_success(account_key=actor_account_key, action="retweet")
                        if not notif.is_commented:
                            notif.is_commented = True
                            notif.comment_text = "[retweet]"
                            notif.commented_at = datetime.now(timezone.utc)
                        logger.info(
                            f"Auto-retweeted tweet {notif.tweet_id} from @{notif.author_username}"
                        )

                notif.auto_engage_status = "done"
                await db.commit()

            except Exception as e:
                if is_automation_failure(e):
                    self.auth_backoff_until = build_automation_backoff_until()
                    logger.warning(
                        "Twitter automation risk triggered while auto-engaging notification %s, entering monitor backoff until %s",
                        notification_id,
                        self.auth_backoff_until.isoformat(),
                    )
                else:
                    logger.error(f"Auto-engage failed for notification {notification_id}: {e}")
                try:
                    result = await db.execute(
                        select(MonitorNotification).where(MonitorNotification.id == notification_id)
                    )
                    notif = result.scalar_one_or_none()
                    if notif:
                        notif.auto_engage_status = "failed"
                        notif.auto_engage_error = str(e)
                        await db.commit()
                except Exception:
                    pass
            break


monitor_service = TwitterMonitorService()
