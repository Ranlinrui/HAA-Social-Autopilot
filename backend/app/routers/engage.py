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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-reply")
async def generate_reply(body: GenerateReplyRequest):
    topic = (
        f"为以下推文生成一条有价值的回复，自然地提及 HAA (Hyper Alpha Arena) AI 交易平台。\n"
        f"原推文作者：@{body.author_username}\n"
        f"原推文内容：{body.tweet_text}\n\n"
        f"要求：回复要有实质内容，不要硬广，字数控制在 200 字以内。"
    )
    try:
        content, _ = await generate_tweet_content(topic=topic, language="en", max_length=200)
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
