"""全局 httpx.AsyncClient 单例管理

复用连接池，统一超时配置，在应用 shutdown 时清理。
解决 D25（连接泄漏）、D36（无连接池复用）。
"""

import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class HttpClientManager:
    """全局 httpx.AsyncClient 单例，复用连接池"""

    _llm_client: Optional[httpx.AsyncClient] = None
    _image_client: Optional[httpx.AsyncClient] = None

    @classmethod
    def get_llm_client(cls) -> httpx.AsyncClient:
        if cls._llm_client is None or cls._llm_client.is_closed:
            cls._llm_client = httpx.AsyncClient(
                trust_env=False,  # 绕过系统代理（如 Clash）
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=300.0,
                    write=10.0,
                    pool=5.0,
                ),
                limits=httpx.Limits(
                    max_connections=20,
                    max_keepalive_connections=5,
                ),
            )
        return cls._llm_client

    @classmethod
    def get_image_client(cls) -> httpx.AsyncClient:
        if cls._image_client is None or cls._image_client.is_closed:
            cls._image_client = httpx.AsyncClient(
                trust_env=False,  # 绕过系统代理（如 Clash）
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=300.0,
                    write=30.0,
                    pool=5.0,
                ),
                limits=httpx.Limits(
                    max_connections=max(settings.IMAGE_MAX_CONCURRENT * 2, 4),
                    max_keepalive_connections=max(settings.IMAGE_MAX_CONCURRENT, 2),
                ),
            )
        return cls._image_client

    @classmethod
    async def close_all(cls):
        if cls._llm_client is not None and not cls._llm_client.is_closed:
            await cls._llm_client.aclose()
            cls._llm_client = None
        if cls._image_client is not None and not cls._image_client.is_closed:
            await cls._image_client.aclose()
            cls._image_client = None
        logger.info("HttpClientManager: all clients closed")
