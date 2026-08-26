"""
Task 进度追踪工具

H4 修复：tracker 不再持有 session 引用，每次 DB 操作用独立短 session。
消除 session 生命周期与 tracker 生命周期耦合导致的连接泄漏。
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update as sa_update
from sqlalchemy.exc import IntegrityError

from app.core.database import async_session_factory
from app.models.task import Task
from app.infra.websocket import task_event_manager

logger = logging.getLogger(__name__)


class TaskProgressTracker:
    """Task 进度追踪器（H4: 不持有 session）。

    用法:
        tracker = await TaskProgressTracker.create(
            project_id, task_type, "generate_script",
            {"novel_id": str(novel_id)}
        )
        await tracker.update_progress(50, "正在处理第3章...")
        await tracker.complete(output_data)
    """

    # 流式输出刷写间隔（秒）：token 太频繁，批量累积后写库
    _STREAM_FLUSH_INTERVAL = 0.3

    def __init__(self, task: Task):
        self.task = task
        self._broadcast_enabled = True
        self._task_id = task.id
        # 流式输出缓冲（push_stream 使用，节流批量写入 DB）。
        # 多流并行：每个流用 stream_key 标识（章节/批次序号），事件以 JSONL 行写入。
        self._stream_buffer: List[str] = []
        self._stream_lock = asyncio.Lock()
        self._last_stream_flush = 0.0

    @classmethod
    async def create(
        cls,
        session: Optional[AsyncSession] = None,
        project_id: Optional[UUID] = None,
        task_type: str = "",
        title: str = "",
        input_data: Optional[Dict] = None,
        priority: str = "normal",
    ) -> "TaskProgressTracker":
        """创建新的 Task 记录并返回 tracker。

        session 参数已废弃（H4），仅为向后兼容保留，实际使用独立短 session。
        """
        async with async_session_factory() as sess:
            task = Task(
                project_id=project_id,
                task_type=task_type,
                status="queued",
                priority=priority,
                progress=0,
                input_data=input_data or {},
                logs=[],
            )
            sess.add(task)
            try:
                await sess.flush()

                task.logs = task.logs or []
                task.logs.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": title or f"任务已创建 (type={task_type})",
                    "level": "info",
                })
                await sess.commit()
            except IntegrityError:
                # 命中活跃任务去重唯一索引（uq_tasks_active_dedup）：
                # 并发重复提交时复用已存在的未完成任务，而不是让请求失败。
                # 该索引不存在时不会走到此分支，行为与之前一致。
                await sess.rollback()
                existing = await find_running_task(
                    sess, project_id, task_type,
                    (input_data or {}).get("novel_id"),
                )
                if existing is None:
                    raise
                logger.info(
                    f"已存在同类未完成任务 {existing.id} (type={task_type})，复用该任务"
                )
                return cls(existing)

        tracker = cls(task)
        await tracker._broadcast()
        return tracker

    async def rebind_session(self, session: AsyncSession) -> None:
        """已废弃（H4）— tracker 不再持有 session，此方法为 no-op。"""
        pass

    async def set_running(self, message: str = "任务开始执行"):
        self.task.status = "running"
        self.task.started_at = datetime.now(timezone.utc)
        self.task.progress = 0
        await self._add_log(message, "info")
        if await self._flush(expected_statuses=("queued", "running")):
            await self._broadcast()

    async def update_progress(self, progress: int, message: Optional[str] = None):
        self.task.progress = min(max(progress, 0), 100)
        if message:
            await self._add_log(message, "info")
        if await self._flush(expected_statuses=("queued", "running")):
            await self._broadcast()

    async def add_log(self, message: str, level: str = "info"):
        await self._add_log(message, level)
        await self._broadcast()

    # ─────────────────────────────────────────────
    # 流式输出（生成脚本等任务的实时文本）
    # ─────────────────────────────────────────────

    async def push_stream(
        self,
        delta: str = "",
        stream_key: Optional[int] = None,
        stream_header: Optional[str] = None,
    ):
        """追加一段流式输出（节流批量写 DB，支持多流并行）。

        - 多流并行：并行生成的多章/多批任务各用一个 stream_key（章节/批次序号），
          事件以 JSONL 行写入（{"k": key, "t": 文本增量} / {"k": key, "h": 标题}），
          前端按 key 分组渲染，互不干扰。单流任务（如生成脚本）不传 key（k=null）。
        - 缓冲累计，每 _STREAM_FLUSH_INTERVAL 秒刷写一次，避免每 token 一次 UPDATE
        - 用 SQL 级 concat（stream_output = stream_output || :delta）只传输增量，
          全量文本由 PostgreSQL 服务端拼接，DB 往返与网络开销可控
        - 只写 DB 不广播（前端通过轮询接口增量读取），避免 WS 大 payload

        Args:
            delta: 文本增量
            stream_key: 流标识（并行任务传入章节/批次序号，None=单流）
            stream_header: 流的标题事件（该流首次出现时写入，如"第 1/5 章：xxx"）
        """
        if not delta and stream_header is None:
            return
        async with self._stream_lock:
            if stream_header is not None:
                self._stream_buffer.append(
                    json.dumps({"k": stream_key, "h": stream_header}, ensure_ascii=False)
                )
            if delta:
                self._stream_buffer.append(
                    json.dumps({"k": stream_key, "t": delta}, ensure_ascii=False)
                )
            now = time.monotonic()
            if now - self._last_stream_flush < self._STREAM_FLUSH_INTERVAL:
                return
            lines = self._stream_buffer
            self._stream_buffer = []
            self._last_stream_flush = now
        await self._write_stream_lines(lines)

    async def flush_stream(self):
        """强制刷写剩余缓冲（任务完成/失败前调用）。"""
        async with self._stream_lock:
            lines = self._stream_buffer
            self._stream_buffer = []
            if not lines:
                return
        await self._write_stream_lines(lines)

    async def _write_stream_lines(self, lines: List[str]):
        if not lines:
            return
        buffer = "".join(line + "\n" for line in lines)
        try:
            async with async_session_factory() as sess:
                stmt = (
                    sa_update(Task)
                    .where(Task.id == self._task_id)
                    .values(stream_output=Task.stream_output + buffer)
                )
                await sess.execute(stmt)
                await sess.commit()
        except Exception as e:
            logger.error(
                f"Task {self._task_id} 流式输出写入失败: {e}",
                exc_info=True,
            )

    async def complete(self, output_data: Optional[Any] = None, message: str = "任务完成", broadcast: bool = True):
        self.task.status = "completed"
        self.task.progress = 100
        self.task.completed_at = datetime.now(timezone.utc)
        self.task.output_data = output_data
        await self._add_log(message, "success")
        if await self._flush(expected_statuses=("queued", "running")):
            if broadcast:
                await self._broadcast()

    async def fail(self, error_message: str, exc_info: bool = True):
        self.task.status = "failed"
        self.task.error_message = error_message
        self.task.completed_at = datetime.now(timezone.utc)
        await self._add_log(error_message, "error")
        if await self._flush(expected_statuses=("queued", "running")):
            await self._broadcast()
        if exc_info:
            logger.exception(error_message)
        else:
            logger.error(error_message)

    async def _flush(self, expected_statuses: Optional[tuple] = None) -> bool:
        """H4: 用独立短 session 执行 UPDATE，不持有 session。

        返回 False 表示状态未持久化（DB 异常或状态不匹配）。
        调用方（complete/fail 等）据此决定是否广播，但不抛异常——
        避免在 fail() 中用 flush 异常掩盖原始业务异常。
        DB 故障时 task 会停留在 running，由轮询补偿机制兜底。
        """
        try:
            async with async_session_factory() as sess:
                stmt = sa_update(Task).where(Task.id == self._task_id)
                if expected_statuses:
                    stmt = stmt.where(Task.status.in_(expected_statuses))
                stmt = stmt.values(
                    status=self.task.status,
                    progress=self.task.progress,
                    error_message=self.task.error_message,
                    started_at=self.task.started_at,
                    completed_at=self.task.completed_at,
                    logs=self.task.logs or [],
                    output_data=self.task.output_data,
                )
                result = await sess.execute(stmt)
                await sess.commit()
                if expected_statuses and (result.rowcount or 0) == 0:
                    logger.info(
                        f"Task {self._task_id} 状态更新被跳过 "
                        f"(当前状态不在 {expected_statuses} 中)"
                    )
                    return False
                return True
        except Exception as e:
            logger.error(
                f"Task {self._task_id} 状态持久化失败 "
                f"(目标状态={self.task.status}): {e}",
                exc_info=True,
            )
            return False

    async def _add_log(self, message: str, level: str = "info"):
        self.task.logs = self.task.logs or []
        self.task.logs.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": message,
            "level": level,
        })

    async def _broadcast(self):
        if not self._broadcast_enabled:
            return
        try:
            msg = {
                "type": "task_update",
                "task_id": str(self._task_id),
                "project_id": str(self.task.project_id) if self.task.project_id else None,
                "task_type": self.task.task_type,
                "status": self.task.status,
                "progress": self.task.progress,
                "logs": self.task.logs or [],
                "error_message": self.task.error_message,
                "started_at": self.task.started_at.isoformat() if self.task.started_at else None,
                "completed_at": self.task.completed_at.isoformat() if self.task.completed_at else None,
            }
            await task_event_manager.broadcast(str(self._task_id), msg)
        except Exception as e:
            logger.warning(f"WebSocket 广播失败: {e}")


async def create_task_tracker(
    session: Optional[AsyncSession] = None,
    project_id: Optional[UUID] = None,
    task_type: str = "",
    title: str = "",
    input_data: Optional[Dict] = None,
) -> TaskProgressTracker:
    """快捷创建 Task tracker。session 参数已废弃（H4）。"""
    return await TaskProgressTracker.create(
        session, project_id, task_type, title, input_data
    )


async def find_running_task(
    session: AsyncSession,
    project_id: Optional[UUID],
    task_type: str,
    novel_id: Optional[str] = None,
) -> Optional[Task]:
    """检查是否已有同类型的 queued/running 任务。

    novel_id 过滤直接下推到 SQL（PostgreSQL JSONB 路径查询），
    避免加载多条记录后内存过滤。
    """
    stmt = select(Task).where(
        Task.task_type == task_type,
        Task.status.in_(["queued", "running"]),
    )
    if project_id:
        stmt = stmt.where(Task.project_id == project_id)
    else:
        stmt = stmt.where(Task.project_id.is_(None))

    if novel_id:
        stmt = stmt.where(
            Task.input_data["novel_id"].as_string() == novel_id
        )

    stmt = stmt.limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
