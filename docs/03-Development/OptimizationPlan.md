# 优化方案：liteLLM 重构 + 代码质量治理

> 状态：**已完成**（O1-O16 全部落地，2026-08）
> 日期：2026-08
> 说明：本文基于**当前代码实际状态**编写（docs 下 PRD/TAD 等历史文档存在过时问题，仅作参考）。各优化项实施摘要见下表，验证方式见 `docs/03-Development/Testing.md` 与根目录 `README.md`。

---

## 1. 背景与现状

系统为"小说 → AI 漫画（Webtoon）"生产线，FastAPI + PostgreSQL 后端、React + TS 前端。经全量代码审查，当前主要问题：

| 类别 | 问题摘要 |
|------|---------|
| 安全 | Token 黑名单用内置 `hash()`（进程内随机加盐，重启失效）；API Key 明文落库且 PUT 响应回显明文；登录无速率限制；Refresh Token 无撤销检测 |
| LLM 通信 | 自研 SSE 流式适配器（`llm_adapter.py`），重试/超时/并发/日志全部手写，绑定 OpenAI 兼容协议，难以切换 DeepSeek/通义/Anthropic 等提供商 |
| 死代码 | `infra/agents/` 8 个 Agent 零调用；`modules/task/service.py` 零引用；Dashboard 多个统计恒为 0 |
| 前端类型 | axios 拦截器与 TS 泛型脱节，52 个 tsc 错误长期存在（`npm run build` 实为失败态） |
| 数据 | 数据库表与模型脱节；"每项目一小说/一世界观"仅服务层校验；PostgreSQL 强绑定（partial index、JSONB 路径查询），SQLite 开发备选实际不可用 |
| 性能 | Dashboard 每次请求 5 项目 × 15+ 条阶段查询 SQL，无跨请求缓存；前端大列表无虚拟滚动/懒加载 |
| 工程 | 零测试；git 仅 3 个"备份"提交；`character/service.py` 硬编码绝对路径写调试文件；任务类型字符串散落无常量 |

---

## 2. 目标与原则

- **目标**：消除安全风险；用 liteLLM 统一并简化 LLM 接入（一次实现，多提供商可切换）；清理死代码与类型错误；补上测试与工程规范；优化关键性能路径。
- **原则**：
  1. **接口不变优先**：改造 LLM 适配器时保持 `LLMAdapter.chat(messages, temperature, max_tokens) -> ChatResult` 接口不变，调用方零改动，迁移风险最小。
  2. **小步提交**：每个优化项独立提交，可单独验证、可回退。
  3. **以当前代码为准**：不依赖过时 PRD/TAD，改前先读当前实现。
  4. **安全优先**：P0 安全项最先落地。

---

## 3. 优化项总览

> ✅ = 已实施；实施明细与验证命令见对应小节与根目录 README。

| # | 优先级 | 类别 | 优化项 | 工作量 | 状态 |
|---|--------|------|--------|--------|------|
| O1 | P0 | 安全 | Token 黑名单改 `hashlib.sha256` + 清理机制 | 小 | ✅ |
| O2 | P0 | 安全 | API Key 加密存储（AES-GCM）+ 响应打码 | 中 | ✅ |
| O3 | P0 | 安全 | 登录/通用接口速率限制 | 中 | ✅ |
| O4 | P0 | 安全 | Refresh Token 撤销/重用检测 | 小 | ✅ |
| O5 | P0 | LLM | **liteLLM 替换 LLM 通信模块**（详见 §5） | 大 | ✅ |
| O6 | P1 | 前端 | axios 拦截器类型修正，消灭 ~30 个 tsc 错误 | 中 | ✅ |
| O7 | P1 | 前端 | 清理未使用 import/变量，tsc 归零 + 引入 ESLint | 中 | ✅ |
| O8 | P1 | 测试 | 搭建 pytest 骨架，覆盖核心逻辑（LLM JSON 解析、任务状态机、生产进度计算） | 大 | ✅ |
| O9 | P1 | 工程 | 修复硬编码绝对路径（character service 调试文件） | 小 | ✅ |
| O10 | P2 | 清理 | 删除死代码：infra/agents/、modules/task/service.py、Dashboard 恒 0 统计 | 小 | ✅ |
| O11 | P2 | 重构 | 任务类型字符串统一为常量（后端枚举 + 前端共享） | 中 | ✅ |
| O12 | P2 | 数据 | 服务层校验补数据库约束（小说/世界观唯一性，PostgreSQL partial unique index） | 小 | ✅ |
| O13 | P2 | 业务 | 小说删除/替换入口（每项目一本的配套能力） | 中 | ✅ |
| O14 | P3 | 性能 | Dashboard 生产进度结果缓存（30s TTL）+ `_get_production_stages` 查询合并 | 中 | ✅ |
| O15 | P3 | 性能 | 前端图片懒加载（LazyImage 组件）；虚拟滚动留待数据量增大后接入 | 中 | ✅ |
| O16 | P3 | 工程 | 规范 git 提交节奏、补 README/.env.example/.gitattributes | 小 | ✅ |

---

## 4. 详细方案（按优先级）

### 4.1 O1：Token 黑名单哈希修复（P0）

**现状**：`backend/app/core/security.py` 用 `str(hash(token))` 作黑名单 key。Python 内置 `hash()` 对 str 使用进程内随机种子（PYTHONHASHSEED），**服务重启后黑名单全部失效**，已登出的 token 重新可用；且非密码学哈希。

**方案**：
```python
import hashlib
def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
```
替换 `_is_token_blacklisted` / `revoke_token` 中的 `str(hash(token))`。
同时将 `_token_blacklist` 的 TTL 判断统一用 `time.monotonic()`（现状已如此，保留）。

**验证**：登出后立即用旧 access token 调用受保护接口返回 401；重启进程后再调用仍返回 401（本次修复的关键点）。

### 4.2 O2：API Key 加密存储（P0）

**现状**：`routers/system.py` 的 `update_llm_config` / `update_image_gen_config` 将 `api_key` 明文写入 `LLMConfig` / `ImageGenConfig` 表；PUT 响应直接返回含明文 key 的 `_llm_config`。

**方案**：
1. 新增 `app/core/crypto.py`：`encrypt_secret(plain) -> str`、`decrypt_secret(cipher) -> str`，使用 `cryptography` 库 AES-256-GCM（requirements 已有 `cryptography`），密钥来自 `settings.APP_SECRET_KEY`（派生 sha256 得 32 字节）。
2. 写入路径：`update_llm_config` 落库前 `row.api_key = encrypt_secret(config.api_key)`。
3. 读取路径：`_load_llm_config_from_db` 解密后放入内存 `_llm_config`；`get_llm_config` 的响应继续打码（现状已打码）。
4. PUT 响应不再回显明文：返回 `{...config, api_key: masked}`。
5. 兼容：检测到旧明文数据时（无法解密）按原样使用并打 warning，避免升级中断。

**验证**：更新配置后直接查库为密文；调 `/models/llm` 返回打码；实际调用 LLM 成功（内存中为明文可用）。

### 4.3 O3：速率限制（P0）

**现状**：登录接口无任何限流（TAD 声称有，实际没有）。

**方案**：引入轻量进程内令牌桶（不引入 Redis 依赖）：
- `app/infra/rate_limit.py`：`RateLimiter(max_requests, window_seconds)`，按 IP 或 username 记 key。
- 登录：每用户名+IP 5 次/分钟；通用接口：120 次/分钟（可用 FastAPI 中间件）。
- 单机进程内即可；多 worker 部署时接受近似限制（或在方案备注中说明可换 Redis）。

**验证**：连续错误登录超过阈值返回 429；正常操作不受影响。

### 4.4 O4：Refresh Token 撤销（P0）

**现状**：`revoke_token` 只加入 access token；refresh token 登出后 7 天内仍可换取新 token。

**方案**：登录/刷新时生成 `token_id`（jti）写入 JWT payload；`User` 表或独立表记录"已撤销的 jti + 过期时间"；`/auth/refresh` 校验 jti 不在撤销列表。简单起见：登出时同时撤销 access 与 refresh（refresh 的 jti 记入同一黑名单结构，TTL=refresh 过期时间）。

**验证**：登出后立即用 refresh token 调 `/auth/refresh` 返回 401。

### 4.5 O6：前端 axios 类型修正（P1）

**现状**：`api/client.ts` 拦截器运行时返回 `response.data`（ApiResponse），但 TS 泛型仍是 `AxiosResponse<T>`，导致各 store `res.data?.items` 全部类型报错（约 30 个）。

**方案**（两选一，推荐 A）：
- **A**：封装 `apiClient` 为包装对象：`get<T>(url, cfg): Promise<T>`，内部 `axios.get` 后直接返回 `response.data`。全量替换 `apiClient.get/post/put/delete` 调用点（约 200 处，可用 codemod 半自动）。改完后 `res.data?.items` 变 `res?.items`，类型正确。
- **B**：保持调用形态，给 axios 实例覆写泛型签名（hack 型，风险高），不推荐。

**验证**：tsc 错误从 52 降到 20 以内；全站冒烟（登录→各页面）。

### 4.6 O7：tsc 归零 + ESLint（P1）

**现状**：约 10 个未使用 import/变量（generation/index.tsx 等）+ 类型错误。

**方案**：O6 完成后逐个清理未使用变量；`tsconfig` 保留 `noUnusedLocals` 等严格选项（逼迫干净代码）；引入 ESLint + prettier 配置；`npm run lint` 接入 CI 或 pre-commit。

**验证**：`npx tsc --noEmit` 输出 0 错误；`npm run build` 成功。

### 4.7 O8：测试骨架（P1）

**现状**：零测试。

**方案**（按风险从高到低覆盖）：
1. `tests/unit/test_llm_json_parse.py`：`parse_llm_json` 的 5 层 fallback 各分支（单引号、未转义换行、markdown 围栏、损坏 JSON）。
2. `tests/unit/test_task_progress.py`：TaskProgressTracker 状态机（queued→running→completed/failed、_flush 状态不匹配跳过）。
3. `tests/unit/test_production_stages.py`：`_get_production_stages` 8 工序判定逻辑（用内存 SQLite 或 mock session——注意模型是 PG 专属，SQLite 需去掉 PG 依赖或用 `aiosqlite` + 兼容处理；若不可行则用 mock）。
4. `tests/unit/test_rate_limit.py`、`test_crypto.py`。
5. 集成冒烟：`tests/integration/` 用真实 PG（测试库）+ httpx ASGI 客户端跑主链路（登录→建项目→上传小说→脚本→分镜→排版→提示词→生图 mock）。

**验证**：`pytest` 全部通过；关键回归点有保护。

### 4.8 O9：硬编码路径（P1）

**现状**：`modules/character/service.py:286` 写死 `E:\VScode\Python\Comic Generation Engine\debug_llm_response_...`。

**方案**：改为 `settings.STORAGE_LOCAL_PATH` 下 `logs/llm_debug/` 或 `backend/logs/`（与 layout service 的 `_dump_layout_llm_failure` 一致）；删除根目录 5 个残留调试文件。

### 4.9 O10：死代码清理（P2）

**清理清单**（先 grep 确认零引用再删）：
- `backend/app/infra/agents/` 8 个 agent 文件（`text_cleaner/story_analyzer/semantic_splitter/storyboard_planner/camera_planner/layout_planner/bubble_planner/prompt_generator`）及 `__init__.py` 导出；`base_agent.py` 保留与否取决于是否有测试引用。
- `backend/app/modules/task/service.py`（TaskService 无引用；tasks 路由用 task_repo + TaskProgressTracker）。
- Dashboard：`total_generated_images` / `pending_review_images` 恒 0——**建议不删字段**，改为接入真实统计（O16 可选）或保留 0 并加注释。

### 4.10 O11：任务类型常量（P2）

**现状**：21 种 `task_type` 字符串散落在各 router、`task_dispatcher` 注册装饰器、前端 `tasks/components/types.ts`。

**方案**：
- 后端：`app/core/task_types.py` 定义枚举/常量类（`TASK_SCRIPT = "generate_script"` 等）+ `TASK_LABELS_CN` 中文映射；各 `@register_task_runner("...")` 改用常量。
- 前端：`src/constants/taskTypes.ts` 导出同名字典；`types.ts` 的 `TYPE_LABELS`/`TYPE_FILTERS` 从常量生成。
- 消除"改了任务名但漏改前端/注册表"的隐患。

### 4.11 O12：唯一性数据库约束（P2）

**现状**：小说"每项目一本"、世界观"每项目一个"只在服务层 `upload_novel` / `ai_create_world` 校验。

**方案**：Alembic 迁移添加 PostgreSQL 部分唯一索引：
```sql
CREATE UNIQUE INDEX uq_novels_one_per_project ON novels(project_id) WHERE (deleted_at IS NULL);  -- 若需软删
CREATE UNIQUE INDEX uq_worlds_one_per_project ON world_buildings(project_id);
```
（现有表如已有多本/多个的数据，先迁移清理或先加服务层+手工清数据再加索引。）

### 4.12 O13：小说替换入口（P2）

**现状**：每项目仅一本，但无删除/替换能力，导入错误被"锁死"。

**方案**：`novels/index.tsx` 增加"删除小说"（后端 `DELETE /novels/{id}` 级联章节/段落/脚本/分镜/排版，参考现有 `delete_all_script_and_downstream` 的清理顺序）；或"替换"（上传时若已有小说则先删后建，需二次确认弹窗）。

### 4.13 O14：Dashboard 缓存与查询合并（P3）

**现状**：`get_dashboard_stats` 对 5 个项目逐个跑 `_get_production_stages`（每项目 15+ 条 SQL），无跨请求缓存。

**方案**：
1. 进程内结果缓存：`{project_id: (stages, timestamp)}`，TTL 30-60s（参考 `prompt_loader` 的缓存模式）。
2. `_get_production_stages` 查询合并：四类资产（SceneAsset/Prop/Building/Outfit）用 `UNION ALL` 一次统计总数与有图数；角色图用一条 LEFT JOIN + COUNT(DISTINCT)；各章节存在性可合并为一条 UNION。
3. 预期：单项目阶段查询从 15+ 条降到 5 条以内。

### 4.14 O15：前端懒加载/虚拟滚动（P3）

- 图片统一 `loading="lazy"`（antd Image / img）或 IntersectionObserver 组件。
- 生图中心布局列表、任务中心列表在数据量增大后接入虚拟滚动（`@tanstack/react-virtual`）或分页。

### 4.15 O16：工程规范（P3）

- git 提交规范（feat/fix/refactor/chore + 描述），为当前 working tree 的 50+ 改动做一次基准提交。
- 用本文替换过时的 TAD/PRD 中与现状不符的描述（或在新文档标注"以代码为准"）。
- README：快速启动、环境变量清单（含导出目录、CORS、代理等实际配置）。

---

## 5. liteLLM 替换 LLM 通信模块（O5，核心）

### 5.1 目标

用 [liteLLM](https://github.com/BerriAI/litellm) 统一 LLM 接入，替换自研 `llm_adapter.py` 的 SSE 流式/重试/超时实现，获得：
- **多提供商支持**：同一接口对接 OpenAI / DeepSeek / 通义 / Anthropic / Gemini / OpenRouter 等（模型名前缀或 `custom_llm_provider`）。
- **内置重试与超时**：`num_retries`、`timeout` 由 liteLLM 统一处理，删除自研退避代码。
- **调用日志钩子**：`litellm.success_callback` / `failure_callback` 对接现有 `model_call_logs`。
- **后续扩展**：Prompt 缓存、预算控制、异常分类等现成能力。

**边界**：生图（`grsai_api_adapter.py`，Flow API 桥接，含参考图 base64 等自定义逻辑）**不属于 liteLLM 范畴，本次不动**。

### 5.2 设计：保持接口不变，替换内部实现

**关键决策**：不新增适配器类、不改任何调用方。**改造 `llm_adapter.py` 内部**，保持对外接口：

```python
class LLMAdapter(BaseLLMAdapter):
    async def chat(self, messages, temperature=0.7, max_tokens=None) -> ChatResult
```
所有调用方（script/storyboard/layout/prompt/world/character service、system.py 测试连接）零改动。

**新内部实现**：

```python
import litellm
from litellm import completion

class LLMAdapter(BaseLLMAdapter):
    def __init__(self, api_base=None, api_key=None, model=None, timeout=3600, max_retries=3):
        # 沿用现有优先级：运行时配置 > 显式参数 > settings
        # litellm 侧配置：
        #   litellm.timeout = timeout
        #   litellm.retry_policy / completion(num_retries=max_retries)

    async def chat(self, messages, temperature=0.7, max_tokens=None) -> ChatResult:
        async with _llm_semaphore:                      # 保留全局并发控制
            resp = await asyncio.to_thread(              # litellm.completion 为同步阻塞 API
                completion,
                model=self.model,                        # 如 "deepseek/deepseek-chat" 或 "openai/gpt-4o"
                messages=[{"role": m.role, "content": m.content} for m in messages],
                api_base=self.api_base,                  # 自定义 OpenAI 兼容端点
                api_key=self.api_key,
                temperature=temperature,
                max_tokens=max_tokens or settings.LLM_MAX_TOKENS,
                stream=False,                            # 见 5.3 流式讨论
                num_retries=self.max_retries,
                timeout=self.timeout,
            )
        # 记录 model_call_logs（沿用现有 _append_log）
        # 返回 ChatResult(content=resp.choices[0].message.content, model=resp.model, usage=...)
```

**要点**：
- `litellm.completion` 是同步 API，用 `asyncio.to_thread` 包住避免阻塞事件循环（与项目"AI 调用不占事件循环"的既有约定一致；也可考虑 litellm 的 `acompletion`——若版本支持则直接用 async，更优）。
- 保留 `_llm_semaphore = asyncio.Semaphore(5)` 全局并发上限（现有 D4 约束）。
- `health_check`：改用 `completion(model=..., messages=[{"role":"user","content":"ping"}], max_tokens=10)` 的成功与否判断。
- 错误分类：liteLLM 抛 `litellm.exceptions.*`（`AuthenticationError`/`RateLimitError`/`Timeout`/`APIConnectionError`），在 adapter 内统一映射为现有业务错误消息（保持前端展示文案不变：401→"API Key 认证失败"、429→"请求频率超限"、超时→"AI 请求超时"等）。

### 5.3 流式 vs 非流式

| 方案 | 说明 | 取舍 |
|------|------|------|
| **A. stream=False（推荐）** | liteLLM 内部完成聚合，返回完整 content | 实现最简；行为与现状等价（现状也是完整聚合后才返回）；大响应无中途进度（对现有调用方无感知） |
| B. stream=True | `resp = completion(..., stream=True)` 返回迭代器，`for chunk in resp` 聚合 | 保留流式语义，但需自写聚合循环（与现状类似），收益有限 |

默认 A，若后续需要"流式透传到前端"再升级 B。

### 5.4 模型名与提供商映射

- 现有配置 `LLM_MODEL`（如 `mock-model`）与 api_base 指向 OpenAI 兼容端点（如 `http://127.0.0.1:5000`）。
- liteLLM 规则：`api_base` 显式传入时，模型名通常加 `openai/` 前缀走 OpenAI 兼容协议（`model="openai/" + settings.LLM_MODEL`）。若配置的是 `deepseek/deepseek-chat` 这类带前缀的名字，liteLLM 直接识别提供商。
- 建议：adapter 内做归一化——若 model 不含 `/` 且 api_base 自定义，则自动加 `openai/` 前缀；否则原样透传。**保证现有 mock/自定义端点配置零改动可用**。

### 5.5 依赖与安装

```bash
pip install "litellm>=1.40"
```
liteLLM 依赖较多（httpx、openai 等），**不与现有依赖冲突**（现有 httpx==0.27 兼容）。更新 `requirements.txt` 并锁版本。注意：liteLLM 引入后，若现有 `llm_adapter.py` 全部逻辑被替换，可删除自研 SSE 解析代码（`_read_sse_stream_async`），减少维护面。

### 5.6 迁移步骤（可回退）

1. **步骤 1**：安装 litellm；新增 `litellm_adapter.py`（内部用 litellm，接口同 LLMAdapter），临时并存；用一段脚本对比新旧 adapter 对同一请求的输出与耗时。
2. **步骤 2**：`system.py` 的模型测试连接改用新 adapter（或配置开关 `LLM_BACKEND=litellm|legacy` 灰度）。
3. **步骤 3**：切换默认实现——将 `llm_adapter.py` 内部改为 litellm（或让各调用方 import 指向新实现）；保留旧文件一个提交供回退。
4. **步骤 4**：验证全部 LLM 调用点（脚本/分镜/排版/提示词/参考图匹配/角色提取/世界观创建/资产生成提示词/模型测试）。
5. **步骤 5**：跑回归（O8 测试）+ 删除旧 SSE 代码。

**风险与回退**：若 liteLLM 在特定端点（如本地 mock、特殊 SSE 行为）不兼容，保留旧 adapter 文件，切换 import 即可回退。

---

## 6. 实施路线图

### 阶段一：安全加固（O1-O4）——约 1-2 天
O1 → O2 → O4 → O3。全部是独立小改动，可逐个提交。

### 阶段二：LLM 层重构（O5）——约 2-3 天
按 §5.6 步骤 1-5 执行。**与阶段一独立，可并行**（不同文件）。

### 阶段三：前端类型与工程质量（O6、O7、O9）——约 2-3 天
O6（类型修正）→ O7（清理+ESLint）→ O9（路径修复）。O6 改动面最大，建议先做并立即跑冒烟。

### 阶段四：测试基建（O8）——约 2-3 天（可与阶段二并行）
先写 `parse_llm_json`、生产进度、任务状态机单测，再补集成冒烟。

### 阶段五：清理与重构（O10-O13）——约 2-3 天
O10 死代码 → O11 任务类型常量 → O13 小说替换 → O12 数据库约束（需先处理存量数据）。

### 阶段六：性能与收尾（O14-O16）——约 2-3 天
O14 缓存与查询合并 → O15 懒加载 → O16 git 规范与文档。

**总计约 2 周（单人）**，每阶段可独立交付、独立验证。

---

## 7. 验证策略

- 每项：tsc/py_compile 通过 + 对应冒烟路径。
- 阶段二：新旧 adapter 输出对比脚本（响应内容一致性、耗时）。
- 阶段四起：`pytest` 全绿作为合并门禁。
- 全量回归清单：登录 → 建项目 → 上传小说 → 一键提取角色 → AI 建世界观 → 脚本/分镜/排版 → 生成提示词 → 匹配参考图 → 批量生图 → 导出；任务中心可查进度/重试；Dashboard 与项目详情页进度一致。

---

## 8. 风险登记

| 风险 | 影响 | 缓解 |
|------|------|------|
| liteLLM 与自定义 mock 端点/特殊 SSE 不兼容 | 阶段二阻塞 | 新旧 adapter 并存 + 配置开关灰度；失败回退旧实现 |
| O2 加密改动后旧明文数据不可用 | 配置读取失败 | 解密失败回退明文 + warning；迁移脚本先行 |
| O12 加唯一索引遇存量脏数据 | 迁移失败 | 先清理/去重再建索引，迁移脚本含数据预检 |
| O6 类型修正改动面大引发回归 | 全站冒烟受阻 | 分模块替换 + 每模块冒烟；codemod 后 diff 审查 |
| O8 测试基建成本高于预期 | 阶段四延期 | 先覆盖最高风险 3 项，其余按需扩展 |
