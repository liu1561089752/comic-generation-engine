"""
生图适配器 — 基于 liteLLM（统一替代 Flow API 桥接）

使用 litellm.aimage_generation 对接任意 OpenAI 兼容生图端点：
- model 统一加 "openai/" 前缀 + api_base 指定自定义端点
- 参考图通过 image_base64 / image_mime_type 透传（实测 liteLLM 支持）
- 重试（num_retries）与超时（timeout）由 liteLLM 统一处理

对外接口与旧 GRSaiAPIAdapter 一致：
    generate(prompt, negative_prompt="", params=None) -> {"image_url", ...}
"""
import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import litellm

from app.core.config import settings
from app.infra.adapters.base_image_gen import BaseImageGenerator
from app.infra.model_logs import model_call_logs as _model_call_logs

logger = logging.getLogger(__name__)

# adapter 内部信号量：全局图片生成并发上限
_image_semaphore = asyncio.Semaphore(settings.IMAGE_MAX_CONCURRENT)


class ImageGenAdapter(BaseImageGenerator):
    """
    基于 liteLLM 的生图适配器（OpenAI 兼容端点）。

    改进：
    - 统一走 liteLLM，不再单独支持 Flow 桥接
    - 429/5xx/连接错误重试由 liteLLM num_retries 处理
    - 参考图参数（image_base64/image_mime_type）透传
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

    def _litellm_model(self) -> str:
        """模型名归一化：无 provider 前缀时自动加 openai/（自定义 OpenAI 兼容端点）。"""
        m = self.model or ""
        if m and "/" not in m:
            return f"openai/{m}"
        return m

    def _litellm_api_base(self) -> str:
        """api_base 归一化：仅对自定义 OpenAI 兼容端点（model 无前缀 → openai/）补齐 /v1。

        旧实现（httpx 直连）会自动拼接 /v1/images/generations；litellm 不会补 /v1，
        因此这里保持兼容：端点未以 /v1 结尾时补上，避免现有无 /v1 配置（如本地 Flow 中转）404。
        已有 provider 前缀的模型路径由 litellm 原生处理，不干预。
        """
        if self.model and "/" not in self.model and self.api_base:
            base = self.api_base.rstrip("/")
            if not base.endswith("/v1"):
                return base + "/v1"
        return self.api_base

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

    def _append_log(self, entry: dict):
        try:
            _model_call_logs.append(entry)
        except Exception as e:
            logger.warning(f"Failed to append image call log: {e}")

    async def generate(self, prompt: str, negative_prompt: str = "",
                       params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        调用 OpenAI 兼容生图端点（liteLLM）。

        有参考图时附加 image_base64 / image_mime_type 参数。
        内部信号量控制并发，重试由 liteLLM num_retries 处理。
        """
        p = params or {}
        kwargs: Dict[str, Any] = {}

        # 图生图：解析参考图并透传
        images = p.get("images")
        if images and isinstance(images, list) and len(images) > 0:
            parsed = [self._parse_data_uri(img) for img in images]
            base64_list = [item[0] for item in parsed]
            mime_list = [item[1] for item in parsed]
            # 单张传字符串，多张传数组
            kwargs["image_base64"] = base64_list[0] if len(base64_list) == 1 else base64_list
            kwargs["image_mime_type"] = mime_list[0] if len(mime_list) == 1 else mime_list

        seed = p.get("seed")
        if seed:
            kwargs["seed"] = seed

        start_ts = time.monotonic()
        try:
            async with _image_semaphore:
                logger.info(
                    f"生图请求 (litellm): model={self.model}, prompt 长度={len(prompt)}, "
                    f"参考图数={len(images) if images else 0}"
                )
                resp = await litellm.aimage_generation(
                    prompt=prompt,
                    model=self._litellm_model(),
                    api_base=self._litellm_api_base(),
                    api_key=self.api_key,
                    n=1,
                    size=p.get("aspectRatio", "1:1"),
                    # 不传 response_format：OpenAI 兼容端点默认返回 url，
                    # 即使返回 b64_json，下方分支也能处理；避免部分模型不支持该参数
                    max_retries=self.max_retries,
                    timeout=self.request_timeout,
                    **kwargs,
                )
        except Exception as e:
            duration_ms = int((time.monotonic() - start_ts) * 1000)
            self._append_log({
                "id": str(uuid.uuid4()),
                "model_type": "image",
                "model_name": self.model,
                "call_type": "image_generation",
                "duration_ms": duration_ms,
                "status": "failed",
                "error_message": str(e),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            logger.error(f"生图失败 (model={self.model}): {e}")
            # 统一抛 "generate failed" 前缀，供业务层（generation service）识别并重试
            raise RuntimeError(f"generate failed: {e}") from e

        try:
            data = resp.data[0]
        except (IndexError, AttributeError) as e:
            raise RuntimeError(f"generate failed: 生图结果中没有图片数据: {e}") from e

        if getattr(data, "url", None):
            image_url = data.url
        elif getattr(data, "b64_json", None):
            image_url = f"data:image/png;base64,{data.b64_json}"
        else:
            raise RuntimeError("generate failed: 生图结果中没有图片 URL")

        duration_ms = int((time.monotonic() - start_ts) * 1000)
        self._append_log({
            "id": str(uuid.uuid4()),
            "model_type": "image",
            "model_name": self.model,
            "call_type": "image_generation",
            "duration_ms": duration_ms,
            "status": "success",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return {
            "image_url": image_url,
            "status": "succeeded",
            "progress": 100,
            "id": "",
        }

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
        """检查生图服务是否可用（GET {api_base}/health）"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.api_base}/health")
                return resp.status_code == 200
        except Exception as e:
            logger.warning(f"生图服务健康检查失败: {e}")
            return False
