"""进程内滑动窗口速率限制器。

用于登录等敏感接口的暴力破解防护。
单进程内生效；多 worker/多实例部署时各进程独立计数（近似限流），
如需精确限流可替换为 Redis 实现（接口保持兼容）。
"""
import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Deque

logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """滑动窗口限流器：key 在 window_seconds 内的请求数不超过 max_requests。"""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # key -> 窗口内请求时间戳队列（deque 自动淘汰）
        self._hits: dict[str, Deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        """尝试放行一次请求；超限返回 False。"""
        now = time.monotonic()
        async with self._lock:
            ts_queue = self._hits[key]
            # 淘汰窗口外的旧时间戳
            while ts_queue and now - ts_queue[0] >= self.window_seconds:
                ts_queue.popleft()
            if len(ts_queue) >= self.max_requests:
                return False
            ts_queue.append(now)
            return True

    async def remaining(self, key: str) -> int:
        """当前窗口内剩余可用次数（用于响应头提示，可选）。"""
        now = time.monotonic()
        async with self._lock:
            ts_queue = self._hits[key]
            while ts_queue and now - ts_queue[0] >= self.window_seconds:
                ts_queue.popleft()
            return max(0, self.max_requests - len(ts_queue))

    def prune(self) -> None:
        """清理长期无访问的 key，防止内存增长（定时调用或惰性）。"""
        now = time.monotonic()
        expired = [
            k for k, q in self._hits.items()
            if not q or now - q[-1] >= self.window_seconds * 10
        ]
        for k in expired:
            del self._hits[k]


# 登录限流：每 (IP + 用户名) 5 次 / 60 秒
login_limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60.0)
