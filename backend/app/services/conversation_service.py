"""
Conversation Follow-up Service

Polls Twitter mention notifications to detect when someone replies to our comments.
Supports auto mode (LLM reply after delay) and manual mode (queue for human review).
Multi-turn conversation history is maintained per thread.
"""

import asyncio
import logging
import random
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.conversation import ConversationThread, ConversationSetting
from app.services.twitter_api import get_mentions, reply_tweet

logger = logging.getLogger(__name__)

# Tracks the most recent notification_id we've processed to avoid reprocessing
_last_seen_notification_id: str | None = None


def _human_like_delay(base_delay: int) -> int:
    multiplier = random.triangular(0.6, 2.0, 1.0)
    delay = base_delay * multiplier
    noise = random.gauss(0, base_delay * 0.2)
    delay += noise
    if random.random() < 0.15:
        delay += random.uniform(60, 180)
    return max(30, min(600, int(delay)))


async def _generate_followup_reply(history: list, from_username: str, latest_text: str) -> str:
    """Generate a contextual follow-up reply using conversation history."""
    from app.services.llm_service import generate_tweet_content

    has_chinese = any('\u4e00' <= c <= '\u9fff' for c in latest_text)
    language = "zh" if has_chinese else "en"

    # Build conversation context string
    context_lines = []
    for turn in history[-6:]:  # Last 6 turns for context
        role_label = "Me" if turn["role"] == "us" else f"@{from_username}"
        context_lines.append(f"{role_label}: {turn['text']}")
    context_str = "\n".join(context_lines)

    if language == "zh":
        prompt = f"""你是一个在 Twitter 上活跃的加密货币玩家，有自己的交易经历和观点，正在进行一段对话。

对话历史：
{context_str}

@{from_username} 最新回复：{latest_text}

---

写一条跟进回复。要求：

**风格**
- 延续对话语境，不要重复已说过的内容
- 口语化，像发微博/朋友圈那种随手一写的感觉
- 有态度，可以赞同、反驳、调侃、共情
- 短句为主，可以有语气词（哈、确实、emmm、说真的、不过）
- 偶尔用表情，但不堆砌（😅🙄😂👀 这类真人常用的）

**关于产品植入（Hyper Alpha Arena）**
- 大多数时候不需要提，先把对话接好
- 只有当话题明确在聊：爆仓/风控/回测/量化策略/AI交易工具，才考虑带一句
- 带的时候要像随口一提，不是广告词：
  - 好："回测这块 Hyper Alpha Arena 做得还行，数据挺全的"
  - 差："你可以试试 Hyper Alpha Arena，它有自动风控功能！"
- 绝对不要每条都提，不要用感叹号推荐，不要列功能点

**硬规则**
- 230字符以内，句子要完整
- 提到产品时必须写完整名字 "Hyper Alpha Arena"，不能缩写成 HAA，不能用"这个平台""这个工具"等模糊代称
- 不用 🤖💡🚀✨ 这类营销号表情

直接输出回复内容，不要任何说明。"""
    else:
        prompt = f"""You're a crypto trader on Twitter — opinionated, been around, continuing a conversation.

Conversation history:
{context_str}

@{from_username} just replied: {latest_text}

---

Write a follow-up reply. Requirements:

**Tone**
- Continue naturally, don't repeat what was already said
- Casual, like something you'd actually type on your phone
- Have a real take — agree, push back, joke around, or just relate
- Short sentences, natural rhythm, maybe a filler word or two (honestly, ngl, tbh, lol)
- Emoji if it fits, but don't overdo it (😅🙄😂👀 type, not 🚀💡✨)

**On product mentions (Hyper Alpha Arena)**
- Most replies don't need it — keep the conversation going first
- Only bring it up if the topic is specifically about: liquidation, risk management, backtesting, quant strategies, AI trading tools
- When you do mention it, make it sound offhand, not like an ad:
  - Good: "backtesting on Hyper Alpha Arena actually helped me figure this out"
  - Bad: "You could try Hyper Alpha Arena, it has automated risk management!"
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


class ConversationService:
    """Polls mentions and manages reply threads."""

    def __init__(self):
        self.is_running = False
        self.poll_task = None

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.poll_task = asyncio.create_task(self._poll_loop())
        logger.info("Conversation service started")

    async def stop(self):
        self.is_running = False
        if self.poll_task:
            self.poll_task.cancel()
            try:
                await self.poll_task
            except asyncio.CancelledError:
                pass
        logger.info("Conversation service stopped")

    async def _get_settings(self, db: AsyncSession) -> ConversationSetting:
        result = await db.execute(select(ConversationSetting).where(ConversationSetting.id == 1))
        settings = result.scalar_one_or_none()
        if not settings:
            settings = ConversationSetting(id=1)
            db.add(settings)
            await db.commit()
            await db.refresh(settings)
        return settings

    async def _poll_loop(self):
        global _last_seen_notification_id
        while self.is_running:
            try:
                async for db in get_db():
                    cfg = await self._get_settings(db)
                    if not cfg.enabled:
                        break
                    await self._process_mentions(db, cfg)
                    break
            except Exception as e:
                logger.error("Error in conversation poll loop: %s", e)

            # Re-fetch interval from DB each cycle
            try:
                async for db in get_db():
                    cfg = await self._get_settings(db)
                    interval = cfg.poll_interval
                    break
            except Exception:
                interval = 180

            await asyncio.sleep(interval)

    async def _process_mentions(self, db: AsyncSession, cfg: ConversationSetting):
        global _last_seen_notification_id
        try:
            mentions = await get_mentions(count=40)
        except Exception as e:
            logger.warning("Could not fetch mentions: %s", e)
            return

        if not mentions:
            return

        new_mentions = []
        for m in mentions:
            if _last_seen_notification_id and m["notification_id"] == _last_seen_notification_id:
                break
            new_mentions.append(m)

        if mentions:
            _last_seen_notification_id = mentions[0]["notification_id"]

        if not new_mentions:
            return

        logger.info("Processing %d new mentions", len(new_mentions))

        for mention in reversed(new_mentions):
            try:
                await self._handle_mention(db, mention, cfg)
            except Exception as e:
                logger.error("Error handling mention %s: %s", mention.get("tweet_id"), e)

    async def _handle_mention(self, db: AsyncSession, mention: dict, cfg: ConversationSetting):
        """
        Check if this mention is a reply to one of our tweets.
        If so, create or update a ConversationThread.
        """
        in_reply_to = mention.get("in_reply_to")
        if not in_reply_to:
            return

        # Check if this mention already exists
        existing = await db.execute(
            select(ConversationThread).where(
                ConversationThread.latest_mention_id == mention["tweet_id"]
            )
        )
        if existing.scalar_one_or_none():
            return

        # Find if in_reply_to matches any of our reply IDs
        # Check EngageReply table and existing ConversationThreads
        from app.models.engage import EngageReply
        engage_result = await db.execute(
            select(EngageReply).where(EngageReply.reply_id == in_reply_to)
        )
        engage_reply = engage_result.scalar_one_or_none()

        thread_result = await db.execute(
            select(ConversationThread).where(
                ConversationThread.replied_tweet_id == in_reply_to
            )
        )
        parent_thread = thread_result.scalar_one_or_none()

        if not engage_reply and not parent_thread:
            # Not a reply to our content, skip
            return

        # Build history
        if parent_thread:
            history = list(parent_thread.history or [])
            root_tweet_id = parent_thread.root_tweet_id
            root_tweet_text = parent_thread.root_tweet_text
            our_reply_id = in_reply_to
            our_reply_text = parent_thread.replied_text
        else:
            history = [
                {
                    "role": "us",
                    "text": engage_reply.reply_content or "",
                    "tweet_id": engage_reply.reply_id,
                    "at": engage_reply.created_at.isoformat() if engage_reply.created_at else "",
                }
            ]
            root_tweet_id = engage_reply.tweet_id
            root_tweet_text = engage_reply.tweet_text
            our_reply_id = engage_reply.reply_id
            our_reply_text = engage_reply.reply_content

        # Append the incoming mention to history
        history.append({
            "role": "them",
            "text": mention["tweet_text"],
            "tweet_id": mention["tweet_id"],
            "at": mention.get("created_at", ""),
        })

        mention_dt = mention.get("created_at_datetime")
        if isinstance(mention_dt, str):
            try:
                mention_dt = datetime.fromisoformat(mention_dt)
            except Exception:
                mention_dt = None

        thread = ConversationThread(
            root_tweet_id=root_tweet_id,
            root_tweet_text=root_tweet_text,
            our_reply_id=our_reply_id,
            our_reply_text=our_reply_text,
            latest_mention_id=mention["tweet_id"],
            latest_mention_text=mention["tweet_text"],
            from_username=mention["from_username"],
            from_user_id=mention.get("from_user_id"),
            mention_created_at=mention_dt,
            history=history,
            status="pending",
            mode=cfg.mode,
        )
        db.add(thread)
        await db.commit()
        await db.refresh(thread)

        logger.info(
            "New conversation thread %d from @%s (reply to %s)",
            thread.id, mention["from_username"], in_reply_to
        )

        if cfg.mode == "auto":
            # Pre-generate draft immediately, then schedule send
            try:
                draft = await _generate_followup_reply(
                    history, mention["from_username"], mention["tweet_text"]
                )
                thread.draft_reply = draft
                await db.commit()
            except Exception as e:
                logger.error("Failed to pre-generate draft for thread %d: %s", thread.id, e)

            delay = _human_like_delay(cfg.auto_reply_delay)
            asyncio.create_task(self._auto_reply(thread.id, delay))
            logger.info("Scheduled auto-reply for thread %d in %ds", thread.id, delay)

    async def _auto_reply(self, thread_id: int, delay: int):
        """Wait then send the pre-generated draft reply."""
        await asyncio.sleep(delay)

        async for db in get_db():
            try:
                result = await db.execute(
                    select(ConversationThread).where(ConversationThread.id == thread_id)
                )
                thread = result.scalar_one_or_none()
                if not thread or thread.status != "pending":
                    return

                content = thread.draft_reply
                if not content:
                    content = await _generate_followup_reply(
                        thread.history or [], thread.from_username, thread.latest_mention_text
                    )

                reply_id = await reply_tweet(thread.latest_mention_id, content)

                history = list(thread.history or [])
                history.append({
                    "role": "us",
                    "text": content,
                    "tweet_id": reply_id,
                    "at": datetime.now(timezone.utc).isoformat(),
                })
                thread.history = history
                thread.status = "auto_replied"
                thread.replied_tweet_id = reply_id
                thread.replied_text = content
                thread.replied_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info("Auto-replied to thread %d, reply_id=%s", thread_id, reply_id)
            except Exception as e:
                logger.error("Auto-reply failed for thread %d: %s", thread_id, e)
                try:
                    result = await db.execute(
                        select(ConversationThread).where(ConversationThread.id == thread_id)
                    )
                    thread = result.scalar_one_or_none()
                    if thread:
                        thread.auto_error = str(e)
                        await db.commit()
                except Exception:
                    pass
            break


conversation_service = ConversationService()
