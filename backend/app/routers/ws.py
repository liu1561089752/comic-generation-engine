import asyncio
import json
import logging
import time
from typing import Optional, Set
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.repositories.task_repo import TaskRepository
from app.models.novel import Project
from app.core.security import decode_token

from app.infra.websocket import task_event_manager, TaskEventManager, _task_to_ws_message

logger = logging.getLogger(__name__)

router = APIRouter()

# WebSocket 连接最大存活时间（秒），超过此时间强制断开
_WS_MAX_LIFETIME = 3600.0


async def _enforce_max_lifetime(websocket: WebSocket, started_at: float, max_lifetime: float = _WS_MAX_LIFETIME) -> bool:
    """检查连接是否超过最大存活时间，超过则关闭并返回 False。"""
    if time.monotonic() - started_at > max_lifetime:
        try:
            await websocket.close(code=4000, reason="连接超过最大存活时间")
        except Exception:
            pass
        return True
    return False


async def _task_belongs_to_user(task, user_id: str, db: AsyncSession) -> bool:
    """校验任务所属的项目是否属于当前用户（口径与 tasks.py 的归属校验一致）"""
    if not task.project_id:
        return True
    result = await db.execute(
        select(Project.id).where(Project.id == task.project_id, Project.user_id == user_id)
    )
    return result.scalar_one_or_none() is not None


@router.websocket("/tasks/{task_id}")
async def task_status_websocket(
    websocket: WebSocket,
    task_id: str,
    token: str = Query(...),
):
    """
    WebSocket 端点：订阅任务状态变更，需要 token 认证

    连接后，当任务状态更新时会推送:
    {"task_id": "...", "status": "running", "progress": 50}
    """
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        await websocket.close(code=4001)
        return
    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=4001)
        return
    await websocket.accept()

    # 归属校验必须在订阅之前完成：无法确认归属（任务不存在或不属于本人）一律拒绝，
    # 否则订阅通道会持续收到他人任务的日志与错误详情
    initial_message = None
    try:
        task_uuid = UUID(task_id)
        async with async_session_factory() as db:
            repo = TaskRepository(db)
            task = await repo.get(task_uuid)
            if task is None or not await _task_belongs_to_user(task, user_id, db):
                await websocket.close(code=4003)
                return
            initial_message = _task_to_ws_message(task)
    except (ValueError, TypeError):
        await websocket.close(code=4003)
        return
    except Exception as e:
        logger.warning(f"WebSocket 任务归属校验失败: {e}")
        await websocket.close(code=4003)
        return

    logger.info(f"WebSocket 连接: task_id={task_id}")
    _started_at = time.monotonic()

    await task_event_manager.subscribe(task_id, websocket)

    try:
        # 先推送当前任务状态（短 session，不持有 DB 连接）
        try:
            await websocket.send_json(initial_message)
        except Exception as e:
            logger.warning(f"WebSocket 初始状态推送失败: {e}")

        # 保持连接，持续接收消息（用于心跳）
        while True:
            if await _enforce_max_lifetime(websocket, _started_at):
                break
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # 处理客户端 ping
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                _started_at = time.monotonic()  # 有消息时重置空闲时间
            except asyncio.TimeoutError:
                # 发送心跳保活
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break
            except (json.JSONDecodeError, ValueError):
                continue

    except WebSocketDisconnect:
        logger.info(f"WebSocket 断开: task_id={task_id}")
    except Exception as e:
        logger.error(f"WebSocket 异常: {e}")
    finally:
        await task_event_manager.unsubscribe(task_id, websocket)
