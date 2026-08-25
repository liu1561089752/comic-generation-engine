"""
通用 LLM 适配器 — 基于 liteLLM

统一使用 litellm.acompletion 对接任意提供商（OpenAI / DeepSeek / 通义 / Anthropic /
Gemini 等），自定义 OpenAI 兼容端点通过 model 加 "openai/" 前缀 + api_base 指定。

保留能力：
- 全局并发信号量 _llm_semaphore（与原实现一致）
- 调用日志写入 model_call_logs（供 /model-logs 查看）
- 错误消息映射为业务友好的中文提示（与前端展示文案兼容）
- chat() / health_check() 接口不变，所有调用方零改动
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import litellm
from litellm import exceptions as litellm_exc

from app.infra.adapters.base_llm import BaseLLMAdapter, ChatMessage, ChatResult
from app.core.config import settings

logger = logging.getLogger(__name__)

# 全局并发限制：最多 5 个 LLM 请求同时进行
_llm_semaphore = asyncio.Semaphore(5)

# 固定大小日志队列（避免内存无限增长）
from app.infra.model_logs import model_call_logs as _model_call_logs


def _map_litellm_error(e: Exception, timeout_seconds: int) -> str:
    """把 litellm 异常映射为业务友好的错误消息（与原实现文案保持一致）。"""
    if isinstance(e, litellm_exc.AuthenticationError):
        return "API Key 认证失败，请检查模型配置中的 API Key"
    if isinstance(e, litellm_exc.RateLimitError):
        return "API 请求频率超限，已重试多次仍失败"
    if isinstance(e, litellm_exc.APIConnectionError):
        return "无法连接到 AI 服务，请检查网络和地址配置"
    if isinstance(e, (litellm_exc.InternalServerError, litellm_exc.ServiceUnavailableError, litellm_exc.BadGatewayError)):
        return "AI 服务暂时不可用，请稍后重试"
    if isinstance(e, litellm_exc.BadRequestError):
        return f"AI 请求参数错误：{e}"
    msg = str(e).lower()
    if "timeout" in msg or "timed out" in msg:
        return f"AI 请求超时（已等待 {timeout_seconds} 秒），模型响应时间过长，建议联系 API 提供商或降低请求复杂度"
    return f"AI 调用失败：{e}"


class LLMAdapter(BaseLLMAdapter):
    """
    基于 liteLLM 的通用 LLM 适配器。

    重试（num_retries）与超时（timeout）由 liteLLM 统一处理，
    业务层不再自行重试。
    """

    def __init__(
        self,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 3600,
        max_retries: int = 3,
    ):
        # 优先级：运行时配置（DB/前端保存）> 显式参数 > settings（.env）
        runtime = self._get_runtime_config()
        self.api_base = (runtime["api_base"] or api_base or settings.LLM_API_BASE or "").rstrip("/")
        self.api_key = runtime["api_key"] or api_key or settings.LLM_API_KEY or ""
        self.model = runtime["model_name"] or model or settings.LLM_MODEL or ""
        logger.info(
            f"LLMAdapter 初始化: api_base={self.api_base}, model={self.model}, "
            f"api_key={'已设置' if self.api_key else '空'}"
        )
        self.timeout = timeout
        self.max_retries = max_retries

    def _get_runtime_config(self) -> dict:
        """获取运行时 LLM 配置（前端模型配置页保存到内存中的值）"""
        try:
            from app.routers.system import _llm_config
            return {
                "api_base": _llm_config.get("api_base", ""),
                "api_key": _llm_config.get("api_key", ""),
                "model_name": _llm_config.get("model_name", ""),
            }
        except (ImportError, AttributeError, Exception):
            logger.warning("无法获取运行时 LLM 配置，使用环境变量或默认值")
            return {"api_base": "", "api_key": "", "model_name": ""}

    def _litellm_model(self) -> str:
        """模型名归一化：无 provider 前缀时自动加 openai/（自定义 OpenAI 兼容端点）。

        如 "mock-model" → "openai/mock-model"，litellm 请求时会去掉前缀，
        请求体 model 为 "mock-model"；已有前缀（deepseek/xxx）则原样使用。
        """
        m = self.model or ""
        if m and "/" not in m:
            return f"openai/{m}"
        return m

    def _litellm_api_base(self) -> Optional[str]:
        """api_base 归一化：仅对自定义 OpenAI 兼容端点（model 无前缀 → openai/）补齐 /v1。

        旧实现（httpx 直连）会自动拼接 /v1/chat/completions；litellm 不会补 /v1，
        因此这里保持兼容：端点未以 /v1 结尾时补上，避免现有无 /v1 配置（如本地中转）404。
        已有 provider 前缀（deepseek/xxx 等）的模型路径由 litellm 原生处理，不干预。
        """
        if self.model and "/" not in self.model and self.api_base:
            base = self.api_base.rstrip("/")
            if not base.endswith("/v1"):
                return base + "/v1"
        return self.api_base

    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> ChatResult:
        """
        调用 LLM 聊天补全（liteLLM 统一处理重试/超时）。

        信号量覆盖整个调用生命周期（含 liteLLM 内部重试）。
        """
        if not self.api_key:
            raise ValueError("AI 服务未配置 API Key，请在「模型配置」页面设置 API Key")
        if not self.model:
            raise ValueError("AI 服务未配置模型名称，请在「模型配置」页面选择或输入模型")

        payload_messages = [
            {"role": m.role, "content": m.content} for m in messages
        ]

        request_summary = {
            "model": self.model,
            "message_count": len(payload_messages),
            "first_message_role": payload_messages[0]["role"] if payload_messages else None,
            "temperature": temperature,
            "api_base": self.api_base,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
        }

        start_ts = time.monotonic()
        try:
            # 信号量覆盖完整生命周期（含 liteLLM 内部重试）
            async with _llm_semaphore:
                logger.info(
                    f"LLM request (litellm): model={self.model}, "
                    f"messages={len(payload_messages)}, temp={temperature}, "
                    f"api_base={self.api_base}"
                )
                resp = await litellm.acompletion(
                    model=self._litellm_model(),
                    messages=payload_messages,
                    api_base=self._litellm_api_base() or None,
                    api_key=self.api_key,
                    temperature=temperature,
                    max_tokens=max_tokens or settings.LLM_MAX_TOKENS,
                    num_retries=self.max_retries,
                    timeout=self.timeout,
                )
        except Exception as e:
            duration_ms = int((time.monotonic() - start_ts) * 1000)
            self._append_log({
                "id": str(uuid.uuid4()),
                "model_type": "llm",
                "model_name": self.model,
                "call_type": "chat_stream",
                "request": request_summary,
                "duration_ms": duration_ms,
                "status": "failed",
                "error_message": str(e),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            logger.error(f"LLM chat failed (model={self.model}): {e}")
            raise ValueError(_map_litellm_error(e, self.timeout)) from e

        try:
            choice = resp.choices[0]
            full_content = choice.message.content or ""
            usage = {
                "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(resp.usage, "completion_tokens", 0) or 0,
                "total_tokens": getattr(resp.usage, "total_tokens", 0) or 0,
            }
            model_used = getattr(resp, "model", "") or self.model
        except (IndexError, AttributeError) as e:
            raise ValueError(f"AI 服务返回了无效响应，请检查模型名称（当前: {self.model}）是否正确") from e

        duration_ms = int((time.monotonic() - start_ts) * 1000)
        self._append_log({
            "id": str(uuid.uuid4()),
            "model_type": "llm",
            "model_name": self.model,
            "call_type": "chat_stream",
            "request": request_summary,
            "response_tokens": usage,
            "duration_ms": duration_ms,
            "status": "success",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(
            f"LLM response: model={model_used}, tokens={usage.get('total_tokens', '?')}, "
            f"content_len={len(full_content)}, duration_ms={duration_ms}"
        )

        return ChatResult(
            content=full_content,
            model=model_used,
            usage=usage,
        )

    def _append_log(self, entry: dict):
        """追加日志到全局队列，自动限制大小"""
        try:
            _model_call_logs.append(entry)
        except Exception as e:
            logger.warning(f"Failed to append model call log: {e}")

    async def health_check(self) -> bool:
        """健康检查：发送一条简短的请求确认服务可用"""
        if not self.api_key or not self.model:
            logger.warning("Health check skipped due to missing API key or model")
            return False
        try:
            async with _llm_semaphore:
                await litellm.acompletion(
                    model=self._litellm_model(),
                    messages=[{"role": "user", "content": "ping"}],
                    api_base=self._litellm_api_base() or None,
                    api_key=self.api_key,
                    max_tokens=10,
                    timeout=10.0,
                )
            return True
        except Exception as e:
            logger.warning(f"LLM health check failed: {e}")
            return False
