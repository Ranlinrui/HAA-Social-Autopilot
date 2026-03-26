from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime, timezone

from app.database import get_db
from app.models.monitor import MonitoredAccount, MonitorNotification
from app.services.monitor_service import monitor_service
from app.services.twitter_risk_control import get_twitter_risk_control
from app.services.twitter_auth_backoff import seconds_until_backoff_expires

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


def _error_detail(exc: Exception, fallback: str) -> str:
    detail = str(exc).strip()
    return detail or fallback


class MonitoredAccountCreate(BaseModel):
    username: str
    priority: int = 2


class MonitoredAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    user_id: Optional[str]
    display_name: Optional[str]
    priority: int
    last_tweet_id: Optional[str]
    last_checked_at: Optional[datetime]
    is_active: bool
    auto_engage: bool
    engage_action: str
    engage_delay: int
    created_at: datetime


class AutoEngageConfig(BaseModel):
    auto_engage: bool
    engage_action: str = "reply"   # "reply", "retweet", "both"
    engage_delay: int = 90         # seconds, 30-300


class MonitorNotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    tweet_id: str
    tweet_text: str
    tweet_url: str
    author_username: str
    author_name: str
    tweet_created_at: datetime
    notified_at: datetime
    is_commented: bool
    comment_text: Optional[str]
    commented_at: Optional[datetime]


class CommentRequest(BaseModel):
    comment_text: str


@router.get("/accounts", response_model=List[MonitoredAccountResponse])
async def list_accounts(
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get list of monitored accounts"""
    try:
        query = select(MonitoredAccount)
        if is_active is not None:
            query = query.where(MonitoredAccount.is_active == is_active)
        query = query.order_by(MonitoredAccount.priority, MonitoredAccount.username)

        result = await db.execute(query)
        accounts = result.scalars().all()
        return accounts
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "加载监控账号失败"))


@router.post("/accounts", response_model=MonitoredAccountResponse)
async def create_account(
    account: MonitoredAccountCreate,
    db: AsyncSession = Depends(get_db)
):
    """Add a new account to monitor"""
    try:
        username = account.username.lstrip('@')

        result = await db.execute(
            select(MonitoredAccount).where(MonitoredAccount.username == username)
        )
        existing = result.scalar_one_or_none()

        if existing:
            raise HTTPException(status_code=400, detail="Account already being monitored")

        new_account = MonitoredAccount(
            username=username,
            priority=account.priority,
            is_active=True
        )

        db.add(new_account)
        await db.commit()
        await db.refresh(new_account)

        return new_account
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "创建监控账号失败"))


@router.delete("/accounts/{account_id}")
async def delete_account(
    account_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Remove an account from monitoring"""
    try:
        result = await db.execute(
            select(MonitoredAccount).where(MonitoredAccount.id == account_id)
        )
        account = result.scalar_one_or_none()

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        await db.delete(account)
        await db.commit()

        return {"success": True, "message": f"Stopped monitoring @{account.username}"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "删除监控账号失败"))


@router.patch("/accounts/{account_id}/toggle")
async def toggle_account(
    account_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Toggle account active status"""
    try:
        result = await db.execute(
            select(MonitoredAccount).where(MonitoredAccount.id == account_id)
        )
        account = result.scalar_one_or_none()

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        account.is_active = not account.is_active
        await db.commit()
        await db.refresh(account)

        return account
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "更新监控账号状态失败"))


@router.patch("/accounts/{account_id}/priority")
async def update_priority(
    account_id: int,
    priority: int = Query(..., ge=1, le=3),
    db: AsyncSession = Depends(get_db)
):
    """Update account monitoring priority"""
    try:
        result = await db.execute(
            select(MonitoredAccount).where(MonitoredAccount.id == account_id)
        )
        account = result.scalar_one_or_none()

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        account.priority = priority
        await db.commit()
        await db.refresh(account)

        return account
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "更新监控优先级失败"))


@router.get("/notifications", response_model=List[MonitorNotificationResponse])
async def list_notifications(
    is_commented: Optional[bool] = None,
    limit: int = Query(50, le=200),
    skip: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Get list of tweet notifications"""
    try:
        query = select(MonitorNotification)

        if is_commented is not None:
            query = query.where(MonitorNotification.is_commented == is_commented)

        query = query.order_by(desc(MonitorNotification.tweet_created_at))
        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        notifications = result.scalars().all()
        return notifications
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "加载监控通知失败"))


@router.post("/notifications/{notification_id}/comment")
async def mark_commented(
    notification_id: int,
    comment: CommentRequest,
    db: AsyncSession = Depends(get_db)
):
    """Mark a notification as commented"""
    try:
        result = await db.execute(
            select(MonitorNotification).where(MonitorNotification.id == notification_id)
        )
        notification = result.scalar_one_or_none()

        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")

        notification.is_commented = True
        notification.comment_text = comment.comment_text
        notification.commented_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(notification)

        return notification
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "更新通知状态失败"))


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get monitoring statistics"""
    from app.services.twitter_api import get_active_auth_state

    try:
        total_accounts = await db.scalar(select(func.count()).select_from(MonitoredAccount))
        active_accounts = await db.scalar(
            select(func.count()).select_from(MonitoredAccount).where(MonitoredAccount.is_active == True)
        )

        total_notifications = await db.scalar(select(func.count()).select_from(MonitorNotification))
        commented_notifications = await db.scalar(
            select(func.count()).select_from(MonitorNotification).where(MonitorNotification.is_commented == True)
        )

        today = datetime.now(timezone.utc).date()
        today_notifications = await db.scalar(
            select(func.count()).select_from(MonitorNotification).where(
                func.date(MonitorNotification.notified_at) == today
            )
        )

        auth_state = await get_active_auth_state("reply")
        risk_state = get_twitter_risk_control().get_state(auth_state.get("active_username"))

        total_accounts = int(total_accounts or 0)
        active_accounts = int(active_accounts or 0)
        total_notifications = int(total_notifications or 0)
        commented_notifications = int(commented_notifications or 0)
        today_notifications = int(today_notifications or 0)

        return {
            "total_accounts": total_accounts,
            "active_accounts": active_accounts,
            "total_notifications": total_notifications,
            "commented_notifications": commented_notifications,
            "uncommented_notifications": max(0, total_notifications - commented_notifications),
            "today_notifications": today_notifications,
            "monitor_running": monitor_service.is_running,
            "backoff_seconds": seconds_until_backoff_expires(monitor_service.auth_backoff_until),
            "backoff_until": monitor_service.auth_backoff_until,
            **risk_state,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "加载监控统计失败"))


@router.patch("/accounts/{account_id}/auto-engage")
async def update_auto_engage(
    account_id: int,
    config: AutoEngageConfig,
    db: AsyncSession = Depends(get_db)
):
    """Update auto-engage configuration for an account"""
    try:
        result = await db.execute(
            select(MonitoredAccount).where(MonitoredAccount.id == account_id)
        )
        account = result.scalar_one_or_none()

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        account.auto_engage = config.auto_engage
        account.engage_action = config.engage_action
        account.engage_delay = max(30, min(300, config.engage_delay))
        await db.commit()
        await db.refresh(account)

        return account
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_error_detail(exc, "更新自动互动配置失败"))


@router.post("/start")
async def start_monitor():
    """Start the monitoring service"""
    await monitor_service.start()
    return {"success": True, "message": "Monitor service started"}


@router.post("/stop")
async def stop_monitor():
    """Stop the monitoring service"""
    await monitor_service.stop()
    return {"success": True, "message": "Monitor service stopped"}
