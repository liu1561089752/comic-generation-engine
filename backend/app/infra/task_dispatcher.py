"""任务派发器 — 根据 task_type 重新派发后台任务。

用于 retry 功能：从 Task 的 input_data 中提取参数，
找到对应的 _run_* 函数并重新执行。

注册模式：各 router 在模块加载时通过 register_task_runner 注册，
避免循环导入。
"""
import logging
from typing import Callable, Dict, Any, Awaitable
from uuid import UUID

from app.infra.task_progress import TaskProgressTracker
from app.models.task import Task

logger = logging.getLogger(__name__)

# task_type → async factory(task: Task, tracker: TaskProgressTracker) -> None
_task_runners: Dict[str, Callable[[Task, TaskProgressTracker], Awaitable[None]]] = {}


def register_task_runner(task_type: str):
    """注册 task_type 对应的后台执行函数（装饰器工厂）。

    用法:
        @register_task_runner("generate_storyboard")
        async def _run(task, tracker):
            ...
    """
    def decorator(runner: Callable[[Task, TaskProgressTracker], Awaitable[None]]):
        _task_runners[task_type] = runner
        return runner
    return decorator


def get_task_runner(task_type: str):
    """获取 task_type 对应的执行函数，未注册返回 None。"""
    return _task_runners.get(task_type)


async def redispatch_task(task: Task, tracker: TaskProgressTracker) -> None:
    """根据 task.task_type 和 task.input_data 重新派发后台任务。

    Raises:
        ValueError: task_type 未注册
    """
    runner = _task_runners.get(task.task_type)
    if runner is None:
        raise ValueError(
            f"任务类型 '{task.task_type}' 未注册后台执行函数，无法重试"
        )
    await runner(task, tracker)
