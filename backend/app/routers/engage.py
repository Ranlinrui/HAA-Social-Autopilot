from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from app.services.twitter_api import search_tweets, reply_tweet
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


class ReplyRequest(BaseModel):
    content: str


@router.post("/search", response_model=List[SearchResult])
async def search_hot_tweets(body: SearchRequest):
    try:
        results = await search_tweets(body.query, body.count)
        return results
    except ValueError as e:
        # Twitter 未登录或配置错误
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.post("/generate-reply")
async def generate_reply(body: GenerateReplyRequest):
    # Detect language
    has_chinese = any('\u4e00' <= char <= '\u9fff' for char in body.tweet_text)
    language = "zh" if has_chinese else "en"

    # HAA platform features
    haa_features = """
Hyper Alpha Arena (HAA) Key Features:
- AI-powered quantitative trading strategies
- Real-time market analysis and prediction
- Automated risk management systems
- Multi-strategy portfolio optimization
- Backtesting and performance analytics
- Community-driven alpha discovery
- Low-latency execution infrastructure
"""

    if language == "zh":
        prompt = f"""你是一个专业的加密货币和 AI 交易领域的社交媒体专家。

【任务】为以下推文生成一条有价值的评论回复。

【原推文】
作者：@{body.author_username}
内容：{body.tweet_text}

【HAA 平台功能】
{haa_features}

【要求】
1. 用中文回复
2. 先对原推文内容给出有见地的评论或补充
3. 自然地提及 HAA (Hyper Alpha Arena) 平台的相关功能（选择与推文内容最相关的 1-2 个功能点）
4. 语气专业但不生硬，像行业内人士的交流
5. 不要硬广，要让提及显得自然
6. **严格控制在 230 字符以内，必须完整结束句子，不能被截断**
7. 可以适当使用 emoji 增加亲和力

【输出】
直接输出评论内容，不要任何额外说明。"""
    else:
        prompt = f"""You are a professional crypto and AI trading expert on social media.

【Task】Generate a valuable reply to the following tweet.

【Original Tweet】
Author: @{body.author_username}
Content: {body.tweet_text}

【HAA Platform Features】
{haa_features}

【Requirements】
1. Reply in English
2. First provide insightful commentary or addition to the original tweet
3. Naturally mention HAA (Hyper Alpha Arena) platform's relevant features (choose 1-2 features most related to the tweet content)
4. Professional but conversational tone, like industry peer discussion
5. No hard selling, make the mention feel natural
6. **Strictly limit to 230 characters, must end with complete sentence, cannot be cut off**
7. Can use emojis appropriately for engagement

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
async def post_reply(tweet_id: str, body: ReplyRequest):
    try:
        reply_id = await reply_tweet(tweet_id, body.content)
        return {"success": True, "reply_id": reply_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
