"""WebSocket event manager - manages task event subscriptions and broadcasting."""
import asyncio
import logging
import time
from typing import Set

from fastapi import WebSocket

from app.models.task import Task

logger = logging.getLogger(__name__)


class TaskEventManager:
    """
    任务事件管理器

    使用内存事件分发机制管理 WebSocket 连接。
    当任务状态更新时，向所有订阅该任务的客户端推送消息。

    H5: broadcast 使用 asyncio.gather 并发发送，避免慢客户端拖累其他客户端。
    M9: 每个 WebSocket 维护独立 asyncio.Lock，防止并发 send 报错。

    按 task_id 订阅的连接在接入时（routers/ws.py）已完成归属校验，
    此处不再重复判定，因此广播不需要携带用户归属信息。
    """

    # 单次 send 的超时上限（秒）。客户端 TCP 半死（如笔记本休眠）时其发送缓冲区
    # 填满后 ASGI send 会无限期挂起，而 broadcast 的 gather 要等所有 send 完成，
    # 一个卡死的连接会冻结所有后台任务的进度上报，因此必须有硬超时。
    SEND_TIMEOUT = 5.0

    def __init__(self):
        self._subscribers: dict[str, Set[WebSocket]] = {}
        self._locks: dict[WebSocket, asyncio.Lock] = {}

    def _get_lock(self, ws: WebSocket) -> asyncio.Lock:
        lock = self._locks.get(ws)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[ws] = lock
        return lock

    def _remove_lock(self, ws: WebSocket):
        self._locks.pop(ws, None)

    def _is_subscribed_anywhere(self, ws: WebSocket) -> bool:
        for subs in self._subscribers.values():
            if ws in subs:
                return True
        return False

    async def subscribe(self, task_id: str, websocket: WebSocket):
        if task_id not in self._subscribers:
            self._subscribers[task_id] = set()
        self._subscribers[task_id].add(websocket)
        self._get_lock(websocket)

    async def unsubscribe(self, task_id: str, websocket: WebSocket):
        if task_id in self._subscribers:
            self._subscribers[task_id].discard(websocket)
            if not self._subscribers[task_id]:
                del self._subscribers[task_id]
        if not self._is_subscribed_anywhere(websocket):
            self._remove_lock(websocket)

    async def _send_safe(self, ws: WebSocket, message: dict) -> bool:
        """带 per-socket 锁的安全发送。成功返回 True，失败/超时返回 False。"""
        lock = self._get_lock(ws)
        try:
            async with lock:
                await asyncio.wait_for(ws.send_json(message), timeout=self.SEND_TIMEOUT)
            return True
        except asyncio.TimeoutError:
            logger.warning("WebSocket send 超时，移除该订阅者")
            return False
        except Exception:
            return False

    async def broadcast(self, task_id: str, message: dict):
        """向所有订阅了 task_id 的客户端并发广播消息。

        H5: 使用 asyncio.gather 并发发送，慢客户端不会阻塞其他客户端。
        """
        targets: Set[WebSocket] = set()
        if task_id in self._subscribers:
            targets.update(self._subscribers[task_id])

        if not targets:
            return

        results = await asyncio.gather(
            *[self._send_safe(ws, message) for ws in targets],
            return_exceptions=True,
        )

        failed: list[WebSocket] = []
        for ws, result in zip(targets, results):
            if isinstance(result, Exception) or result is False:
                failed.append(ws)

        for ws in failed:
            if task_id in self._subscribers:
                self._subscribers[task_id].discard(ws)
                if not self._subscribers[task_id]:
                    self._subscribers.pop(task_id, None)
            self._remove_lock(ws)


# 全局事件管理器
task_event_manager = TaskEventManager()


def _task_to_ws_message(task: Task) -> dict:
    return {
        "type": "task_update",
        "task_id": str(task.id),
        "project_id": str(task.project_id) if task.project_id else None,
        "task_type": task.task_type,
        "status": task.status,
        "priority": task.priority,
        "progress": task.progress,
        "logs": task.logs or [],
        "error_message": task.error_message,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }
