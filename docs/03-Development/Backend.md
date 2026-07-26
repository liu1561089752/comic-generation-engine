# AI Webtoon Factory — 后端开发规范

> **版本**：v1.0  
> **最后更新**：2026-06-27  
> **状态**：草案  
> **适用语言**：Python 3.11+  
> **框架**：FastAPI  
> **ORM**：SQLAlchemy 2.0+（异步模式）

---

## 1. 项目结构

后端代码遵循分层架构，目录结构如下：

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 应用入口
│   ├── config.py                  # 配置加载（环境变量 → Pydantic Settings）
│   ├── database.py                # 数据库连接 + Session 管理
│   │
│   ├── routers/                   # API 路由层
│   │   ├── __init__.py
│   │   ├── novels.py              # /api/v1/novels
│   │   ├── characters.py          # /api/v1/characters
│   │   ├── scenes.py              # /api/v1/scenes
│   │   ├── panels.py              # /api/v1/panels
│   │   ├── shots.py               # /api/v1/shots
│   │   ├── pages.py               # /api/v1/pages
│   │   ├── bubbles.py             # /api/v1/bubbles
│   │   ├── prompts.py             # /api/v1/prompts
│   │   ├── generation.py          # /api/v1/generation
│   │   ├── quality.py             # /api/v1/qa
│   │   ├── export.py              # /api/v1/export
│   │   ├── resources.py           # /api/v1/resources
│   │   ├── models.py              # /api/v1/models
│   │   ├── plugins.py             # /api/v1/plugins
│   │   ├── system.py              # /api/v1/system
│   │   └── ws.py                  # WebSocket 路由
│   │
│   ├── services/                  # 服务层（业务逻辑）
│   │   ├── __init__.py
│   │   ├── novel_service.py
│   │   ├── character_service.py
│   │   ├── scene_service.py
│   │   ├── panel_service.py
│   │   ├── shot_service.py
│   │   ├── page_service.py
│   │   ├── bubble_service.py
│   │   ├── prompt_service.py
│   │   ├── generation_service.py
│   │   ├── quality_service.py
│   │   ├── export_service.py
│   │   ├── model_service.py
│   │   ├── pipeline_service.py    # 管线编排
│   │   └── task_service.py        # 任务调度服务
│   │
│   ├── agents/                    # AI Agent 层
│   │   ├── __init__.py
│   │   ├── base_agent.py          # Agent 基类
│   │   ├── text_cleaner.py
│   │   ├── story_analyzer.py
│   │   ├── semantic_splitter.py
│   │   ├── storyboard_planner.py
│   │   ├── camera_planner.py
│   │   ├── layout_planner.py
│   │   ├── bubble_planner.py
│   │   ├── prompt_generator.py
│   │   ├── consistency_checker.py
│   │   └── quality_scorer.py
│   │
│   ├── adapters/                  # AI 模型适配层
│   │   ├── __init__.py
│   │   ├── base_llm.py
│   │   ├── openai_adapter.py
│   │   ├── base_image_gen.py
│   │   ├── sd_api_adapter.py
│   │   └── midjourney_adapter.py
│   │
│   ├── models/                    # SQLAlchemy ORM 模型
│   │   ├── __init__.py
│   │   ├── novel.py
│   │   ├── chapter.py
│   │   ├── scene.py
│   │   ├── panel.py
│   │   ├── shot.py
│   │   ├── page.py
│   │   ├── bubble.py
│   │   ├── prompt.py
│   │   ├── image.py
│   │   ├── character.py
│   │   ├── worldview.py
│   │   ├── task.py
│   │   ├── quality_report.py
│   │   ├── model_config.py
│   │   └── plugin.py
│   │
│   ├── repositories/              # 数据访问层
│   │   ├── __init__.py
│   │   ├── base.py                # 基础 CRUD 抽象类
│   │   ├── novel_repo.py
│   │   ├── chapter_repo.py
│   │   ├── scene_repo.py
│   │   ├── panel_repo.py
│   │   ├── shot_repo.py
│   │   ├── page_repo.py
│   │   ├── bubble_repo.py
│   │   ├── prompt_repo.py
│   │   ├── image_repo.py
│   │   └── ...
│   │
│   ├── schemas/                   # Pydantic 数据模型（API 请求/响应）
│   │   ├── __init__.py
│   │   ├── novel_schema.py
│   │   ├── chapter_schema.py
│   │   ├── scene_schema.py
│   │   ├── panel_schema.py
│   │   ├── shot_schema.py
│   │   ├── page_schema.py
│   │   ├── bubble_schema.py
│   │   ├── prompt_schema.py
│   │   ├── image_schema.py
│   │   └── ...
│   │
│   ├── tasks/                     # Celery 任务定义
│   │   ├── __init__.py
│   │   ├── celery_app.py
│   │   ├── generation_tasks.py
│   │   ├── analysis_tasks.py
│   │   └── export_tasks.py
│   │
│   ├── plugins/                   # 插件引擎（规划中）
│   │   ├── __init__.py
│   │   ├── base_plugin.py
│   │   ├── plugin_manager.py
│   │   └── hook_registry.py
│   │
│   ├── middleware/                # 中间件
│   │   ├── __init__.py
│   │   ├── auth.py                # JWT 认证
│   │   ├── cors.py
│   │   ├── log_sanitizer.py       # 日志脱敏
│   │   └── rate_limit.py          # 限流
│   │
│   └── utils/                     # 工具函数
│       ├── __init__.py
│       ├── security.py            # 加密/哈希
│       ├── file_utils.py
│       ├── image_utils.py
│       └── text_utils.py
│
├── migrations/                    # Alembic 迁移脚本
├── alembic.ini
├── requirements.txt
├── pyproject.toml                 # 规划中
└── Dockerfile
```

### 1.1 分层调用规则

```
Router（路由层）
    │ 接收 HTTP 请求，参数校验，调用 Service
    ▼
Service（服务层）
    │ 业务逻辑编排，调用 Agent / Repository / Adapter
    ▼
Agent（AI Agent 层）
    │ 特定 AI 任务的实现，调用 Adapter 连接 LLM
    ▼
Repository（数据访问层）
    │ ORM 操作封装，CRUD 方法
    ▼
Database（数据库）
```

**禁止跨层调用**：Router 不能直接调用 Repository，Service 不能直接访问数据库连接。每层只能调用其直接下层。

---

## 2. 开发环境搭建

### 2.1 前置条件

| 依赖 | 版本要求 | 说明 |
|------|----------|------|
| Python | 3.11+ | 推荐使用 pyenv 或 conda 管理版本 |
| PostgreSQL | 15+ | 生产数据库（开发可用 SQLite 替代） |
| Redis | 7+ | 缓存 + Celery Broker（开发可选） |
| Poetry | 1.7+ | 依赖管理工具 |

### 2.2 安装步骤

```bash
# 1. 克隆仓库
git clone <repo-url>
cd webtoon-factory/backend

# 2. 安装 Poetry（如未安装）
pip install poetry

# 3. 安装依赖
poetry install

# 4. 激活虚拟环境
poetry shell

# 5. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，至少设置 DATABASE_URL 和 APP_SECRET_KEY

# 6. 运行数据库迁移
alembic upgrade head

# 7. 启动开发服务器
uvicorn app.main:app --reload --port 8000
```

### 2.3 配置说明

配置通过环境变量加载，使用 `pydantic-settings` 管理：

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 应用
    APP_ENV: str = "development"
    APP_SECRET_KEY: str
    APP_DEBUG: bool = True
    APP_LOG_LEVEL: str = "INFO"

    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/app.db"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # AI 模型
    LLM_API_BASE: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4-turbo"

    IMAGE_API_BASE: str = "http://localhost:7860/sdapi/v1"
    IMAGE_API_KEY: str = ""
    IMAGE_MODEL: str = "sd_xl_base_1.0"
    IMAGE_DEFAULT_WIDTH: int = 1080
    IMAGE_DEFAULT_HEIGHT: int = 1440

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

settings = Settings()
```

### 2.4 开发与生产数据库切换

```python
# app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import settings

# 根据环境变量自动选择数据库
# 开发：sqlite+aiosqlite:///./data/app.db
# 生产：postgresql+asyncpg://user:pass@host/db

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_DEBUG,
    pool_size=5 if "postgresql" in settings.DATABASE_URL else None,
    max_overflow=10 if "postgresql" in settings.DATABASE_URL else None,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
```

---

## 3. 核心架构模式

### 3.1 分层架构

后端采用四层架构，每层职责明确：

| 层级 | 目录 | 职责 | 输入 | 输出 |
|------|------|------|------|------|
| 路由层 | `routers/` | HTTP 路由定义、参数校验、响应序列化 | HTTP 请求 | HTTP 响应 |
| 服务层 | `services/` | 业务逻辑编排、事务管理、跨模块协调 | Service 参数 | Service 结果 |
| Agent 层 | `agents/` | AI 任务实现、LLM 调用编排 | JSON 结构化数据 | JSON 结构化数据 |
| 数据层 | `repositories/` | ORM 操作封装、查询构建 | 查询条件 | ORM 对象 |

### 3.2 依赖注入

使用 FastAPI 的 `Depends` 实现依赖注入：

```python
# 依赖定义
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    ...

# 路由中使用
@router.get("/novels/{novel_id}")
async def get_novel(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = NovelService(db)
    return await service.get_novel(novel_id)
```

### 3.3 异步编程

所有 I/O 操作必须使用 `async/await`：

```python
# 正确的异步模式
async def get_novel(novel_id: UUID) -> Novel:
    return await self.repo.get_by_id(novel_id)

# 同步阻塞模式（禁止使用）
def get_novel(novel_id: UUID) -> Novel:
    return self.repo.get_by_id_sync(novel_id)  # ❌ 阻塞事件循环

# 如果需要执行 CPU 密集型操作，使用 run_in_executor
import asyncio

async def process_image(image_data: bytes) -> bytes:
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, cpu_intensive_process, image_data)
    return result
```

### 3.4 Service 层模式

Service 是业务逻辑的核心编排层，遵循以下模式：

```python
# services/novel_service.py
class NovelService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = NovelRepo(db)

    async def create_novel(self, project_id: UUID, data: NovelCreate) -> Novel:
        """创建小说"""
        novel = await self.repo.create(
            project_id=project_id,
            **data.model_dump(),
        )
        # 创建成功后，自动触发文本清洗任务
        await task_service.dispatch(
            task_type="text_clean",
            novel_id=novel.id,
        )
        return novel

    async def get_novel_with_chapters(self, novel_id: UUID) -> NovelWithChapters:
        """获取小说及其章节列表"""
        novel = await self.repo.get_by_id(novel_id)
        chapters = await ChapterRepo(self.db).get_by_novel(novel_id)
        return NovelWithChapters(novel=novel, chapters=chapters)
```

---

## 4. 如何添加新 API

### 4.1 创建路由

在 `routers/` 目录下创建路由文件：

```python
# routers/your_module.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/your-module", tags=["Your Module"])

@router.get("/")
async def list_items(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取列表"""
    service = YourService(db)
    return await service.list_items()
```

### 4.2 创建 Schema

在 `schemas/` 目录下定义 Pydantic 模型：

```python
# schemas/your_schema.py
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

class YourItemCreate(BaseModel):
    """创建请求"""
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)

class YourItemUpdate(BaseModel):
    """更新请求"""
    name: str | None = None
    description: str | None = None

class YourItemResponse(BaseModel):
    """响应"""
    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

### 4.3 创建 Service

在 `services/` 目录下创建服务类：

```python
# services/your_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.your_repo import YourRepo

class YourService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = YourRepo(db)

    async def list_items(self) -> list[YourModel]:
        return await self.repo.list()

    async def create_item(self, data: YourItemCreate) -> YourModel:
        return await self.repo.create(**data.model_dump())
```

### 4.4 注册路由

在 `app/main.py` 中注册路由：

```python
# main.py
from app.routers import your_module

app.include_router(your_module.router)
```

### 4.5 API 版本控制

- 所有 API 路径以 `/api/v1/` 开头
- 向后兼容的变更（新增可选参数、新增字段）：保持当前版本
- 不兼容变更：创建新的路由版本（如 `/api/v2/`）
- 弃用 API 遵循：公告 → 弃用期（至少一个次版本） → 移除

---

## 5. 如何添加新 AI Agent

### 5.1 创建 Agent 类

继承 `BaseAgent` 基类：

```python
# agents/your_agent.py
from app.agents.base_agent import BaseAgent
from app.schemas.agent_schema import AgentInput, AgentOutput

class YourAgent(BaseAgent):
    """你新的 AI Agent"""

    agent_id = "your_agent_id"
    agent_name = "你的 Agent 名称"
    description = "Agent 功能描述"

    async def process(self, input_data: AgentInput) -> AgentOutput:
        """核心处理逻辑"""
        # 1. 准备 Prompt
        prompt = self.build_prompt(input_data)

        # 2. 调用 LLM
        llm_result = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=4096,
        )

        # 3. 解析 LLM 输出为结构化 JSON
        result = self.parse_response(llm_result.content)

        # 4. 返回结构化输出
        return AgentOutput(**result)

    def build_prompt(self, input_data: AgentInput) -> str:
        """构建 Prompt"""
        return f"""
        你是一个专业的漫画制作 AI 助手。
        根据以下输入，执行你的 Agent 任务。

        输入数据：
        {input_data.model_dump_json(indent=2)}

        请按以下 JSON 格式输出：
        {{
            // 你的输出 Schema
        }}
        """
```

**BaseAgent 基类定义**：

```python
# agents/base_agent.py
from abc import ABC, abstractmethod
from app.adapters.base_llm import BaseLLMAdapter

class BaseAgent(ABC):
    agent_id: str
    agent_name: str
    description: str

    def __init__(self, llm: BaseLLMAdapter | None = None):
        self.llm = llm

    @abstractmethod
    async def process(self, input_data: dict) -> dict:
        """执行 Agent 处理逻辑"""
        pass
```

### 5.2 注册到 AgentRegistry

```python
# agents/__init__.py
from app.agents.registry import AgentRegistry
from app.agents.your_agent import YourAgent

def register_agents():
    AgentRegistry.register(YourAgent)

# agents/registry.py
class AgentRegistry:
    _agents: dict[str, type[BaseAgent]] = {}

    @classmethod
    def register(cls, agent_cls: type[BaseAgent]):
        cls._agents[agent_cls.agent_id] = agent_cls

    @classmethod
    def get(cls, agent_id: str) -> type[BaseAgent]:
        if agent_id not in cls._agents:
            raise ValueError(f"Agent {agent_id} 未注册")
        return cls._agents[agent_id]

    @classmethod
    def list_agents(cls) -> list[dict]:
        return [
            {"id": aid, "name": cls.agent_name, "desc": cls.description}
            for aid, cls in cls._agents.items()
        ]
```

### 5.3 添加对应任务

在 `tasks/` 中添加 Celery 任务：

```python
# tasks/analysis_tasks.py
from app.agents.registry import AgentRegistry
from app.tasks.celery_app import celery_app

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_agent_task(self, agent_id: str, input_data: dict) -> dict:
    """通用 AI Agent 任务"""
    try:
        agent_cls = AgentRegistry.get(agent_id)
        agent = agent_cls()
        result = await agent.process(input_data)
        return result
    except Exception as exc:
        raise self.retry(exc=exc)
```

---

## 6. 数据库操作规范

### 6.1 Repository 模式

每个实体对应一个 Repository，封装所有数据库操作：

```python
# repositories/base.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

class BaseRepo:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.model = None  # 子类必须设置

    async def get_by_id(self, id: UUID) -> model | None:
        stmt = select(self.model).where(self.model.id == id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: dict | None = None,
        order_by: str | None = None,
    ) -> list[model]:
        stmt = select(self.model)
        if filters:
            for key, value in filters.items():
                stmt = stmt.where(getattr(self.model, key) == value)
        if order_by:
            stmt = stmt.order_by(order_by)
        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, **kwargs) -> model:
        obj = self.model(**kwargs)
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def update(self, id: UUID, **kwargs) -> model | None:
        obj = await self.get_by_id(id)
        if not obj:
            return None
        for key, value in kwargs.items():
            setattr(obj, key, value)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, id: UUID) -> bool:
        obj = await self.get_by_id(id)
        if not obj:
            return False
        await self.db.delete(obj)
        await self.db.commit()
        return True
```

### 6.2 命名规范

| 项目 | 规范 | 示例 |
|------|------|------|
| 表名 | 蛇形命名，复数 | `novels`, `scenes`, `character_relations` |
| 字段名 | 蛇形命名 | `created_at`, `paragraph_ref` |
| Python 模型类 | 大驼峰 | `class Novel(Base)` |
| Repository 类 | 大驼峰 + Repo | `class NovelRepo(BaseRepo)` |
| Service 类 | 大驼峰 + Service | `class NovelService` |
| Schema 类 | 大驼峰 + 后缀 | `NovelCreate`, `NovelResponse` |
| 路由函数 | 蛇形命名 | `async def get_novel()` |

### 6.3 事务管理

- 单个 Repository 方法内无须显式事务管理（SQLAlchemy 自动管理）
- 跨 Repository 的操作在 Service 层使用事务：

```python
async def create_panel_with_bubbles(self, panel_data, bubble_data_list):
    async with self.db.begin():
        panel = await self.panel_repo.create(**panel_data)
        for data in bubble_data_list:
            await self.bubble_repo.create(panel_id=panel.id, **data)
    return panel
```

### 6.4 查询优化

- 关联查询使用 `selectinload` 或 `joinedload` 避免 N+1 问题
- 列表接口必须支持分页（`skip`/`limit`）
- 大数据量场景使用流式查询
- 长列表查询使用游标分页（cursor pagination）而非偏移分页

---

## 7. 错误处理规范

### 7.1 自定义异常

```python
# utils/exceptions.py
class AppException(Exception):
    """应用基础异常"""
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code

class NotFoundException(AppException):
    def __init__(self, entity: str, entity_id: str):
        super().__init__(
            code="NOT_FOUND",
            message=f"{entity} {entity_id} 不存在",
            status_code=404,
        )

class BusinessException(AppException):
    def __init__(self, message: str):
        super().__init__(
            code="BUSINESS_ERROR",
            message=message,
            status_code=400,
        )
```

### 7.2 全局异常处理器

```python
# main.py
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        },
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未捕获异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误",
            }
        },
    )
```

### 7.3 统一响应格式

所有 API 响应遵循统一格式：

```json
// 成功响应
{
    "data": { ... },
    "meta": {
        "total": 100,
        "skip": 0,
        "limit": 20
    }
}

// 错误响应
{
    "error": {
        "code": "NOT_FOUND",
        "message": "小说 123e4567 不存在"
    }
}
```

---

## 8. 日志规范

### 8.1 日志级别使用

| 级别 | 使用场景 | 示例 |
|------|----------|------|
| DEBUG | 调试信息，开发环境使用 | SQL 查询、函数参数 |
| INFO | 关键业务流程记录 | 用户登录、小说导入、任务开始/完成 |
| WARNING | 异常但可自动恢复 | API 重试、限流触发、LLM 返回异常格式 |
| ERROR | 功能不可用但系统可继续运行 | LLM 调用失败、图片生成失败 |
| CRITICAL | 系统不可用 | 数据库连接失败、磁盘空间不足 |

### 8.2 日志内容规范

```python
import structlog
logger = structlog.get_logger()

# INFO 级别：记录关键业务事件
logger.info("novel_imported",
    novel_id=novel.id,
    novel_title=novel.title,
    chapter_count=len(chapters),
    word_count=novel.word_count,
)

# ERROR 级别：记录失败详情
logger.error("agent_execution_failed",
    agent_id="text_cleaner",
    novel_id=novel_id,
    error=str(exc),
    traceback=traceback.format_exc(),
)
```

### 8.3 敏感信息脱敏

日志中禁止出现以下信息，使用 `***` 替代：
- API Key、Secret Key、Token
- 密码、身份证号、电话号码
- 用户邮箱（允许显示域名部分）

日志脱敏在中间件层自动处理，不需要在每个日志调用处手动脱敏。

---

## 9. 性能优化指南

### 9.1 数据库层

- 善用 SQLAlchemy 的 `selectinload` 避免 N+1 查询
- 列表接口必须分页，默认 `limit=20`，最大 `limit=100`
- 为高频查询字段建立索引（参考 DBD 文档的索引策略）
- 生产环境使用 PostgreSQL 连接池（最小 5，最大 20）

### 9.2 AI 调用层

- LLM 调用使用流式响应（`stream=True`），减少等待时间
- 生图任务每个 Panel 批量生成 4-8 张候选图，而非单张生成
- LLM 调用使用连接池复用 HTTP 连接（`httpx.AsyncClient`）
- 相同 Prompt 的调用使用缓存（Redis），避免重复请求

### 9.3 异步任务层

- AI 密集型任务通过 Celery 异步执行，不阻塞 API 响应
- 使用 WebSocket 推送任务状态，避免前端轮询
- 设置合理的队列并发数：生图 2-4，分析 8-16，导出 1-2

### 9.4 代码层

- 缓存频繁读取的配置数据（角色设定、Prompt 模板等）
- 大文件上传使用流式处理，避免加载到内存
- 批量操作使用批量插入（`bulk_insert`）而非逐条插入
- 图片处理使用 Web Worker 或后台任务，避免阻塞 API

---

## 附录 A：依赖清单

```txt
# requirements.txt 核心依赖
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
sqlalchemy[asyncio]>=2.0.0
alembic>=1.13.0
asyncpg>=0.29.0          # PostgreSQL 异步驱动
aiosqlite>=0.19.0        # SQLite 异步驱动（开发用）
celery>=5.4.0
redis>=5.0.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
httpx>=0.27.0            # 异步 HTTP 客户端
cryptography>=41.0.0     # API Key 加密
python-magic>=0.4.27     # 文件类型检测
Pillow>=10.0.0           # 图片处理
structlog>=24.0.0        # 结构化日志
python-jose[cryptography]>=3.3.0  # JWT
passlib[bcrypt]>=1.7.0   # 密码哈希
```

---

*本文档为后端开发的核心规范，所有后端开发人员必须遵守。如有疑问，请提交 Issue 至项目仓库。*
