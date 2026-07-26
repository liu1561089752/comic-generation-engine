from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


class ChatMessage:
    """聊天消息"""
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content


@dataclass
class ChatResult:
    content: str
    model: str
    usage: dict = field(default_factory=dict)


class BaseLLMAdapter(ABC):
    """LLM 适配器基类"""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatResult:
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        pass
