"""WebSocket event manager - manages task event subscriptions and broadcasting."""
import asyncio
import logging
import time
import uuid
from typing import Optional, Set

from fastapi import WebSocket
from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.novel import Project
from app.models.task import Task

logger = logging.getLogger(__name__)


class TaskEventManager:
    """
    任务事件管理器

    使用内存事件分发机制管理 WebSocket 连接。
    当任务状态更新时，向所有订阅该任务的客户端推送消息。

    H5: broadcast 使用 asyncio.gather 并发发送，避免慢客户端拖累其他客户端。
    M9: 每个 WebSocket 维护独立 asyncio.Lock，防止并发 send 报错。

    全局订阅者（/ws/tasks）必须携带 user_id：任务事件消息里含有他人任务的
    logs / error_message / project_id，无归属过滤地群发等于把别人的任务详情
    推给任意已登录用户。归属判定所需的 project_id -> owner_user_id 映射走
    内存缓存，缓存未命中时在后台协程里解析，绝不在 broadcast 的发送路径上查库。
    """

    # 单次 send 的超时上限（秒）。客户端 TCP 半死（如笔记本休眠）时其发送缓冲区
    # 填满后 ASGI send 会无限期挂起，而 broadcast 的 gather 要等所有 send 完成，
    # 一个卡死的连接会冻结所有后台任务的进度上报，因此必须有硬超时。
    SEND_TIMEOUT = 5.0

    # project_id -> owner_user_id 缓存的有效期（秒）与容量上限
    PROJECT_OWNER_TTL = 300.0
    PROJECT_OWNER_CACHE_MAX = 512

    def __init__(self):
        self._subscribers: dict[str, Set[WebSocket]] = {}
        # 全局订阅者 -> 该连接认证后的 user_id（None 表示调用方未提供，按无权处理）
        self._global_subscribers: dict[WebSocket, Optional[str]] = {}
        self._locks: dict[WebSocket, asyncio.Lock] = {}
        # project_id -> (owner_user_id, 写入时刻)；owner_user_id 为 None 表示项目不存在
        self._project_owners: dict[str, tuple[Optional[str], float]] = {}
        self._owner_resolving: Set[str] = set()
        self._owner_resolve_tasks: Set[asyncio.Task] = set()

    def _get_lock(self, ws: WebSocket) -> asyncio.Lock:
        lock = self._locks.get(ws)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[ws] = lock
        return lock

    def _remove_lock(self, ws: WebSocket):
        self._locks.pop(ws, None)

    def _is_subscribed_anywhere(self, ws: WebSocket) -> bool:
        if ws in self._global_subscribers:
            return True
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

    async def subscribe_global(self, websocket: WebSocket, user_id: Optional[str] = None):
        """注册全局订阅者。

        user_id 为该连接认证后的用户 ID，用于事件广播时的归属过滤。
        为兼容旧调用方保留默认值 None，但默认值取安全的一侧——
        缺少 user_id 的连接不会收到任何任务事件推送（由轮询兜底），
        而不是收到全部任务。
        """
        self._global_subscribers[websocket] = str(user_id) if user_id else None
        self._get_lock(websocket)
        if not user_id:
            logger.warning(
                "全局 WebSocket 订阅未提供 user_id，该连接不会收到任务事件推送"
            )

    async def unsubscribe_global(self, websocket: WebSocket):
        self._global_subscribers.pop(websocket, None)
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

    def _cached_project_owner(self, project_id: str) -> tuple[bool, Optional[str]]:
        """读取项目归属缓存，返回 (是否命中, owner_user_id)。过期视为未命中。"""
        entry = self._project_owners.get(project_id)
        if entry is None:
            return False, None
        owner_id, cached_at = entry
        if time.monotonic() - cached_at > self.PROJECT_OWNER_TTL:
            self._project_owners.pop(project_id, None)
            return False, None
        return True, owner_id

    def _schedule_owner_resolve(self, project_id: str):
        """缓存未命中时在后台协程里解析项目归属，不阻塞也不污染 broadcast 的发送路径。"""
        if project_id in self._owner_resolving:
            return
        self._owner_resolving.add(project_id)
        try:
            resolve_task = asyncio.create_task(self._resolve_project_owner(project_id))
        except RuntimeError:
            # 无运行中的事件循环，放弃本次解析，下次事件再试
            self._owner_resolving.discard(project_id)
            return
        # 保留强引用，避免任务被 GC 提前回收
        self._owner_resolve_tasks.add(resolve_task)
        resolve_task.add_done_callback(self._owner_resolve_tasks.discard)

    def _trim_owner_cache(self):
        """归属缓存达到上限时先清过期项，仍超限则整体清空，防止无界增长。"""
        if len(self._project_owners) < self.PROJECT_OWNER_CACHE_MAX:
            return
        now = time.monotonic()
        self._project_owners = {
            pid: entry
            for pid, entry in self._project_owners.items()
            if now - entry[1] <= self.PROJECT_OWNER_TTL
        }
        if len(self._project_owners) >= self.PROJECT_OWNER_CACHE_MAX:
            self._project_owners.clear()

    async def _resolve_project_owner(self, project_id: str):
        """用独立短 session 查询项目 owner 并写入缓存。查询失败时不写缓存，留待重试。"""
        try:
            project_uuid = uuid.UUID(project_id)
        except (ValueError, TypeError, AttributeError):
            # project_id 非法，缓存为"无归属"，避免每次事件都重复调度解析
            self._trim_owner_cache()
            self._project_owners[project_id] = (None, time.monotonic())
            self._owner_resolving.discard(project_id)
            return

        try:
            async with async_session_factory() as sess:
                result = await sess.execute(
                    select(Project.user_id).where(Project.id == project_uuid)
                )
                owner_id = result.scalar_one_or_none()
            self._trim_owner_cache()
            self._project_owners[project_id] = (
                str(owner_id) if owner_id else None,
                time.monotonic(),
            )
        except Exception as e:
            logger.warning(f"解析项目 {project_id} 归属失败，事件暂不推送给全局订阅者: {e}")
        finally:
            self._owner_resolving.discard(project_id)

    def _global_targets(self, message: dict) -> Set[WebSocket]:
        """筛选出有权接收该任务事件的全局订阅者。

        安全默认：只要归属无法判定，就一律不推送（宁可少推，不可错推）——
        包括订阅者未携带 user_id、消息体缺少 project_id、以及归属缓存尚未
        解析完成这三种情况。实时性缺口由 /ws/tasks 的轮询补偿（轮询侧已按
        项目归属过滤）。
        """
        if not self._global_subscribers:
            return set()

        project_id = message.get("project_id")
        if not project_id:
            # 无项目归属的系统级任务不落到任何用户名下，与轮询看板的口径一致，不推送
            return set()

        project_id = str(project_id)
        hit, owner_id = self._cached_project_owner(project_id)
        if not hit:
            self._schedule_owner_resolve(project_id)
            return set()
        if not owner_id:
            return set()

        return {
            ws
            for ws, subscriber_id in self._global_subscribers.items()
            if subscriber_id and subscriber_id == owner_id
        }

    async def broadcast(self, task_id: str, message: dict):
        """向所有订阅了 task_id 的客户端 + 有权查看的全局订阅者并发广播消息。

        H5: 使用 asyncio.gather 并发发送，慢客户端不会阻塞其他客户端。
        按 task_id 订阅的连接已在接入时完成归属校验，此处不再重复判定；
        全局订阅者必须逐个通过归属过滤。
        """
        targets: Set[WebSocket] = set()
        if task_id in self._subscribers:
            targets.update(self._subscribers[task_id])
        targets.update(self._global_targets(message))

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
            self._global_subscribers.pop(ws, None)
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
