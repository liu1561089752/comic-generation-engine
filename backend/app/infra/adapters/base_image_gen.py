from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class BaseImageGenerator(ABC):
    """
    生图模型适配器基类

    定义统一的生图接口，不同的后端（SD API、Midjourney、DALL-E 等）
    通过实现此接口来接入系统。
    """

    @abstractmethod
    async def generate(self, prompt: str, negative_prompt: str = "",
                       params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        生成单张图片

        Args:
            prompt: 正向 Prompt
            negative_prompt: 反向 Prompt
            params: 生图参数（width, height, steps, cfg_scale, seed 等）

        Returns:
            dict: {
                "image_url": str,
                "seed": int,
                "info": dict,   # 模型返回的原始信息
            }
        """
        pass

    @abstractmethod
    async def generate_batch(self, prompts: list, negative_prompt: str = "",
                             params: Optional[Dict[str, Any]] = None) -> list:
        """
        批量生图

        Args:
            prompts: 正向 Prompt 列表
            negative_prompt: 反向 Prompt
            params: 生图参数

        Returns:
            list[dict]: 每张图片的结果
        """
        pass

    @abstractmethod
    async def check_health(self) -> bool:
        """检查后端服务是否可用"""
        pass
