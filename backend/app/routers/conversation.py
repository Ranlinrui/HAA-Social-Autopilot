from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models.conversation import ConversationThread, ConversationSetting
from app.services.twitter_api import reply_tweet
from app.services.conversation_service import conversation_service
from app.services.twitter_risk_control import get_twitter_risk_control
from app.services.twitter_auth_backoff import seconds_until_backoff_expires

router = APIRouter(prefix="/api/conversation", tags=["conversation"])


def _error_detail(exc: Exception) -> str:
    return str(exc).strip() or exc.__class__.__name__


class ThreadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    root_tweet_id: str
    root_tweet_text: Optional[str]
    our_reply_id: str
    our_reply_text: Optional[str]
    latest_mention_id: str
    latest_mention_text: str
    from_username: str
    from_user_id: Optional[str]
    mention_created_at: Optional[datetime]
    history: Optional[list]
    status: str
    mode: str
    draft_reply: Optional[str]
    replied_tweet_id: Optional[str]
    replied_text: Optional[str]
    replied_at: Optional[datetime]
    auto_error: Optional[str]
    created_at: Optional[datetime]


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mode: str
    poll_interval: int
    auto_reply_delay: int
    enabled: bool


class ManualReplyRequest(BaseModel):
    content: str


class GenerateDraftRequest(BaseModel):
    thread_id: int


class UpdateSettingsRequest(BaseModel):
    mode: Optional[str] = None
    poll_interval: Optional[int] = None
    auto_reply_delay: Optional[int] = None
    enabled: Optional[bool] = None


class UpdateThreadModeRequest(BaseModel):
    mode: str  # "auto" or "manual"


async def _get_or_create_settings(db: AsyncSession) -> ConversationSetting:
    result = await db.execute(select(ConversationSetting).where(ConversationSetting.id == 1))
    cfg = result.scalar_one_or_none()
    if not cfg:
        cfg = ConversationSetting(id=1)
        db.add(cfg)
        await db.commit()
        await db.refresh(cfg)
    return cfg


@router.get("/threads", response_model=List[ThreadOut])
async def list_threads(
    status: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    try:
        query = select(ConversationThread).order_by(desc(ConversationThread.created_at)).limit(limit)
        if status:
            query = select(ConversationThread).where(
                ConversationThread.status == status
            ).order_by(desc(ConversationThread.created_at)).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=_error_detail(e))


@router.get("/threads/{thread_id}", response_model=ThreadOut)
async def get_thread(thread_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ConversationThread).where(ConversationThread.id == thread_id)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@router.post("/threads/{thread_id}/generate-draft")
async def generate_draft(thread_id: int, db: AsyncSession = Depends(get_db)):
    """Generate (or regenerate) an AI reply draft for a thread."""
    from app.services.conversation_service import _generate_followup_reply

    result = await db.execute(
        select(ConversationThread).where(ConversationThread.id == thread_id)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    try:
        draft = await _generate_followup_reply(
            thread.history or [], thread.from_username, thread.latest_mention_text
        )
        thread.draft_reply = draft
        await db.commit()
        return {"draft": draft}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_error_detail(e))


@router.post("/threads/{thread_id}/reply")
async def manual_reply(
    thread_id: int,
    body: ManualReplyRequest,
    db: AsyncSession = Depends(get_db)
):
    """Send a manual reply to a conversation thread."""
    result = await db.execute(
        select(ConversationThread).where(ConversationThread.id == thread_id)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    if thread.status in ("manual_replied", "auto_replied"):
        raise HTTPException(status_code=400, detail="Thread already replied")

    try:
        reply_id = await reply_tweet(thread.latest_mention_id, body.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=_error_detail(e))

    history = list(thread.history or [])
    history.append({
        "role": "us",
        "text": body.content,
        "tweet_id": reply_id,
        "at": datetime.now(timezone.utc).isoformat(),
    })
    thread.history = history
    thread.status = "manual_replied"
    thread.replied_tweet_id = reply_id
    thread.replied_text = body.content
    thread.replied_at = datetime.now(timezone.utc)
    await db.commit()
    return {"success": True, "reply_id": reply_id}


@router.post("/threads/{thread_id}/ignore")
async def ignore_thread(thread_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ConversationThread).where(ConversationThread.id == thread_id)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread.status = "ignored"
    await db.commit()
    return {"success": True}


@router.patch("/threads/{thread_id}/mode")
async def update_thread_mode(
    thread_id: int,
    body: UpdateThreadModeRequest,
    db: AsyncSession = Depends(get_db)
):
    """Switch a single thread between auto and manual mode."""
    if body.mode not in ("auto", "manual"):
        raise HTTPException(status_code=400, detail="mode must be 'auto' or 'manual'")
    result = await db.execute(
        select(ConversationThread).where(ConversationThread.id == thread_id)
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread.mode = body.mode
    await db.commit()
    return {"success": True}


@router.get("/settings", response_model=SettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    try:
        return await _get_or_create_settings(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=_error_detail(e))


@router.patch("/settings")
async def update_settings(body: UpdateSettingsRequest, db: AsyncSession = Depends(get_db)):
    try:
        cfg = await _get_or_create_settings(db)
        if body.mode is not None:
            if body.mode not in ("auto", "manual"):
                raise HTTPException(status_code=400, detail="mode must be 'auto' or 'manual'")
            cfg.mode = body.mode
        if body.poll_interval is not None:
            cfg.poll_interval = max(60, body.poll_interval)
        if body.auto_reply_delay is not None:
            cfg.auto_reply_delay = max(30, body.auto_reply_delay)
        if body.enabled is not None:
            cfg.enabled = body.enabled
        await db.commit()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=_error_detail(e))


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func
    from app.services.twitter_api import get_active_auth_state

    try:
        total_result = await db.execute(select(func.count(ConversationThread.id)))
        total = total_result.scalar() or 0

        pending_result = await db.execute(
            select(func.count(ConversationThread.id)).where(ConversationThread.status == "pending")
        )
        pending = pending_result.scalar() or 0

        cfg = await _get_or_create_settings(db)
        auth_state = await get_active_auth_state("reply")
        return {
            "total_threads": int(total or 0),
            "pending_threads": int(pending or 0),
            "mode": cfg.mode,
            "enabled": cfg.enabled,
            "backoff_seconds": seconds_until_backoff_expires(conversation_service.auth_backoff_until),
            "backoff_until": conversation_service.auth_backoff_until,
            **get_twitter_risk_control().get_state(auth_state.get("active_username")),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=_error_detail(e))
