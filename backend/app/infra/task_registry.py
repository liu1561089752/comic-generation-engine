"""后台任务注册表

解决：
- D27: asyncio.create_task 未持有引用，任务可能被 GC 回收
- D39: 任务取消只改 DB 状态不取消协程

提供强引用持有 + task_id 到 asyncio.Task 的映射，支持取消运行中的协程。
"""

import asyncio
import logging
from typing import Dict, Set
from uuid import UUID

logger = logging.getLogger(__name__)

# 持有所有运行中任务的强引用，防止 GC 回收（D27）
_running_tasks: Set[asyncio.Task] = set()

# task_id → asyncio.Task 映射，支持取消（D39）
_task_map: Dict[str, asyncio.Task] = {}


def spawn_background_task(task_id: UUID, coro) -> asyncio.Task:
    """创建后台任务并持有强引用，防止 GC 回收。

    Args:
        task_id: 关联的 Task 记录 ID
        coro: 要执行的协程

    Returns:
        asyncio.Task 对象
    """
    task = asyncio.create_task(coro)
    key = str(task_id)
    _running_tasks.add(task)
    _task_map[key] = task
    task.add_done_callback(
        lambda t: (
            _running_tasks.discard(t),
            _task_map.pop(key, None),
        )
    )
    logger.info(f"后台任务已创建: task_id={key}, 当前运行中={len(_running_tasks)}")
    return task


async def cancel_background_task(task_id: UUID) -> bool:
    """取消后台任务，同时中断协程（D39）。

    带有 5 秒超时保护，防止任务在阻塞操作中无法及时响应取消信号。
    Returns:
        True 如果任务被取消，False 如果任务不存在或已完成。
    """
    key = str(task_id)
    task = _task_map.get(key)
    if task is None or task.done():
        return False
    task.cancel()
    try:
        await asyncio.wait_for(task, timeout=5.0)
    except asyncio.CancelledError:
        pass
    except asyncio.TimeoutError:
        logger.warning(f"取消后台任务 {key} 超时（任务未在 5 秒内停止）")
    except Exception as e:
        logger.warning(f"取消后台任务 {key} 时捕获异常: {e}")
    logger.info(f"后台任务已取消: task_id={key}")
    return True


def get_running_task(task_id: UUID) -> asyncio.Task | None:
    """获取运行中的任务对象"""
    return _task_map.get(str(task_id))


def running_task_count() -> int:
    """当前运行中的任务数"""
    return len(_running_tasks)
