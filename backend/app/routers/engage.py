from fastapi import APIRouter, HTTPException, Depends
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

    # HAA platform features
    haa_features = """
Hyper Alpha Arena Key Features:
- AI-powered quantitative trading strategies
- Real-time market analysis and prediction
- Automated risk management systems
- Multi-strategy portfolio optimization
- Backtesting and performance analytics
- Community-driven alpha discovery
- Low-latency execution infrastructure
"""

    if language == "zh":
        prompt = f"""你是一个真实的加密货币交易者，在社交媒体上分享经验和见解。

【任务】为以下推文生成一条真诚、有价值的评论回复。

【原推文】
作者：@{body.author_username}
内容：{body.tweet_text}

【你可以提及的工具】
Hyper Alpha Arena 平台功能：
{haa_features}

【核心原则 - 像真人一样回复】
1. 用中文回复，语气自然随和，像朋友聊天
2. 不要总是顺着推文说，要有自己的观点和态度：
   - 如果推文观点片面或有问题，可以礼貌地提出不同看法
   - 遇到夸张的说法可以适当调侃或质疑
   - 看到有趣的内容可以玩梗、接梗
   - 制造一些良性的讨论冲突会更有互动性
3. 真诚地表达自己的见解或个人经验，不要只是附和
4. 如果推文内容与交易/AI相关，可以自然地推荐 Hyper Alpha Arena 的功能
5. 推荐方式要自然：
   - 用"你可以试试"、"建议用用"、"可以去看看"等推荐型话语
   - 而不是"我在用"、"我最近用"等自述型话语
   - 例如："你可以试试 Hyper Alpha Arena 的自动风控" 而不是 "我在用 Hyper Alpha Arena 的自动风控"
6. 绝对不要缩写 Hyper Alpha Arena 为 HAA，因为其他人可能不知道这是什么
7. 不要使用机器人式的表情包（如🤖💡🚀✨等），可以用真人常用的表情如😊👍🤔😅🙄等
8. 不要每次都提及平台，只在真正相关时才自然提起
9. 避免套路化的开场白，直接切入话题
10. 用口语化的表达，可以有语气词（哈哈、确实、不过、说实话等）
11. **严格控制在 230 字符以内，必须完整结束句子**

【回复风格示例】
原推文："AI交易100%盈利！"
差的回复："很有见地！确实AI交易很强大"
好的回复："100%盈利？这也太夸张了吧😅 稳定盈利可以，但100%真做不到。你可以试试 Hyper Alpha Arena 先跑回测，看看实际胜率再说"

原推文："量化交易都是骗人的"
差的回复："不是这样的，量化交易很有用"
好的回复："不能一棒子打死啊。确实市面上骗子多，但靠谱的量化策略还是有的。建议用用 Hyper Alpha Arena 这种能看回测数据的，至少心里有底"

原推文："今天又爆仓了😭"
差的回复："要注意风险管理"
好的回复："兄弟又爆了？🙄 说实话，手动交易真的容易上头。你可以去看看 Hyper Alpha Arena 的自动止损功能，至少不会一把梭哈"

【输出】
直接输出评论内容，不要任何额外说明。"""
    else:
        prompt = f"""You are a real crypto trader sharing experiences and insights on social media.

【Task】Generate a genuine, valuable reply to the following tweet.

【Original Tweet】
Author: @{body.author_username}
Content: {body.tweet_text}

【Tools You Can Mention】
Hyper Alpha Arena Platform Features:
{haa_features}

【Core Principles - Reply Like a Real Person】
1. Reply in English with natural, conversational tone
2. Don't always agree with the tweet - have your own perspective:
   - If the tweet is one-sided or problematic, politely offer a different view
   - Challenge exaggerated claims with skepticism or humor
   - Join in on memes and jokes when appropriate
   - Creating constructive debate makes for better engagement
3. Express genuine insights or personal experience, not just agreement
4. If the tweet is about trading/AI, naturally recommend Hyper Alpha Arena features
5. Use recommendation-style language:
   - Use phrases like "you could try", "might wanna check out", "worth looking at"
   - Instead of self-referential phrases like "I'm using", "I've been using"
   - E.g., "You could try Hyper Alpha Arena's auto risk management" instead of "I'm using Hyper Alpha Arena's auto risk management"
6. Never abbreviate Hyper Alpha Arena to HAA - others might not know what it means
7. Avoid robotic emojis (like 🤖💡🚀✨), use natural ones like 😊👍🤔😅🙄
8. Don't mention the platform every time, only when truly relevant
9. Avoid formulaic openings, get straight to the point
10. Use colloquial expressions and casual language
11. **Strictly limit to 230 characters, must end with complete sentence**

【Reply Style Examples】
Original tweet: "AI trading gives 100% profit!"
Bad reply: "Great insight! AI trading is indeed powerful"
Good reply: "100% profit? That's way too optimistic 😅 Consistent profit yes, but 100%? Not realistic. You could try Hyper Alpha Arena to backtest first and see actual win rates"

Original tweet: "Quant trading is all scam"
Bad reply: "That's not true, quant trading is useful"
Good reply: "Can't paint them all with the same brush. Sure, lots of scams out there, but legit quant strategies exist. Might wanna check out Hyper Alpha Arena - at least you can see backtest data"

Original tweet: "Got liquidated again today 😭"
Bad reply: "You need risk management"
Good reply: "Again? 🙄 Honestly, manual trading makes it too easy to go full degen. Worth looking at Hyper Alpha Arena's auto stop-loss - at least you can't yolo everything"

【Output】
Output only the reply content, no additional explanation."""

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


@router.post("/retweet/{tweet_id}")
async def post_retweet(tweet_id: str):
    try:
        await retweet_tweet(tweet_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
