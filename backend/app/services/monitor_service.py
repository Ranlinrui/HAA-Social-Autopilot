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
                await asyncio.sleep(min(30, max(5, remaining)))
                continue

            try:
                async for db in get_db():
                    await self._check_all_accounts(db)
                    break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
            await asyncio.sleep(30)

    async def _check_all_accounts(self, db: AsyncSession):
        result = await db.execute(
            select(MonitoredAccount).where(MonitoredAccount.is_active == True)
        )
        accounts = result.scalars().all()
        if not accounts:
            return

        interval_per_account = max(5, 30 / len(accounts))

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

    def _should_check_account(self, account: MonitoredAccount) -> bool:
        if not account.last_checked_at:
            return True
        now = datetime.now(timezone.utc)
        last = account.last_checked_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        elapsed = (now - last).total_seconds()
        # Priority intervals: 1=60s, 2=180s, 3=600s
        intervals = {1: 60, 2: 180, 3: 600}
        return elapsed >= intervals.get(account.priority, 180)

    async def _check_account(self, db: AsyncSession, account: MonitoredAccount):
        if not account.user_id or not account.display_name:
            user = await get_user_profile(account.username)
            account.user_id = user.get("id") or account.username
            account.display_name = user.get("name") or account.username
            await db.commit()

        tweets = await get_user_timeline(account.username, count=5)
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
                asyncio.create_task(
                    self._auto_engage(notif.id, account.engage_action, delay)
                )
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
                    await db.commit()
                    return

                if action in ("reply", "both"):
                    content = await _generate_reply_content(
                        notif.tweet_text, notif.author_username
                    )
                    reply_id = await reply_tweet(notif.tweet_id, content)
                    notif.is_commented = True
                    notif.comment_text = content
                    notif.commented_at = datetime.now(timezone.utc)
                    logger.info(
                        f"Auto-replied to tweet {notif.tweet_id} "
                        f"from @{notif.author_username}, reply_id={reply_id}"
                    )

                if action in ("retweet", "both"):
                    await retweet_tweet(notif.tweet_id)
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
