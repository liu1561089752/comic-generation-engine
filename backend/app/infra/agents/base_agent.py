from abc import ABC, abstractmethod
from typing import Any, Optional, Dict
from datetime import datetime, timezone
import json
import logging
import uuid

logger = logging.getLogger(__name__)


class AgentContext:
    """Agent 执行上下文"""

    def __init__(self, task_id: Optional[str] = None, max_retries: int = 3,
                 chapter_id: Optional[str] = None, user_id: Optional[str] = None,
                 trace_id: Optional[str] = None):
        self.task_id = task_id
        self.chapter_id = chapter_id
        self.user_id = user_id
        self.trace_id = trace_id or str(uuid.uuid4())
        self.max_retries = max_retries
        self.retry_count = 0
        self.started_at = datetime.now(timezone.utc)


class AgentResult:
    """Agent 执行结果"""

    def __init__(self, success: bool, data: Any = None, error: Optional[str] = None):
        self.success = success
        self.data = data
        self.error = error
        self.completed_at = datetime.now(timezone.utc)


class BaseAgent(ABC):
    """所有 Agent 的抽象基类"""

    @abstractmethod
    async def process(self, context: AgentContext, **kwargs) -> AgentResult:
        pass

    async def validate_input(self, data: dict) -> bool:
        """验证输入数据是否符合预期 Schema"""
        return True

    async def validate_output(self, data: dict) -> bool:
        """验证输出数据是否符合预期 Schema"""
        return True

    async def fallback(self, context: AgentContext, error: Exception, **kwargs) -> AgentResult:
        """降级处理方法：当 process 多次失败后调用"""
        return AgentResult(success=False, data={}, error=str(error))

    async def handle_failure(self, context: AgentContext, error: Exception, **kwargs) -> AgentResult:
        """统一异常处理"""
        logger.error(f"Agent {self.__class__.__name__} failed: {error}", exc_info=True)
        if context.retry_count < context.max_retries:
            context.retry_count += 1
            logger.info(f"Retry {context.retry_count}/{context.max_retries}")
            return await self.process(context, **kwargs)
        return await self.fallback(context, error, **kwargs)
