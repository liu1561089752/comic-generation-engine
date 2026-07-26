from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.schemas.common import ApiResponse
from app.models.system import Notification

router = APIRouter()


@router.get("")
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取通知列表"""
    conditions = [Notification.user_id == user_id]
    if unread_only:
        conditions.append(Notification.is_read == False)

    # 总数量
    count_q = select(func.count(Notification.id)).where(*conditions)
    total = await db.scalar(count_q)

    # 分页查询
    q = (
        select(Notification)
        .where(*conditions)
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = await db.execute(q)
    notifications = rows.scalars().all()

    return ApiResponse(data={
        "items": [
            {
                "id": str(n.id),
                "type": n.type,
                "title": n.title,
                "description": n.description,
                "related_url": n.related_url,
                "is_read": n.is_read,
                "priority": n.priority,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notifications
        ],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "unread_count": await db.scalar(
                select(func.count(Notification.id)).where(
                    Notification.user_id == user_id,
                    Notification.is_read == False,
                )
            ),
        },
    })


@router.get("/unread-count")
async def unread_count(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取未读通知数量"""
    count = await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.is_read == False,
        )
    )
    return ApiResponse(data={"unread_count": count or 0})


@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记单条通知为已读"""
    q = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == user_id,
    )
    row = await db.execute(q)
    notification = row.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")

    notification.is_read = True
    return ApiResponse(data={"id": notification_id, "is_read": True})


@router.post("/read-all")
async def mark_all_as_read(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记所有通知为已读"""
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)
        .values(is_read=True)
    )
    return ApiResponse(data={"message": "全部已读"})


@router.post("/settings")
async def update_notification_settings(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """通知设置（占位，后续可扩展为存储在用户配置中）"""
    return ApiResponse(data={"message": "设置已保存"})
