"""Flow API 桥接服务适配器

通过 Flow API 桥接服务提供的 OpenAI 兼容接口生图。
API 地址: http://localhost:8567/v1/images/generations
支持模型: nano_banana_pro / nano_banana_2 / nano_banana_2_lite
"""
import asyncio
import logging
from typing import Optional, Dict, Any

import httpx

from app.core.config import settings
from app.infra.adapters.base_image_gen import BaseImageGenerator
from app.infra.adapters.http_client import HttpClientManager

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# adapter 内部信号量：全局图片生成并发上限
_image_semaphore = asyncio.Semaphore(settings.IMAGE_MAX_CONCURRENT)


class GRSaiAPIAdapter(BaseImageGenerator):
    """
    Flow API 桥接服务适配器

    通过 Flow API 桥接服务提供的 OpenAI 兼容接口生图。
    API 地址: http://localhost:8567/v1/images/generations
    支持模型: nano_banana_pro / nano_banana_2 / nano_banana_2_lite

    改进：
    - 迁移到 httpx.AsyncClient
    - 内部信号量控制并发
    - 429/5xx/连接错误重试 + 指数退避
    - generate_batch 并发执行
    """

    def __init__(self, api_base: Optional[str] = None, api_key: Optional[str] = None,
                 model: Optional[str] = None, max_retries: int = 3,
                 request_timeout: int = 300):
        runtime = self._get_runtime_config()
        self.api_base = (runtime["api_base"] or api_base or settings.IMAGE_API_BASE).rstrip("/")
        self.api_key = runtime["api_key"] or api_key or settings.IMAGE_API_KEY or ""
        self.model = runtime["model_name"] or model or settings.IMAGE_MODEL or ""
        self.max_retries = max_retries
        self.request_timeout = request_timeout

    def _get_runtime_config(self) -> dict:
        """从运行时内存缓存中获取配置（即用户在模型配置页面保存的值）"""
        try:
            from app.routers.system import _image_gen_config
            return {
                "api_base": _image_gen_config.get("api_base", ""),
                "api_key": _image_gen_config.get("api_key", ""),
                "model_name": _image_gen_config.get("model_name", ""),
            }
        except Exception as e:
            logger.warning(f"读取运行时生图配置失败，回退到settings: {e}")
            return {"api_base": "", "api_key": "", "model_name": ""}

    @staticmethod
    def _parse_data_uri(data_uri: str) -> tuple[str, str]:
        """解析 data URI，返回 (base64_data, mime_type)。

        支持格式：
        - "data:image/png;base64,xxxxx" → ("xxxxx", "image/png")
        - 纯 base64 字符串 → (原值, "image/png")
        """
        if data_uri.startswith("data:"):
            header, base64_data = data_uri.split(",", 1)
            mime_type = header.split(":")[1].split(";")[0]
            return base64_data, mime_type
        return data_uri, "image/png"

    async def generate(self, prompt: str, negative_prompt: str = "",
                       params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        调用 Flow API 桥接服务生图（阻塞式，OpenAI 兼容接口）。

        文生图和图生图统一走 /v1/images/generations，服务端阻塞等待结果后返回。
        有参考图时附加 image_base64 / image_mime_type 参数。

        内部信号量控制并发，429/5xx/连接错误重试。
        """
        p = params or {}
        payload = {
            "model": p.get("model", self.model) or "nano_banana_pro",
            "prompt": prompt,
            "n": 1,
            "size": p.get("aspectRatio", "1:1"),
            "response_format": "url",
        }

        seed = p.get("seed")
        if seed:
            payload["seed"] = seed

        # 图生图：解析参考图并附加到 payload
        images = p.get("images")
        if images and isinstance(images, list) and len(images) > 0:
            parsed = [self._parse_data_uri(img) for img in images]
            base64_list = [item[0] for item in parsed]
            mime_list = [item[1] for item in parsed]
            # 单张传字符串，多张传数组
            payload["image_base64"] = base64_list[0] if len(base64_list) == 1 else base64_list
            payload["image_mime_type"] = mime_list[0] if len(mime_list) == 1 else mime_list

        headers = {
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = f"{self.api_base}/v1/images/generations"
        ref_count = len(images) if images else 0
        logger.info(f"Flow API 请求: {url}, prompt 长度={len(prompt)}, 参考图数={ref_count}")

        client = HttpClientManager.get_image_client()
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                async with _image_semaphore:
                    resp = await client.post(url, headers=headers, json=payload, timeout=self.request_timeout)
                    resp.raise_for_status()
                    result = resp.json()

                data = result.get("data", [])
                if data and "url" in data[0]:
                    image_url = data[0]["url"]
                    return {
                        "image_url": image_url,
                        "status": "succeeded",
                        "progress": 100,
                        "id": result.get("created", ""),
                    }
                elif data and "b64_json" in data[0] and data[0]["b64_json"]:
                    image_url = f"data:image/png;base64,{data[0]['b64_json']}"
                    return {
                        "image_url": image_url,
                        "status": "succeeded",
                        "progress": 100,
                        "id": result.get("created", ""),
                    }
                else:
                    raise RuntimeError("生图结果中没有图片 URL")

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code if e.response is not None else 0
                resp_text = e.response.text if e.response is not None else ""
                logger.error(f"Flow API HTTP 错误 (attempt {attempt+1}/{self.max_retries}): {status_code} - {resp_text[:500]}")
                last_error = e
                if status_code in (429, 502, 503, 504) and attempt < self.max_retries - 1:
                    retry_after = e.response.headers.get("Retry-After") if e.response is not None else None
                    try:
                        # Retry-After 允许是 HTTP-date 而非秒数，此时退回指数退避
                        delay = min(float(retry_after), 60)
                    except (TypeError, ValueError):
                        delay = 2 ** attempt
                    await asyncio.sleep(delay)
                    continue
                raise RuntimeError(f"Flow API 请求失败 (HTTP {status_code}): {resp_text[:200]}")

            except (httpx.ConnectError, httpx.RequestError) as e:
                logger.error(f"Flow API 连接错误 (attempt {attempt+1}/{self.max_retries}): {e}", exc_info=True)
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"Flow API 请求失败: {e}")

            except RuntimeError:
                raise

            except Exception as e:
                logger.error(f"Flow API 生图出错 (attempt {attempt+1}/{self.max_retries}): {e}", exc_info=True)
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"Flow API 生图出错: {e}")

        raise RuntimeError(f"Flow API 生图失败（重试 {self.max_retries} 次后仍失败）: {last_error}")

    async def generate_batch(self, prompts: list, negative_prompt: str = "",
                             params: Optional[Dict[str, Any]] = None) -> list:
        """批量生图 - 并发执行，受内部信号量控制"""
        async def _safe_generate(prompt):
            try:
                return await self.generate(prompt, negative_prompt, params)
            except Exception as e:
                logger.error(f"批量生图中单张失败: {e}")
                return {"error": str(e)}

        results = await asyncio.gather(
            *[_safe_generate(p) for p in prompts],
            return_exceptions=False,
        )
        return list(results)

    async def check_health(self) -> bool:
        """检查 Flow API 桥接服务是否可用"""
        try:
            client = HttpClientManager.get_image_client()
            resp = await client.get(f"{self.api_base}/health", timeout=10.0)
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Flow API 健康检查失败: {e}")
            return False
