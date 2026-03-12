from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models.monitor import MonitoredAccount, MonitorNotification
from app.services.monitor_service import monitor_service

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


class MonitoredAccountCreate(BaseModel):
    username: str
    priority: int = 2


class MonitoredAccountResponse(BaseModel):
    id: int
    username: str
    user_id: Optional[str]
    display_name: Optional[str]
    priority: int
    last_tweet_id: Optional[str]
    last_checked_at: Optional[datetime]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MonitorNotificationResponse(BaseModel):
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

    class Config:
        from_attributes = True


class CommentRequest(BaseModel):
    comment_text: str


@router.get("/accounts", response_model=List[MonitoredAccountResponse])
async def list_accounts(
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get list of monitored accounts"""
    query = select(MonitoredAccount)
    if is_active is not None:
        query = query.where(MonitoredAccount.is_active == is_active)
    query = query.order_by(MonitoredAccount.priority, MonitoredAccount.username)

    result = await db.execute(query)
    accounts = result.scalars().all()
    return accounts


@router.post("/accounts", response_model=MonitoredAccountResponse)
async def create_account(
    account: MonitoredAccountCreate,
    db: AsyncSession = Depends(get_db)
):
    """Add a new account to monitor"""
    # Remove @ if present
    username = account.username.lstrip('@')

    # Check if already exists
    result = await db.execute(
        select(MonitoredAccount).where(MonitoredAccount.username == username)
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="Account already being monitored")

    # Create new account
    new_account = MonitoredAccount(
        username=username,
        priority=account.priority,
        is_active=True
    )

    db.add(new_account)
    await db.commit()
    await db.refresh(new_account)

    return new_account


@router.delete("/accounts/{account_id}")
async def delete_account(
    account_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Remove an account from monitoring"""
    result = await db.execute(
        select(MonitoredAccount).where(MonitoredAccount.id == account_id)
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    await db.delete(account)
    await db.commit()

    return {"success": True, "message": f"Stopped monitoring @{account.username}"}


@router.patch("/accounts/{account_id}/toggle")
async def toggle_account(
    account_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Toggle account active status"""
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


@router.patch("/accounts/{account_id}/priority")
async def update_priority(
    account_id: int,
    priority: int = Query(..., ge=1, le=3),
    db: AsyncSession = Depends(get_db)
):
    """Update account monitoring priority"""
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


@router.get("/notifications", response_model=List[MonitorNotificationResponse])
async def list_notifications(
    is_commented: Optional[bool] = None,
    limit: int = Query(50, le=200),
    skip: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Get list of tweet notifications"""
    query = select(MonitorNotification)

    if is_commented is not None:
        query = query.where(MonitorNotification.is_commented == is_commented)

    query = query.order_by(desc(MonitorNotification.tweet_created_at))
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    notifications = result.scalars().all()
    return notifications


@router.post("/notifications/{notification_id}/comment")
async def mark_commented(
    notification_id: int,
    comment: CommentRequest,
    db: AsyncSession = Depends(get_db)
):
    """Mark a notification as commented"""
    result = await db.execute(
        select(MonitorNotification).where(MonitorNotification.id == notification_id)
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_commented = True
    notification.comment_text = comment.comment_text
    notification.commented_at = datetime.utcnow()

    await db.commit()
    await db.refresh(notification)

    return notification


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get monitoring statistics"""
    # Count accounts
    total_accounts = await db.scalar(select(func.count()).select_from(MonitoredAccount))
    active_accounts = await db.scalar(
        select(func.count()).select_from(MonitoredAccount).where(MonitoredAccount.is_active == True)
    )

    # Count notifications
    total_notifications = await db.scalar(select(func.count()).select_from(MonitorNotification))
    commented_notifications = await db.scalar(
        select(func.count()).select_from(MonitorNotification).where(MonitorNotification.is_commented == True)
    )

    # Count today's notifications
    today = datetime.utcnow().date()
    today_notifications = await db.scalar(
        select(func.count()).select_from(MonitorNotification).where(
            func.date(MonitorNotification.notified_at) == today
        )
    )

    return {
        "total_accounts": total_accounts,
        "active_accounts": active_accounts,
        "total_notifications": total_notifications,
        "commented_notifications": commented_notifications,
        "uncommented_notifications": total_notifications - commented_notifications,
        "today_notifications": today_notifications,
        "monitor_running": monitor_service.is_running
    }


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
