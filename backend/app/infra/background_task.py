"""后台任务统一执行模板

H4 修复：tracker 不再持有 session，每次 DB 操作用独立短 session。
业务逻辑（coro_factory）内部也应使用 async_session_factory() 创建自己的 session。
"""

import logging
from typing import Awaitable, Callable

from app.infra.task_progress import TaskProgressTracker

logger = logging.getLogger(__name__)


async def run_background_task(
    tracker: TaskProgressTracker,
    coro_factory: Callable[[TaskProgressTracker], Awaitable],
) -> None:
    """后台任务统一模板（H4: 无需外部 session）。

    Args:
        tracker: 路由层创建的 TaskProgressTracker（含 task_id）
        coro_factory: 接收 tracker，返回业务协程的函数
    """
    task_id = tracker._task_id
    try:
        await tracker.set_running()
        result = await coro_factory(tracker)
        await tracker.complete(broadcast=False)
        await tracker._broadcast()
    except Exception as e:
        logger.exception(f"后台任务失败 (task_id={task_id}): {e}")
        try:
            await tracker.fail(str(e))
        except Exception:
            logger.error(f"写入失败状态时出错 (task_id={task_id})", exc_info=True)
