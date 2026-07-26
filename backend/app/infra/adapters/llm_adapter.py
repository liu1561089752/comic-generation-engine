"""
通用 LLM 适配器 — 基于 httpx 原生 async 流式实现

直接调用 OpenAI 兼容 API，使用 SSE 流式接收响应。
一次性解决：
- D4 信号量覆盖整个流式生命周期
- D5 超时配置实际生效
- D6 协程可取消
- D16 不占用线程池
- D25 async with 自动关闭响应
- D36 连接池复用
- D37 总超时控制
- D66 超时错误消息一致
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.infra.adapters.base_llm import BaseLLMAdapter, ChatMessage, ChatResult
from app.infra.adapters.http_client import HttpClientManager
from app.core.config import settings

logger = logging.getLogger(__name__)

# 浏览器风格请求头，绕过 Cloudflare 等安全检测
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# 固定大小日志队列（避免内存无限增长）
# 统一使用共享实例，使 system 路由的 /model-logs 端点能看到适配器调用
from app.infra.model_logs import model_call_logs as _model_call_logs

# 全局并发限制：最多 5 个 LLM 请求同时进行
# 信号量现在覆盖完整的 stream 生命周期（D4）
_llm_semaphore = asyncio.Semaphore(5)


async def _read_sse_stream_async(
    response: httpx.Response,
    initial_model: Optional[str] = None,
) -> tuple[str, Optional[str], dict]:
    """异步读取 SSE 流，不阻塞事件循环、不占用线程池（D16）"""
    content_chunks: list[str] = []
    model_used = initial_model
    usage: dict = {}
    async for line_bytes in response.aiter_lines():
        if not line_bytes:
            continue
        if isinstance(line_bytes, bytes):
            try:
                line = line_bytes.decode("utf-8", errors="replace")
            except UnicodeDecodeError:
                line = line_bytes.decode("latin-1", errors="replace").encode(
                    "latin-1"
                ).decode("utf-8", errors="replace")
        else:
            line = line_bytes
        # SSE 规范允许 "data:" 后跟可选空格；两种格式都需要处理
        if line.startswith("data:"):
            data_str = line[5:].lstrip(" ")
            if data_str.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
                choices = chunk.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    if "content" in delta and delta["content"]:
                        content_chunks.append(delta["content"])
                if not model_used:
                    model_used = chunk.get("model", model_used)
                if "usage" in chunk and chunk["usage"]:
                    usage = {
                        "prompt_tokens": chunk["usage"].get("prompt_tokens", 0),
                        "completion_tokens": chunk["usage"].get(
                            "completion_tokens", 0
                        ),
                        "total_tokens": chunk["usage"].get("total_tokens", 0),
                    }
            except json.JSONDecodeError:
                continue
    result_content = "".join(content_chunks)
    if not result_content and not usage:
        raise ValueError(
            "LLM 返回了空响应（非 SSE 格式或 API 返回了 HTML 错误页），"
            "请检查 api_base 配置是否正确"
        )
    return result_content, model_used, usage


class LLMAdapter(BaseLLMAdapter):
    """
    基于 httpx 原生 async 流式的通用 LLM 适配器

    使用 SSE 流式输出，逐步接收 AI 响应内容。
    重试逻辑在此层统一实现，业务层不再重试（D24）。
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
            f"api_key={'已设置' if self.api_key else '空'}, "
            f"runtime_key={'已设置' if runtime.get('api_key') else '空'}, "
            f"settings_key={'已设置' if settings.LLM_API_KEY else '空'}"
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

    def _build_headers(self) -> dict:
        """构建请求头"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        }

    def _build_payload(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> dict:
        """构建请求体"""
        return {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
            "stream": True,
        }

    @property
    def _api_url(self) -> str:
        """完整的聊天补全 API URL（统一使用小写 v1）"""
        return f"{self.api_base}/v1/chat/completions"

    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> ChatResult:
        """
        调用 LLM 聊天补全（流式输出）

        adapter 层统一重试（D24），业务层不再重试。
        信号量覆盖整个流式生命周期（D4）。
        async with 自动关闭响应（D25）。
        asyncio.wait_for 提供总超时（D37）。
        """
        if not self.api_key:
            raise ValueError("AI 服务未配置 API Key，请在「模型配置」页面设置 API Key")
        if not self.model:
            raise ValueError("AI 服务未配置模型名称，请在「模型配置」页面选择或输入模型")

        payload_messages = [
            {"role": m.role, "content": m.content} for m in messages
        ]

        headers = self._build_headers()
        payload = self._build_payload(payload_messages, temperature, max_tokens)
        url = self._api_url
        client = HttpClientManager.get_llm_client()

        request_summary = {
            "model": self.model,
            "message_count": len(payload_messages),
            "first_message_role": payload_messages[0]["role"] if payload_messages else None,
            "temperature": temperature,
            "api_base": self.api_base,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
        }
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                # 信号量覆盖整个流式生命周期：连接建立 + SSE 流读取 + 响应关闭（D4）
                async with _llm_semaphore:
                    logger.info(
                        f"LLM request (stream): model={self.model}, "
                        f"messages={len(payload_messages)}, temp={temperature}, "
                        f"api_base={self.api_base}"
                    )
                    start_ts = time.monotonic()
                    # async with 自动关闭响应，解决 D25 连接泄漏
                    # 原生 async stream 不占线程（D16），可被协程取消（D6）
                    async with client.stream(
                        "POST", url, headers=headers, json=payload
                    ) as resp:
                        if resp.status_code >= 400:
                            # 必须在 stream 上下文内预读：退出上下文时 httpx 会关闭
                            # 响应流，之后对未消费的流调 aread() 会抛 StreamClosed，
                            # 导致外层 except 永远拿不到错误响应体
                            await resp.aread()
                        resp.raise_for_status()
                        # 总超时控制（D37）+ self.timeout 实际生效（D5）
                        full_content, model_used, usage = await asyncio.wait_for(
                            _read_sse_stream_async(
                                resp,
                                initial_model=None,
                            ),
                            timeout=self.timeout,
                        )

                    duration_ms = int((time.monotonic() - start_ts) * 1000)
                    logger.info(
                        f"LLM stream response: model={model_used}, "
                        f"tokens={usage.get('total_tokens', '?')}, "
                        f"content_len={len(full_content)}, duration_ms={duration_ms}"
                    )

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

                    return ChatResult(
                        content=full_content,
                        model=model_used,
                        usage=usage,
                    )

            except httpx.HTTPStatusError as e:
                status = e.response.status_code if e.response is not None else 0
                body = ""
                if e.response is not None:
                    try:
                        await e.response.aread()
                        body = e.response.text[:500]
                    except Exception:
                        body = ""
                logger.warning(
                    f"LLM HTTP error (attempt {attempt+1}/{self.max_retries}): "
                    f"status={status}, body={body}"
                )
                last_error = e

                if status == 401:
                    raise ValueError("API Key 认证失败，请检查模型配置中的 API Key") from e
                if status == 429:
                    if attempt < self.max_retries - 1:
                        retry_after = e.response.headers.get("Retry-After") if e.response else None
                        try:
                            # Retry-After 允许是 HTTP-date 而非秒数，此时退回指数退避
                            delay = min(float(retry_after), 60)
                        except (TypeError, ValueError):
                            delay = 2 ** attempt
                        await asyncio.sleep(delay)
                        continue
                    raise ValueError("API 请求频率超限，已重试多次仍失败") from e
                if "Cloudflare" in body or "Attention Required" in body:
                    raise ValueError(
                        f"API 请求被 Cloudflare 拦截（{self.api_base}），"
                        "请联系 API 提供商将您的 IP 加入白名单"
                    ) from e
                if status >= 500 or status == 408:
                    if attempt < self.max_retries - 1:
                        await self._exponential_backoff(attempt)
                        continue
                    logger.error(f"LLM request failed after {self.max_retries} attempts: {body}")
                    raise ValueError(
                        f"AI 服务暂时不可用（HTTP {status}），请稍后重试"
                    ) from e
                else:
                    raise ValueError(f"AI 请求失败（HTTP {status}），请检查请求参数") from e

            except (httpx.TimeoutException, asyncio.TimeoutError) as e:
                # D5/D37/D66：超时消息使用实际 self.timeout 值
                logger.warning(
                    f"LLM timeout (attempt {attempt+1}/{self.max_retries}): {e}"
                )
                last_error = e
                if attempt < self.max_retries - 1:
                    await self._exponential_backoff(attempt)
                    continue
                raise ValueError(
                    f"AI 请求超时（已等待 {self.timeout} 秒），模型响应时间过长，"
                    "建议联系 API 提供商或降低请求复杂度"
                ) from e

            except httpx.ConnectError as e:
                logger.error(f"LLM connection error (api_base={self.api_base}): {e}")
                last_error = e
                if attempt < self.max_retries - 1:
                    await self._exponential_backoff(attempt)
                    continue
                raise ValueError(
                    f"无法连接到 LLM 服务（{self.api_base}），请检查网络和地址配置"
                ) from e

            except httpx.RequestError as e:
                logger.error(f"LLM request error: {e}")
                last_error = e
                if attempt < self.max_retries - 1:
                    await self._exponential_backoff(attempt)
                    continue
                raise ValueError(f"AI 请求失败：{e}") from e

            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"LLM response parse error: {e}")
                raise ValueError(
                    f"AI 服务返回了无效响应，请检查模型名称（当前: {self.model}）是否正确"
                ) from e

            except Exception as e:
                logger.error(f"LLM chat failed (model={self.model}): {e}", exc_info=True)
                last_error = e
                if attempt < self.max_retries - 1:
                    await self._exponential_backoff(attempt)
                    continue
                raise ValueError("AI 调用失败，请查看日志获取详细信息") from e

        raise last_error or RuntimeError("LLM 调用失败（未知错误）")

    async def _exponential_backoff(self, attempt: int, base_delay: float = 1.0):
        """指数退避等待 (attempt 从0开始)"""
        delay = base_delay * (2 ** attempt)
        await asyncio.sleep(delay)

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

        url = self._api_url
        headers = self._build_headers()
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 10,
        }
        try:
            client = HttpClientManager.get_llm_client()
            resp = await client.post(url, headers=headers, json=payload, timeout=10.0)
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"LLM health check failed: {e}")
            return False
