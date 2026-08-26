"""liteLLM 全局 HTTP client 初始化（统一 User-Agent）。

背景：部分 OpenAI 兼容服务商（如 gemai.cc / god2017.top 所在的 Cloudflare zone）
的 WAF 会拦截 `User-Agent: OpenAI/Python x.y.z` 的请求（返回 403 Cloudflare
拦截页），而中性/浏览器 UA 可以正常通过。openai SDK 的 UA 无法通过
extra_headers / default_headers 覆盖，因此通过注入自定义 httpx client 的
request hook 强制改写 UA。

litellm.aclient_session 是全局共享的异步 client（litellm 对 openai 兼容
provider 使用它），LLM 与生图适配器均走同一 client，一处设置全局生效。
"""

import httpx
import litellm

# 主流浏览器 UA：兼容性最好，避免被各类 WAF 按工具 UA 拦截
_API_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


async def _rewrite_user_agent(request: httpx.Request) -> None:
    """改写 User-Agent。

    httpx 0.28+ 的 request hook 必须是 async 函数（内部 await hook(request)），
    同步函数会被 await 导致 TypeError；且不能返回 Request（会被当作 Response）。
    """
    request.headers["User-Agent"] = _API_USER_AGENT


def ensure_litellm_http_client() -> httpx.AsyncClient:
    """确保 litellm.aclient_session 已设置为带 UA 重写的全局 client。"""
    if litellm.aclient_session is None:
        litellm.aclient_session = httpx.AsyncClient(
            timeout=httpx.Timeout(600.0),
            event_hooks={"request": [_rewrite_user_agent]},
        )
    return litellm.aclient_session
