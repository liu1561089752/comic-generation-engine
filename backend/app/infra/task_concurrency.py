"""单图生成任务的每类型并发控制。

背景：角色形象 / 状态形象 / 场景 / 道具 / 建筑 / 服装 的图片生成任务
每个模块最多同时生成 2 张，其余任务创建后进入排队，前面的完成后自动补位。

实现：按 task_type 各持有一个 asyncio.Semaphore(2)。任务执行器（runner）
在 set_running 之前 acquire，拿不到信号量就等待——此时任务在 DB 中保持
queued 状态，前端轮询看到"排队中"；前面的任务 complete 释放信号量后，
排队的任务自动获得执行权并转为 running。
"""

import asyncio
from typing import Dict

# 每个图片生成模块的最大并发数
IMAGE_TASK_CONCURRENCY = 2

_semaphores: Dict[str, asyncio.Semaphore] = {}


def get_image_task_semaphore(task_type: str) -> asyncio.Semaphore:
    """获取指定任务类型的并发信号量（懒创建，首次在 async 上下文中调用）。"""
    sem = _semaphores.get(task_type)
    if sem is None:
        sem = asyncio.Semaphore(IMAGE_TASK_CONCURRENCY)
        _semaphores[task_type] = sem
    return sem
