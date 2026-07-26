import asyncio
import json
import logging
from typing import Optional, Set
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.repositories.task_repo import TaskRepository
from app.models.task import Task
from app.models.novel import Project
from app.core.security import decode_token

from app.infra.websocket import task_event_manager, TaskEventManager, _task_to_ws_message

logger = logging.getLogger(__name__)

router = APIRouter()


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

    await task_event_manager.subscribe(task_id, websocket)

    try:
        # 先推送当前任务状态（短 session，不持有 DB 连接）
        try:
            await websocket.send_json(initial_message)
        except Exception as e:
            logger.warning(f"WebSocket 初始状态推送失败: {e}")

        # 保持连接，持续接收消息（用于心跳）
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # 处理客户端 ping
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
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


@router.websocket("/tasks")
async def task_list_websocket(
    websocket: WebSocket,
    token: str = Query(...),
):
    """
    WebSocket 端点：订阅全部任务列表变更，需要 token 认证

    连接后，每3秒推送一次队列看板数据:
    {"type": "queue_update", "data": {...}}
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
    logger.info("WebSocket 连接: /ws/tasks (全局)")

    await task_event_manager.subscribe_global(websocket, user_id=user_id)

    try:
        while True:
            try:
                # 每10秒推送队列数据（短 session，不持有 DB 连接）
                # 实时更新由 task_event_manager 的事件广播处理，轮询仅作为补偿
                async with async_session_factory() as db:
                    # 仅当前用户项目的任务
                    user_project_ids = select(Project.id).where(
                        Project.user_id == user_id
                    ).scalar_subquery()
                    query = (
                        select(Task)
                        .where(
                            Task.status.in_(
                                ["queued", "running", "completed", "failed", "cancelled"]
                            ),
                            Task.project_id.in_(user_project_ids),
                        )
                        .order_by(Task.status, Task.created_at.desc())
                        .limit(250)
                    )
                    result = await db.execute(query)
                    all_tasks = list(result.scalars().all())

                # 按 status 分组
                kanban_data = {}
                for status in ["queued", "running", "completed", "failed", "cancelled"]:
                    status_tasks = [t for t in all_tasks if t.status == status][:50]
                    kanban_data[status] = {
                        "items": [_task_to_ws_message(t) for t in status_tasks],
                        "total": len(status_tasks),
                    }

                try:
                    await websocket.send_json({
                        "type": "queue_update",
                        "data": kanban_data,
                    })
                except Exception:
                    break

                # 等待10秒，同时监听消息（心跳）
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=10)
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except asyncio.TimeoutError:
                    # 正常超时，继续下一轮推送
                    continue
                except (json.JSONDecodeError, ValueError):
                    continue

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"任务列表 WebSocket 异常: {e}")
                break

    finally:
        await task_event_manager.unsubscribe_global(websocket)
        logger.info("WebSocket 断开: /ws/tasks (全局)")
