"""共享的模型调用日志队列。

LLM 适配器和 system 路由共同写入此队列，
使 GET /api/v1/system/model-logs 能返回所有适配器的调用记录。
"""
from collections import deque

_MAX_LOG_ENTRIES = 1000
model_call_logs: deque = deque(maxlen=_MAX_LOG_ENTRIES)
