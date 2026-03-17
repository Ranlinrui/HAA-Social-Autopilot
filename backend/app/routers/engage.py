import asyncio
import random
import os
import shutil
import uuid

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.engage import EngageReply
from app.services.twitter_api import search_tweets, reply_tweet, retweet_tweet, quote_tweet
from app.services.llm_service import generate_tweet_content

router = APIRouter(prefix="/api/engage", tags=["engage"])


class SearchRequest(BaseModel):
    query: str
    count: int = 20


class SearchResult(BaseModel):
    id: str
    text: str
    author_name: str
    author_username: str
    author_verified: bool
    like_count: Optional[int] = 0
    retweet_count: Optional[int] = 0
    reply_count: Optional[int] = 0
    view_count: Optional[str] = None
    created_at: str
    url: str


class GenerateReplyRequest(BaseModel):
    tweet_text: str
    author_username: str
    mode: str = "reply"  # "reply" or "quote"


class ReplyRequest(BaseModel):
    content: str
    tweet_text: Optional[str] = None
    author_username: Optional[str] = None


@router.post("/search", response_model=List[SearchResult])
async def search_hot_tweets(body: SearchRequest):
    try:
        results = await search_tweets(body.query, body.count)
        return results
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/replied-ids")
async def get_replied_ids(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EngageReply.tweet_id))
    ids = [row[0] for row in result.fetchall()]
    return {"ids": ids}


@router.post("/generate-reply")
async def generate_reply(body: GenerateReplyRequest):
    # Detect language
    has_chinese = any('\u4e00' <= char <= '\u9fff' for char in body.tweet_text)
    language = "zh" if has_chinese else "en"

    if language == "zh":
        prompt = f"""你是一个在 Twitter 上活跃的加密货币玩家，有自己的交易经历和观点，偶尔会提到自己用过的工具。

原推文：
@{body.author_username}：{body.tweet_text}

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
@{body.author_username}: {body.tweet_text}

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

    try:
        content, _ = await generate_tweet_content(
            topic=prompt,
            language=language,
            max_length=250,
            template_prompt="{topic}"
        )
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reply/{tweet_id}")
async def post_reply(tweet_id: str, body: ReplyRequest, db: AsyncSession = Depends(get_db)):
    try:
        reply_id = await reply_tweet(tweet_id, body.content)
        # Record the replied tweet; skip if already recorded (idempotent)
        existing = await db.execute(select(EngageReply).where(EngageReply.tweet_id == tweet_id))
        if not existing.scalar_one_or_none():
            record = EngageReply(
                tweet_id=tweet_id,
                reply_id=reply_id,
                tweet_text=body.tweet_text,
                author_username=body.author_username,
                reply_content=body.content,
            )
            db.add(record)
            await db.commit()
        return {"success": True, "reply_id": reply_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


UPLOAD_DIR = "/app/uploads"


class QuoteRequest(BaseModel):
    tweet_url: str
    content: str


@router.post("/quote")
async def post_quote(body: QuoteRequest):
    try:
        tweet_id = await quote_tweet(body.tweet_url, body.content)
        return {"success": True, "tweet_id": tweet_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quote-with-media")
async def post_quote_with_media(
    tweet_url: str = Form(...),
    content: str = Form(...),
    images: List[UploadFile] = File(default=[]),
):
    saved_paths = []
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        for img in images:
            ext = os.path.splitext(img.filename or "")[1] or ".jpg"
            filename = f"quote_{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(UPLOAD_DIR, filename)
            with open(filepath, "wb") as f:
                shutil.copyfileobj(img.file, f)
            saved_paths.append(filepath)

        tweet_id = await quote_tweet(tweet_url, content, saved_paths)
        return {"success": True, "tweet_id": tweet_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for p in saved_paths:
            try:
                os.remove(p)
            except Exception:
                pass


@router.post("/retweet/{tweet_id}")
async def post_retweet(tweet_id: str):
    try:
        await retweet_tweet(tweet_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class BatchReplyItem(BaseModel):
    tweet_id: str
    content: str
    tweet_text: Optional[str] = None
    author_username: Optional[str] = None


class BatchReplyRequest(BaseModel):
    items: List[BatchReplyItem]
    delay_min: int = 45
    delay_max: int = 90


class BatchReplyResult(BaseModel):
    tweet_id: str
    success: bool
    reply_id: Optional[str] = None
    error: Optional[str] = None
    aborted: bool = False  # True if skipped due to rate-limit circuit breaker


@router.post("/batch-reply", response_model=List[BatchReplyResult])
async def batch_reply(body: BatchReplyRequest, db: AsyncSession = Depends(get_db)):
    results: List[BatchReplyResult] = []
    consecutive_rate_limits = 0  # Track back-to-back 226 errors

    for i, item in enumerate(body.items):
        # If two consecutive 226s, abort the rest of the batch
        if consecutive_rate_limits >= 2:
            results.append(BatchReplyResult(
                tweet_id=item.tweet_id, success=False,
                error="Aborted: rate limit detected, try again later",
                aborted=True
            ))
            continue

        # Random delay between items (skip before the first one)
        if i > 0:
            delay = random.uniform(body.delay_min, body.delay_max)
            await asyncio.sleep(delay)

        # Every 4 items, take a longer break (3-5 min) to mimic human behaviour
        if i > 0 and i % 4 == 0:
            await asyncio.sleep(random.uniform(180, 300))

        try:
            reply_id = await reply_tweet(item.tweet_id, item.content)
            consecutive_rate_limits = 0  # Reset on success
            existing = await db.execute(select(EngageReply).where(EngageReply.tweet_id == item.tweet_id))
            if not existing.scalar_one_or_none():
                record = EngageReply(
                    tweet_id=item.tweet_id,
                    reply_id=reply_id,
                    tweet_text=item.tweet_text,
                    author_username=item.author_username,
                    reply_content=item.content,
                )
                db.add(record)
                await db.commit()
            results.append(BatchReplyResult(tweet_id=item.tweet_id, success=True, reply_id=reply_id))
        except Exception as e:
            error_str = str(e)
            # Detect 226 rate-limit / automation detection
            if "226" in error_str or "automated" in error_str.lower():
                consecutive_rate_limits += 1
                # Back off immediately: wait 15 minutes before continuing
                if consecutive_rate_limits < 2:
                    await asyncio.sleep(900)
            else:
                consecutive_rate_limits = 0
            results.append(BatchReplyResult(tweet_id=item.tweet_id, success=False, error=error_str))

    return results
