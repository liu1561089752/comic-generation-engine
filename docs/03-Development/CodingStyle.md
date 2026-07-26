# AI Webtoon Factory — 编码规范（Coding Style Guide）

> 版本：v1.0  
> 最后更新：2026-06-27  
> 状态：草案  
> 适用范围：后端（Python / FastAPI）、前端（TypeScript / React）

---

## 1. Python 编码规范

### 1.1 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 包/目录 | `snake_case` | `story_analyzer/` |
| 模块文件 | `snake_case` | `text_cleaner.py` |
| 类 | `PascalCase` | `StoryAnalyzerAgent` |
| 函数/方法 | `snake_case` | `process_scene()` |
| 变量 | `snake_case` | `panel_list` |
| 常量 | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| 私有成员 | `_` 前缀 | `_validate_input()` |
| 类型变量 | `PascalCase` | `T` |
| 枚举成员 | `UPPER_SNAKE_CASE` | `STATUS_PENDING` |

#### 1.1.1 命名原则

- **自文档化**：名称应能清晰表达用途，无需额外注释。`get_panels_by_scene_id` 优于 `get_data`。
- **避免缩写**：除非是业界通用缩写（如 `HTTP`、`DB`、`JSON`），否则使用完整单词。
- **布尔变量/函数**：使用 `is_`、`has_`、`should_` 前缀，如 `is_enabled`、`has_dialog`。

### 1.2 项目目录规范

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 应用入口
│   ├── config.py               # 配置加载（Pydantic Settings）
│   ├── routers/                # API 路由 — 只做参数校验和路由分发
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── novels.py
│   │   │   ├── characters.py
│   │   │   ├── scenes.py
│   │   │   ├── panels.py
│   │   │   ├── images.py
│   │   │   ├── projects.py
│   │   │   ├── export.py
│   │   │   └── health.py
│   ├── services/               # 服务层 — 业务逻辑编排
│   │   ├── __init__.py
│   │   ├── novel_service.py
│   │   ├── character_service.py
│   │   ├── scene_service.py
│   │   ├── panel_service.py
│   │   └── export_service.py
│   ├── agents/                 # Agent 层 — AI 处理逻辑
│   │   ├── __init__.py
│   │   ├── base_agent.py       # 基础 Agent 抽象类
│   │   ├── text_clean_agent.py
│   │   ├── character_extract_agent.py
│   │   ├── scene_split_agent.py
│   │   ├── panel_layout_agent.py
│   │   ├── prompt_gen_agent.py
│   │   └── qc_agent.py
│   ├── adapters/               # 适配层 — 外部服务接口
│   │   ├── __init__.py
│   │   ├── llm_adapter.py      # LLM 调用封装
│   │   ├── image_gen_adapter.py # 生图 API 封装
│   │   └── storage_adapter.py   # 对象存储封装
│   ├── models/                 # ORM 模型 — 数据库映射
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── novel.py
│   │   ├── character.py
│   │   ├── scene.py
│   │   ├── panel.py
│   │   └── image.py
│   ├── repositories/           # 数据访问层 — 数据库查询
│   │   ├── __init__.py
│   │   ├── base_repository.py
│   │   ├── novel_repository.py
│   │   ├── character_repository.py
│   │   ├── scene_repository.py
│   │   └── panel_repository.py
│   ├── schemas/                # Pydantic 模型 — API 请求/响应
│   │   ├── __init__.py
│   │   ├── common.py           # 分页、排序等通用 Schema
│   │   ├── novel_schema.py
│   │   ├── character_schema.py
│   │   ├── scene_schema.py
│   │   └── panel_schema.py
│   ├── tasks/                  # Celery 任务 — 异步任务
│   │   ├── __init__.py
│   │   ├── celery_app.py
│   │   ├── generation_tasks.py
│   │   └── export_tasks.py
│   ├── middleware/             # 中间件
│   │   ├── __init__.py
│   │   ├── cors.py
│   │   └── exception_handler.py
│   └── utils/                  # 工具函数
│       ├── __init__.py
│       ├── logger.py
│       ├── security.py         # JWT、密码加密
│       └── file_utils.py       # 文件处理工具
├── tests/
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── alembic/
├── alembic.ini
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
├── .env.example
├── Dockerfile
└── pyproject.toml
```

#### 1.2.1 各层职责

| 层级 | 职责 | 依赖 | 禁止行为 |
|------|------|------|----------|
| `routers/` | 参数校验、路由分发、调用 Service | `schemas/`、`services/` | 不包含业务逻辑，不直接操作数据库 |
| `services/` | 业务编排、调用 Repository 和 Agent | `repositories/`、`agents/`、`schemas/` | 不直接操作数据库（通过 Repository） |
| `agents/` | AI 交互逻辑（构造 Prompt、解析响应） | `adapters/` | 不调用数据库，不暴露 HTTP 端点 |
| `adapters/` | 外部服务接口封装 | 第三方 SDK | 不包含业务逻辑 |
| `models/` | ORM 表映射 | SQLAlchemy | 不包含业务逻辑 |
| `repositories/` | 数据库查询封装 | `models/` | 不包含业务逻辑，不调用 Service/Agent |
| `schemas/` | 请求/响应数据定义 | Pydantic | 不包含业务逻辑 |

### 1.3 数据层规范（DTO / Service / Repository 模式）

#### 1.3.1 DTO（Data Transfer Object）

使用 Pydantic 定义 API 的请求和响应结构，与 ORM 模型分离。

```python
# ✅ 正确：独立的 Pydantic Schema
class NovelCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    author: str | None = Field(None, max_length=100)
    content: str = Field(..., min_length=1)

class NovelResponse(BaseModel):
    id: int
    title: str
    author: str | None
    status: NovelStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

```python
# ❌ 错误：直接使用 ORM 模型作为响应
@app.get("/novels/{id}")
async def get_novel(id: int) -> Novel:  # 应返回 Pydantic Schema
    ...
```

#### 1.3.2 Repository 层

封装数据库查询，每个方法对应一个数据库操作。

```python
# ✅ 正确
class NovelRepository(BaseRepository[Novel]):
    def get_by_id(self, novel_id: int) -> Novel | None:
        return self.session.get(Novel, novel_id)

    def get_by_status(self, status: NovelStatus, skip: int = 0, limit: int = 20) -> list[Novel]:
        stmt = select(Novel).where(Novel.status == status).offset(skip).limit(limit)
        return list(self.session.scalars(stmt).all())
```

#### 1.3.3 Service 层

编排业务逻辑，不直接操作数据库。

```python
# ✅ 正确
class NovelService:
    def __init__(self, repo: NovelRepository, agent: TextCleanAgent):
        self._repo = repo
        self._agent = agent

    async def create_novel(self, data: NovelCreate) -> Novel:
        # 1. 调用 Agent 处理文本
        cleaned_content = await self._agent.clean(data.content)
        # 2. 调用 Repository 持久化
        novel = Novel(title=data.title, content=cleaned_content)
        return await self._repo.save(novel)
```

```python
# ❌ 错误：Service 层直接操作数据库
class NovelService:
    async def create_novel(self, data: NovelCreate) -> Novel:
        novel = Novel(title=data.title, content=data.content)
        await self._db.execute(add(novel))  # 应通过 Repository
        ...
```

### 1.4 异常处理规范

#### 1.4.1 自定义异常层次

```python
class AppError(Exception):
    """应用基础异常"""
    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)

class NotFoundError(AppError):
    def __init__(self, resource: str, resource_id: int | str):
        super().__init__(
            message=f"{resource} not found: {resource_id}",
            code="NOT_FOUND",
            status_code=404
        )

class ValidationError(AppError):
    def __init__(self, message: str, detail: dict | None = None):
        super().__init__(message=message, code="VALIDATION_ERROR", status_code=422)
        self.detail = detail

class AIServiceError(AppError):
    def __init__(self, message: str, provider: str):
        super().__init__(
            message=f"AI service error from {provider}: {message}",
            code="AI_SERVICE_ERROR",
            status_code=502
        )
```

| 异常类 | 用途 | HTTP 状态码 |
|--------|------|-------------|
| `AppError` | 所有应用异常的基类 | 500 |
| `NotFoundError` | 资源不存在 | 404 |
| `ValidationError` | 业务校验失败 | 422 |
| `AIServiceError` | AI 服务调用失败 | 502 |
| `AuthError` | 认证/授权失败 | 401/403 |

#### 1.4.2 统一异常处理中间件

```python
# app/middleware/exception_handler.py
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        }
    )

@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
            }
        }
    )
```

#### 1.4.3 异常处理规则

- **禁止使用 `except: pass`**：即使确定要忽略异常，也需明确指定异常类型并记录日志。
- **禁止吞异常**：捕获异常后必须记录日志或重新抛出。仅在确定异常无害且不影响后续流程时才可忽略。
- **分层处理**：Agent 层的异常应在 Service 层捕获并转换为业务异常，不要将 AI 原始错误直接暴露给 API 调用方。
- **日志记录**：捕获异常时记录 `logger.error(msg, exc_info=True)`，保留完整堆栈。

### 1.5 类型注解规范

```python
# ✅ 正确：所有函数参数和返回值都有类型注解
def process_scene(scene: Scene, options: SceneOptions | None = None) -> list[Panel]:
    ...

# ✅ 正确：使用 | None 而非 Optional（Python 3.10+）
def get_character(character_id: int) -> Character | None:
    ...

# ❌ 错误：无类型注解
def process_scene(scene, options=None):
    ...

# ❌ 错误：Python 3.10+ 项目中仍使用 typing.Optional
from typing import Optional
def get_character(character_id: int) -> Optional[Character]:
    ...
```

### 1.6 导入规范

```python
# 标准库
import json
import os
from datetime import datetime
from pathlib import Path

# 第三方库
import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

# 本地库
from app.models.novel import Novel
from app.schemas.novel_schema import NovelCreate, NovelResponse
from app.services.novel_service import NovelService
```

规则：

1. **三组顺序**：标准库 → 第三方库 → 本地库，组之间用空行分隔。
2. **禁止使用 `from module import *`**：明确导入所需内容。
3. **禁止相对导入**：使用绝对导入（`from app.models.novel import Novel`），可读性和可维护性更好。
4. **按字母序排列**：每组内按字母序排列，便于快速查找依赖。

### 1.7 异步编程规范

```python
# ✅ 正确：I/O 操作用 async/await
@app.get("/novels/{novel_id}")
async def get_novel(novel_id: int, repo: NovelRepository = Depends()):
    novel = await repo.get_by_id(novel_id)
    if novel is None:
        raise NotFoundError("Novel", novel_id)
    return NovelResponse.model_validate(novel)

# ✅ 正确：CPU 密集型操作使用 run_in_executor
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

async def analyze_text(text: str) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _heavy_text_analysis, text)

# ✅ 正确：数据库操作使用异步 session
async def get_panels(scene_id: int, session: AsyncSession) -> list[Panel]:
    stmt = select(Panel).where(Panel.scene_id == scene_id).order_by(Panel.order)
    result = await session.execute(stmt)
    return list(result.scalars().all())
```

规则：

1. **I/O 操作必须用 async/await**：包括 HTTP 请求、数据库查询、文件读写等。
2. **避免 `asyncio.run()` 在异步函数中调用**：在 FastAPI 应用中，无需手动创建事件循环。
3. **同步 Agent 包装**：如果 Agent 内部使用同步 SDK（如某些 LLM SDK），使用 `run_in_executor` 包装，避免阻塞事件循环。

### 1.8 配置管理规范

使用 Pydantic Settings 管理配置，替代传统 `os.getenv`。

```python
# ✅ 正确：Pydantic Settings
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 应用
    APP_NAME: str = "AI Webtoon Factory"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./dev.db"
    DATABASE_POOL_SIZE: int = 10

    # AI 服务
    LLM_API_KEY: str
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o"
    LLM_TIMEOUT: int = 60

    # 存储
    STORAGE_BACKEND: str = "local"  # local | s3
    STORAGE_PATH: str = "./uploads"
    S3_BUCKET: str = ""
    S3_ENDPOINT: str = ""

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
```

```python
# ❌ 错误：散落的 os.getenv
import os
API_KEY = os.getenv("API_KEY")  # 无类型、无默认值、不可测试
```

### 1.9 Logger 使用规范

```python
import logging

logger = logging.getLogger(__name__)

# ✅ 正确：在 catch 块中使用 exc_info
try:
    result = await ai_service.generate(prompt)
except AIServiceError as e:
    logger.error("AI generation failed: %s", prompt_id, exc_info=True)
    raise

# ❌ 错误：手动格式化 + 不传递异常信息
logger.error(f"AI generation failed: {e}")  # 不使用 f-string 格式化日志消息
```

规则：

1. **使用 `logging.getLogger(__name__)`**：在每个模块中创建模块级 logger。
2. **延迟格式化**：使用 `%s` 占位符而非 f-string，避免格式化开销。
3. **传递异常**：使用 `exc_info=True` 记录完整堆栈。
4. **日志级别**：`DEBUG`（开发调试）、`INFO`（关键流程节点）、`WARNING`（可恢复问题）、`ERROR`（需人工介入）。

---

## 2. TypeScript 编码规范

### 2.1 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| React 组件 | `PascalCase` | `PanelPreview` |
| 组件文件 | `PascalCase` | `PanelPreview.tsx` |
| 非组件文件 | `camelCase` | `apiClient.ts` |
| 变量 | `camelCase` | `selectedPanel` |
| 常量 | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| 类型别名 | `PascalCase` | `PanelData` |
| 接口 | `PascalCase` | `PanelData` |
| Props 接口 | `ComponentName + Props` | `PanelPreviewProps` |
| 枚举 | `PascalCase` | `PanelStatus` |
| 枚举成员 | `PascalCase` | `PanelStatus.Completed` |
| 函数 | `camelCase` | `fetchPanels()` |
| 自定义 Hook | `use` 前缀 | `usePanelData()` |

### 2.2 项目目录规范

```
frontend/
├── src/
│   ├── main.tsx                 # 入口文件
│   ├── App.tsx                  # 根组件
│   ├── routes.tsx               # 路由配置
│   ├── api/                     # API 客户端
│   │   ├── client.ts            # Axios 实例
│   │   ├── novels.ts
│   │   ├── characters.ts
│   │   └── panels.ts
│   ├── components/              # 通用组件
│   │   ├── common/              # 按钮、输入框等基础组件
│   │   ├── layout/              # 布局组件（Header、Sidebar）
│   │   └── business/            # 业务组件（NovelCard、PanelPreview）
│   ├── pages/                   # 页面组件
│   │   ├── Dashboard/
│   │   ├── NovelManage/
│   │   ├── CharacterManage/
│   │   ├── SceneSplit/
│   │   ├── PanelLayout/
│   │   └── Export/
│   ├── hooks/                   # 自定义 Hooks
│   │   ├── useNovels.ts
│   │   └── useWebSocket.ts
│   ├── stores/                  # Zustand 状态
│   │   ├── novelStore.ts
│   │   └── panelStore.ts
│   ├── types/                   # TypeScript 类型定义
│   │   ├── novel.ts
│   │   ├── panel.ts
│   │   └── api.ts
│   ├── utils/                   # 工具函数
│   │   ├── format.ts
│   │   └── validators.ts
│   └── styles/                  # 样式
│       └── globals.css
├── public/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.js
└── postcss.config.js
```

### 2.3 React 规范

#### 2.3.1 组件定义

```tsx
// ✅ 正确：Function Component + Hooks
interface PanelPreviewProps {
  panelId: number;
  onLoad?: () => void;
}

const PanelPreview: React.FC<PanelPreviewProps> = ({ panelId, onLoad }) => {
  const { data, isLoading, error } = usePanelData(panelId);

  if (isLoading) return <Skeleton active />;
  if (error) return <Alert message="加载失败" type="error" />;

  return (
    <div className="relative">
      <Image src={data.imageUrl} alt={`Panel ${panelId}`} />
      <BubbleOverlay bubbles={data.bubbles} />
    </div>
  );
};

export default PanelPreview;
```

```tsx
// ❌ 错误：Class Component
class PanelPreview extends React.Component<PanelPreviewProps> {
  render() {
    return <div>...</div>;
  }
}
```

#### 2.3.2 Props 规范

```tsx
// ✅ 正确：使用 TypeScript 接口定义 Props
interface NovelCardProps {
  novel: NovelSummary;
  onClick?: (id: number) => void;
  className?: string;          // 允许外部样式覆盖
  style?: React.CSSProperties; // 允许外部样式覆盖
}
```

```tsx
// ❌ 错误：使用 any
interface NovelCardProps {
  novel: any;  // 应使用具体类型
  onClick: any; // 应使用 (id: number) => void
}
```

#### 2.3.3 useState 规范

```tsx
// ✅ 正确：使用具体类型
const [panels, setPanels] = useState<PanelData[]>([]);
const [status, setStatus] = useState<ApiStatus>(ApiStatus.Idle);

// ❌ 错误：使用 any
const [panels, setPanels] = useState<any>([]);
```

#### 2.3.4 useEffect 规范

```tsx
// ✅ 正确：明确依赖列表
useEffect(() => {
  fetchPanels(projectId).then(setPanels);
}, [projectId]); // 依赖项显式声明

// ❌ 错误：空依赖但有外部变量引用
useEffect(() => {
  fetchPanels(projectId).then(setPanels); // projectId 未在依赖中声明
}, []);
```

规则：

- **禁止缺少依赖检查**：ESLint `react-hooks/exhaustive-deps` 规则必须开启，禁止用 `// eslint-disable-next-line` 跳过。
- **条件逻辑放在 useEffect 内部**：不要条件式调用 Hook。

### 2.4 状态管理规范

使用 Zustand 管理全局状态，组件内部状态使用 `useState`。

```tsx
// ✅ 正确：Zustand Store
interface NovelStore {
  currentNovel: NovelDetail | null;
  novelList: NovelSummary[];
  isLoading: boolean;
  fetchNovels: () => Promise<void>;
  selectNovel: (id: number) => void;
}

const useNovelStore = create<NovelStore>((set, get) => ({
  currentNovel: null,
  novelList: [],
  isLoading: false,

  fetchNovels: async () => {
    set({ isLoading: true });
    try {
      const novels = await api.getNovels();
      set({ novelList: novels, isLoading: false });
    } catch (error) {
      set({ isLoading: false });
      message.error('加载小说列表失败');
    }
  },

  selectNovel: (id: number) => {
    const novel = get().novelList.find(n => n.id === id);
    set({ currentNovel: novel ?? null });
  },
}));
```

规范：

- **Store 按模块拆分**：`novelStore`、`panelStore`、`userStore` 等各自独立，避免单一巨大 Store。
- **只存储跨组件共享的状态**：仅父子组件传递的数据不需要 Store。
- **异步操作在 Store 中完成**：不要在组件中直接调用 API 然后 setState。

### 2.5 样式规范

```tsx
// ✅ 正确：Tailwind CSS 优先
<div className="flex items-center gap-2 p-4 bg-white rounded-lg shadow-sm">
  <span className="text-sm text-gray-500">{label}</span>
  <span className="font-medium">{value}</span>
</div>

// ✅ 正确：复杂样式提取为组件
const StatBadge: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="flex items-center gap-2 p-4 bg-white rounded-lg shadow-sm">
    <span className="text-sm text-gray-500">{label}</span>
    <span className="font-medium">{value}</span>
  </div>
);
```

```tsx
// ❌ 错误：内联样式（除非动态计算）
<div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
  ...
</div>
```

规则：

1. **Tailwind CSS 优先**：项目中 90% 以上的样式应使用 Tailwind 原子类。
2. **Token 引用**：颜色、间距、字体大小等引用设计系统 Token（通过 `tailwind.config.js` 中的 `theme.extend` 配置），禁止魔术值。
3. **复杂组件提取**：当一组 Tailwind 类重复出现 2 次以上时，提取为独立组件。
4. **覆盖 Ant Design 样式**：使用全局 CSS 变量或 ConfigProvider 主题，避免 `:global` 覆盖。

### 2.6 导入规范

```tsx
// React 核心
import React, { useState, useEffect, useCallback } from 'react';

// 第三方库
import { Button, Modal, message } from 'antd';
import { useNavigate } from 'react-router-dom';
import { create } from 'zustand';

// 本地模块
import { NovelCard } from '@/components/business/NovelCard';
import { useNovelStore } from '@/stores/novelStore';
import { fetchNovels } from '@/api/novels';
import type { NovelSummary } from '@/types/novel';
```

规则：

1. **三组顺序**：React 核心 → 第三方库 → 本地模块，组之间用空行分隔。
2. **路径别名**：使用 `@/` 映射到 `src/`，避免深层相对路径（如 `../../../components/...`）。
3. **Type-only 导入**：仅类型引用时使用 `import type` 语法。

### 2.7 错误处理规范

```tsx
// ✅ 正确：API 层统一错误处理
const apiClient = axios.create({ baseURL: import.meta.env.VITE_API_BASE });

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorResponse>) => {
    if (error.response?.status === 401) {
      // 未授权，跳转登录
      window.location.href = '/login';
      return Promise.reject(error);
    }
    message.error(error.response?.data?.error?.message ?? '网络错误');
    return Promise.reject(error);
  }
);

// ✅ 正确：组件内使用 try-catch
const handleSubmit = async () => {
  try {
    setSubmitting(true);
    await api.createNovel(data);
    message.success('创建成功');
    onSuccess?.();
  } catch (error) {
    // 错误已在拦截器中处理，这里仅恢复 UI 状态
  } finally {
    setSubmitting(false);
  }
};
```

---

## 3. 通用规范

### 3.1 注释规范

#### 3.1.1 文档注释

```python
# Python：仅对公开 API 写 docstring
def process_scene(scene: Scene, options: SceneOptions | None = None) -> list[Panel]:
    """将 Scene 拆分为 Panel 列表。

    根据场景文本和配置的拆分策略，将 Scene 自动拆分为 Panel。
    支持按段落、按对话、按描述三种拆分策略。

    Args:
        scene: 待拆分的场景对象。
        options: 拆分选项，为 None 时使用默认策略。

    Returns:
        拆分后的 Panel 列表。

    Raises:
        AIServiceError: AI 服务调用失败时抛出。
    """
```

```tsx
// TypeScript：仅对导出的函数/类型写 JSDoc
/**
 * 获取指定小说的所有章节列表。
 * @param novelId - 小说 ID
 * @returns 章节列表
 */
export async function fetchChapters(novelId: number): Promise<ChapterSummary[]> {
  const { data } = await apiClient.get(`/novels/${novelId}/chapters`);
  return data;
}
```

#### 3.1.2 代码注释规范

```python
# ✅ 正确：解释"为什么"而非"是什么"
# 使用批量插入而非逐条插入，减少数据库往返次数
panels = [Panel(scene_id=sid, order=i) for i, p in enumerate(panel_data)]
session.add_all(panels)

# ❌ 错误：无意义注释
# 循环遍历 panel_data
for i, p in enumerate(panel_data):
    ...
```

### 3.2 代码格式化

| 工具 | 语言 | 配置文件 |
|------|------|----------|
| Ruff | Python | `pyproject.toml` 中的 `[tool.ruff]` |
| Prettier | TypeScript | `.prettierrc` |
| ESLint | TypeScript | `eslint.config.js` |

所有代码提交前必须通过格式化检查和 Lint 检查。CI 流水线中会强制执行此要求。

### 3.3 文件大小限制

- **单个文件不超过 500 行**。超过时考虑拆分为多个文件或模块。
- **单个函数不超过 80 行**。超过时考虑拆分为多个函数。
- **单行不超过 100 字符**。超出时换行。

---
