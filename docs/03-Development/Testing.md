# AI Webtoon Factory — 测试规范（Testing Specification）

> 版本：v1.0  
> 最后更新：2026-06-27  
> 状态：草案  
> 适用范围：后端（pytest）、前端（Vitest）、E2E（Playwright）

---

## 1. 测试哲学

### 1.1 测试金字塔

```
      /\          E2E Tests（端到端）
     /  \         覆盖核心用户流程，数量少
    /    \
   /──────\
  /        \      Integration Tests（集成测试）
 /          \     覆盖 API + Agent 管线协作
/────────────\
┌────────────────┐
│  Unit Tests    │  单元测试，数量最多
│  (单元测试)    │  覆盖 Service / Agent / Repository 关键逻辑
└────────────────┘
```

### 1.2 测试目标

| 指标 | MVP 阶段 | V2 阶段 | V3 阶段 |
|------|----------|---------|---------|
| 单元测试覆盖率 | ≥ 40% | ≥ 60% | ≥ 80% |
| 集成测试覆盖率 | 核心 API | 全部 API | 全部 API + 异常场景 |
| E2E 覆盖率 | 1 条主线流程 | 3 条核心流程 | 全部核心流程 |

### 1.3 测试原则

1. **可靠优先**：测试不应是脆弱的（flaky）。非确定性逻辑（如 LLM 返回）必须 Mock。
2. **速度优先**：单元测试 < 100ms/个，集成测试 < 2s/个。运行全部单元测试 < 1 分钟。
3. **可维护**：测试代码遵循与生产代码相同的编码规范。
4. **测试行为而非实现**：测试外部可见行为，而非内部实现细节。重构不应当导致测试失败。

---

## 2. 单元测试

### 2.1 覆盖范围

| 层 | 必须覆盖 | 可选覆盖 |
|----|----------|----------|
| `services/` | 核心业务逻辑、分支条件、边界值、异常处理 | 纯 CRUD 委托方法 |
| `agents/` | Prompt 构造、响应解析、重试逻辑、错误处理 | SDK 调用封装 |
| `repositories/` | 复杂查询、分页逻辑、事务操作 | 基础 CRUD |
| `schemas/` | 自定义验证器（`@field_validator`） | Pydantic 基础类型校验 |
| `utils/` | 全部工具函数 | — |

### 2.2 框架与工具

#### 2.2.1 Python（pytest）

```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    -v
    --strict-markers
    --tb=short
    --cov=app
    --cov-report=term-missing
```

#### 2.2.2 TypeScript（Vitest）

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.d.ts', 'src/**/*.test.*', 'src/main.tsx'],
    },
  },
});
```

### 2.3 文件组织

```bash
tests/
├── conftest.py                    # 共享 fixture
├── unit/                          # 单元测试
│   ├── services/
│   │   ├── test_novel_service.py
│   │   ├── test_character_service.py
│   │   └── test_panel_service.py
│   ├── agents/
│   │   ├── test_text_clean_agent.py
│   │   ├── test_scene_split_agent.py
│   │   └── test_prompt_gen_agent.py
│   ├── repositories/
│   │   └── test_novel_repository.py
│   └── utils/
│       └── test_file_utils.py
├── integration/                   # 集成测试
│   ├── api/
│   │   ├── test_novel_api.py
│   │   ├── test_character_api.py
│   │   ├── test_scene_api.py
│   │   └── test_panel_api.py
│   └── pipeline/
│       └── test_full_pipeline.py
├── fixtures/                      # 测试夹具数据
│   ├── novels/
│   │   └── sample_chapter.txt
│   ├── scenes/
│   │   └── sample_scene.json
│   └── factory.py                 # 测试数据工厂
└── e2e/                           # E2E 测试
    └── workflows/
        └── test_create_webtoon.py
```

**命名规则：**

- 测试文件：`test_<被测模块>.py`
- 测试类：`Test<被测类名>`（可选，可用纯函数风格）
- 测试函数：`test_<被测功能>_<场景>_<期望行为>`

### 2.4 测试模式

#### 2.4.1 Arrange-Act-Assert（AAA）模式

```python
# ✅ 正确：AAA 模式
async def test_create_novel_with_valid_data():
    # Arrange（准备）
    service = NovelService(repo=mock_repo, agent=mock_agent)
    data = NovelCreate(title="测试小说", content="第一章 开始")

    # Act（执行）
    result = await service.create_novel(data)

    # Assert（验证）
    assert result.title == "测试小说"
    assert result.status == NovelStatus.DRAFT
    mock_repo.save.assert_awaited_once()
```

```python
# ❌ 错误：缺少清晰的结构
async def test_create_novel():
    service = NovelService(repo=mock_repo, agent=mock_agent)
    data = NovelCreate(title="测试小说", content="第一章 开始")
    result = await service.create_novel(data)
    assert result.title == "测试小说"
    # 断言不够全面
```

#### 2.4.2 Given-When-Then 模式（适用于 BDD 风格）

```python
async def test_panel_creation_with_invalid_order():
    """Given: 同一场景下已有 3 个 Panel
       When: 创建第 4 个 Panel 且序号重复
       Then: 应自动调整序号
    """
    # Given
    repo = mock.Mock()
    repo.get_max_order.return_value = 3
    service = PanelService(repo=repo, agent=mock_agent)

    # When
    panel = await service.create_panel(scene_id=1, order=2)

    # Then
    assert panel.order == 4  # 自动分配新的最大序号
```

### 2.5 Mock 策略

#### 2.5.1 各层 Mock 规则

| 被测层 | Mock 对象 | 不 Mock |
|--------|-----------|---------|
| Service | Repository、Agent | Service 自身的业务逻辑 |
| Agent | LLM Adapter、Image Gen Adapter | Agent 的 Prompt 构造和响应解析 |
| Repository | SQLAlchemy Session | Repository 的查询逻辑 |
| Router | Service | Router 的参数校验 |

#### 2.5.2 Python Mock 示例

```python
# tests/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture
def mock_llm_adapter():
    """Mock LLM 适配器，返回固定响应"""
    adapter = AsyncMock(spec=LLMAdapter)
    adapter.generate.return_value = {
        "choices": [{
            "message": {
                "content": '{"panels": [{"description": "场景描述"}]}'
            }
        }]
    }
    return adapter

@pytest.fixture
def mock_repo():
    """Mock Repository"""
    repo = MagicMock(spec=NovelRepository)
    repo.get_by_id = AsyncMock()
    repo.save = AsyncMock()
    repo.delete = AsyncMock()
    return repo

@pytest.fixture
def scene_split_agent(mock_llm_adapter):
    """使用 Mock LLM 的场景拆分 Agent"""
    return SceneSplitAgent(llm=mock_llm_adapter)

# tests/unit/agents/test_scene_split_agent.py
class TestSceneSplitAgent:
    async def test_split_returns_correct_panel_count(self, scene_split_agent):
        """Agent 在收到有效输入时返回正确的 Panel 数量"""
        # Arrange
        scene_text = "主角走进房间。房间里有一张桌子。"

        # Act
        result = await scene_split_agent.split(scene_text, strategy="paragraph")

        # Assert
        assert len(result.panels) == 2
        assert result.panels[0].description == "场景描述"

    async def test_split_with_empty_text_raises_error(self, scene_split_agent):
        """Agent 在收到空文本时抛出自定义异常"""
        # Arrange
        empty_text = ""

        # Act & Assert
        with pytest.raises(ValidationError, match="Scene text cannot be empty"):
            await scene_split_agent.split(empty_text)
```

#### 2.5.3 TypeScript Mock 示例

```typescript
// tests/unit/hooks/useNovels.test.ts
import { renderHook, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';

// Mock API 模块
vi.mock('@/api/novels', () => ({
  fetchNovels: vi.fn(),
}));

import { fetchNovels } from '@/api/novels';
import { useNovels } from '@/hooks/useNovels';
import type { NovelSummary } from '@/types/novel';

describe('useNovels', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch and return novel list', async () => {
    // Arrange
    const mockNovels: NovelSummary[] = [
      { id: 1, title: 'Novel A', status: 'draft' },
      { id: 2, title: 'Novel B', status: 'published' },
    ];
    vi.mocked(fetchNovels).mockResolvedValue(mockNovels);

    // Act
    const { result } = renderHook(() => useNovels());

    // Assert
    expect(result.current.isLoading).toBe(true);
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.novels).toEqual(mockNovels);
    expect(result.current.error).toBeNull();
  });

  it('should handle fetch error', async () => {
    // Arrange
    vi.mocked(fetchNovels).mockRejectedValue(new Error('Network error'));

    // Act
    const { result } = renderHook(() => useNovels());

    // Assert
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.novels).toEqual([]);
    expect(result.current.error).toBe('Network error');
  });
});
```

### 2.6 测试数据工厂

使用工厂模式生成测试数据，避免在每个测试中重复构造。

```python
# tests/fixtures/factory.py
from app.models.novel import Novel
from app.models.character import Character
from app.models.scene import Scene

class NovelFactory:
    @staticmethod
    def create(
        id: int = 1,
        title: str = "测试小说",
        author: str = "作者",
        content: str = "这是小说内容。",
        status: str = "draft",
        **kwargs,
    ) -> Novel:
        return Novel(
            id=id,
            title=title,
            author=author,
            content=content,
            status=status,
            **kwargs,
        )

class SceneFactory:
    @staticmethod
    def create(
        id: int = 1,
        novel_id: int = 1,
        chapter_num: int = 1,
        scene_num: int = 1,
        content: str = "场景描述文本。",
        **kwargs,
    ) -> Scene:
        return Scene(
            id=id,
            novel_id=novel_id,
            chapter_num=chapter_num,
            scene_num=scene_num,
            content=content,
            **kwargs,
        )
```

### 2.7 服务层测试示例

```python
# tests/unit/services/test_scene_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.scene_service import SceneService
from app.schemas.scene_schema import SceneSplitRequest, SplitStrategy
from app.exceptions import ValidationError

class TestSceneService:
    @pytest.fixture
    def service(self, mock_repo, mock_agent):
        return SceneService(repo=mock_repo, agent=mock_agent)

    async def test_split_scene_creates_panels(self, service, mock_agent):
        """场景拆分成功时创建 Panel 列表"""
        # Arrange
        mock_agent.split.return_value = [
            {"description": "Panel 1", "order": 0},
            {"description": "Panel 2", "order": 1},
        ]

        # Act
        scenes = await service.split_scene(
            scene_id=1,
            request=SceneSplitRequest(strategy=SplitStrategy.PARAGRAPH)
        )

        # Assert
        assert len(scenes) == 2
        assert scenes[0].description == "Panel 1"

    async def test_split_scene_with_invalid_strategy(self, service):
        """不支持的拆分策略应抛出异常"""
        # Act & Assert
        with pytest.raises(ValidationError, match="Unsupported strategy"):
            await service.split_scene(
                scene_id=1,
                request=SceneSplitRequest(strategy="invalid")
            )
```

---

## 3. 集成测试

### 3.1 覆盖范围

- **API 端点测试**：所有 RESTful 接口的请求/响应验证
- **Agent 管线测试**：Agent 之间的数据流转
- **数据库交互测试**：CRUD 操作验证

### 3.2 集成测试配置

#### 3.2.1 Python 集成测试

```python
# tests/conftest.py（集成测试部分）
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.main import app
from app.database import get_session

# 使用 SQLite 内存数据库进行集成测试
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def test_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # 创建所有表
    async with engine.begin() as conn:
        from app.models.base import Base
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        yield session

    await engine.dispose()

@pytest.fixture
async def async_client(test_session):
    """创建测试用的 AsyncClient"""

    async def override_get_session():
        yield test_session

    app.dependency_overrides[get_session] = override_get_session

    # 使用 ASGITransport 而非默认的 HTTPX 传输
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()
```

#### 3.2.2 API 集成测试示例

```python
# tests/integration/api/test_novel_api.py
import pytest

class TestNovelAPI:
    """小说管理 API 集成测试"""

    @pytest.mark.asyncio
    async def test_create_novel(self, async_client):
        """POST /api/v1/novels 创建小说"""
        # Arrange
        payload = {
            "title": "测试小说",
            "author": "作者",
            "content": "这是小说内容。"
        }

        # Act
        response = await async_client.post("/api/v1/novels", json=payload)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "测试小说"
        assert data["status"] == "draft"
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_get_novel_not_found(self, async_client):
        """GET /api/v1/novels/999 不存在的资源"""
        # Act
        response = await async_client.get("/api/v1/novels/999")

        # Assert
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_create_novel_empty_title(self, async_client):
        """POST /api/v1/novels 标题为空"""
        # Arrange
        payload = {"title": "", "content": "内容"}

        # Act
        response = await async_client.post("/api/v1/novels", json=payload)

        # Assert
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_novels_with_pagination(self, async_client):
        """GET /api/v1/novels?skip=0&limit=10 分页查询"""
        # Arrange: 先创建 3 篇小说
        for i in range(3):
            await async_client.post("/api/v1/novels", json={
                "title": f"小说{i+1}", "content": f"内容{i+1}"
            })

        # Act
        response = await async_client.get("/api/v1/novels?skip=0&limit=10")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 3
```

### 3.3 Agent 管线集成测试

```python
# tests/integration/pipeline/test_full_pipeline.py
"""Agent 管线集成测试：测试多个 Agent 的协作"""

class TestAgentPipeline:
    """验证 Agent 管线的端到端数据流转"""

    async def test_novel_to_scenes_pipeline(self, async_client):
        """小说→章节→场景 管线

        验证：
        1. 小说上传后自动清洗
        2. 清洗后自动拆分为章节
        3. 章节自动拆分为场景
        """
        # 1. 上传小说
        novel_resp = await async_client.post("/api/v1/novels", json={
            "title": "测试小说",
            "content": "第一章 开始。\n\n这是第一章的内容。\n\n第二章。\n\n这是第二章的内容。"
        })
        novel_id = novel_resp.json()["id"]

        # 2. 触发拆分
        split_resp = await async_client.post(
            f"/api/v1/novels/{novel_id}/split"
        )
        assert split_resp.status_code == 200

        # 3. 验证场景列表
        scenes_resp = await async_client.get(f"/api/v1/novels/{novel_id}/scenes")
        assert scenes_resp.status_code == 200
        scenes = scenes_resp.json()
        assert len(scenes) > 0
        assert all("content" in scene for scene in scenes)
```

---

## 4. 测试类型

### 4.1 功能测试

覆盖所有 API 端点的正常流程和异常流程：

| 端点 | 正常场景 | 异常场景 |
|------|----------|----------|
| `POST /novels` | 创建成功 | 空标题、超长标题、空内容 |
| `GET /novels/{id}` | 返回详情 | 不存在的 ID |
| `GET /novels` | 分页列表 | 负数页码、超大门限 |
| `PUT /novels/{id}` | 更新成功 | 不存在的 ID |
| `DELETE /novels/{id}` | 删除成功 | 不存在的 ID、有关联数据 |

### 4.2 Agent 测试

```python
class TestSceneSplitAgent:
    """场景拆分 Agent 测试"""

    async def test_prompt_template_renders_correctly(self, agent):
        """Prompt 模板变量替换正确"""
        prompt = agent.build_prompt(
            scene_text="主角走进房间。",
            strategy="paragraph"
        )
        assert "{scene_text}" not in prompt  # 变量已替换
        assert "主角走进房间。" in prompt

    async def test_handle_llm_returning_invalid_json(self, agent, mock_llm):
        """LLM 返回非法 JSON 时的错误处理"""
        mock_llm.generate.return_value = {"choices": [{"message": {"content": "not json"}}]}

        with pytest.raises(AIServiceError, match="Invalid JSON response"):
            await agent.split("test text")

    async def test_retry_on_timeout(self, agent, mock_llm):
        """LLM 超时后的重试逻辑"""
        mock_llm.generate.side_effect = [
            TimeoutError("Timeout"),
            TimeoutError("Timeout"),
            {"choices": [{"message": {"content": '{"panels": []}'}}]}
        ]

        result = await agent.split("test text", max_retries=3)
        assert mock_llm.generate.await_count == 3
        assert result is not None

    async def test_max_retries_exceeded(self, agent, mock_llm):
        """超过最大重试次数后抛出异常"""
        mock_llm.generate.side_effect = TimeoutError("Timeout")

        with pytest.raises(AIServiceError, match="Max retries exceeded"):
            await agent.split("test text", max_retries=2)
```

### 4.3 Prompt 测试

```python
class TestPromptTemplate:
    """Prompt 模板测试"""

    def test_template_variable_substitution(self):
        """变量替换正确性"""
        template = PromptTemplate(
            template="请分析以下场景：{scene_text}\n策略：{strategy}"
        )
        result = template.render(
            scene_text="主角走进房间",
            strategy="paragraph"
        )
        assert "主角走进房间" in result
        assert "paragraph" in result
        assert "{scene_text}" not in result

    def test_missing_variable_raises_error(self):
        """缺少必需变量时抛出异常"""
        template = PromptTemplate(
            template="请分析：{scene_text}",
            required_vars=["scene_text"]
        )
        with pytest.raises(ValueError, match="Missing required variable"):
            template.render(strategy="paragraph")

    def test_long_prompt_truncation(self):
        """超长 Prompt 截断正确"""
        template = PromptTemplate(
            template="{content}",
            max_length=100
        )
        long_text = "a" * 200
        result = template.render(content=long_text)
        assert len(result) == 100
```

### 4.4 边界值和异常测试

```python
class TestBoundaryConditions:
    """边界条件和异常场景测试"""

    async def test_empty_novel_content(self, async_client):
        """空内容小说"""
        response = await async_client.post("/api/v1/novels", json={
            "title": "空内容",
            "content": ""
        })
        assert response.status_code == 422  # 内容为空应拒绝

    async def test_oversized_title(self, async_client):
        """超长标题"""
        response = await async_client.post("/api/v1/novels", json={
            "title": "x" * 201,  # 超过 200 字符限制
            "content": "内容"
        })
        assert response.status_code == 422

    async def test_concurrent_scene_split(self, async_client):
        """并发场景拆分"""
        import asyncio
        # 先创建小说
        novel_resp = await async_client.post("/api/v1/novels", json={
            "title": "并发测试",
            "content": "第一节。\n\n第二节。\n\n第三节。"
        })
        novel_id = novel_resp.json()["id"]

        # 并发触发拆分
        tasks = [
            async_client.post(f"/api/v1/novels/{novel_id}/split")
            for _ in range(5)
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # 验证：只有第一次调用成功，后续应返回 409 Conflict
        success_count = sum(
            1 for r in responses
            if isinstance(r, AsyncClientResponse) and r.status_code == 200
        )
        assert success_count == 1
```

---

## 5. E2E 测试

### 5.1 工具

- **框架**：Playwright
- **配置**：`playwright.config.ts`
- **环境**：独立测试环境，使用测试数据库

### 5.2 覆盖场景

```typescript
// tests/e2e/workflows/test_create_webtoon.spec.ts
import { test, expect } from '@playwright/test';

test.describe('完整创作流程', () => {
  test('用户从导入小说到导出 Webtoon 的完整流程', async ({ page }) => {
    // 1. 登录
    await page.goto('/login');
    await page.fill('[data-testid="username"]', 'testuser');
    await page.fill('[data-testid="password"]', 'testpass');
    await page.click('[data-testid="login-btn"]');
    await expect(page).toHaveURL('/dashboard');

    // 2. 新建项目
    await page.click('[data-testid="create-project"]');
    await page.fill('[data-testid="project-name"]', '测试项目');
    await page.click('[data-testid="project-submit"]');

    // 3. 上传小说
    await page.click('[data-testid="upload-novel"]');
    await page.setInputFiles(
      '[data-testid="file-upload"]',
      'tests/fixtures/novels/sample_novel.txt'
    );
    await expect(page.locator('[data-testid="upload-success"]')).toBeVisible();

    // 4. 等待场景拆分完成
    await expect(page.locator('[data-testid="scene-list"]'))
      .toBeVisible({ timeout: 30000 });

    // 5. 进入分镜编辑
    await page.click('[data-testid="first-scene"] >> [data-testid="edit-panels"]');
    await expect(page.locator('[data-testid="panel-editor"]')).toBeVisible();

    // 6. 生成图片
    await page.click('[data-testid="generate-all"]');
    await expect(page.locator('[data-testid="generation-progress"]'))
      .toBeVisible({ timeout: 5000 });
    await expect(page.locator('[data-testid="generation-complete"]'))
      .toBeVisible({ timeout: 120000 }); // 生图可能较慢

    // 7. 导出
    await page.click('[data-testid="export"]');
    await page.selectOption('[data-testid="export-format"]', 'png');
    await page.click('[data-testid="export-confirm"]');
    await expect(page.locator('[data-testid="export-success"]'))
      .toBeVisible({ timeout: 60000 });
  });
});
```

### 5.3 E2E 测试守则

1. **数量少而精**：每个核心用户流程 1-2 个 E2E 测试，不要覆盖 UI 细节。
2. **使用 data-testid 定位元素**：避免 CSS class 变化导致测试失败。
3. **设置合理的超时**：生图等耗时操作设置较长超时（120s+）。
4. **并行运行**：E2E 测试互相独立，支持 sharding。

---

## 6. 测试自动化

### 6.1 CI 流水线

```yaml
# .github/workflows/test.yml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install Python dependencies
        run: |
          cd backend
          pip install -r requirements/dev.txt

      - name: Run unit tests
        run: |
          cd backend
          pytest tests/unit -v --cov=app --cov-report=term-missing

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          directory: backend
          flags: backend-unit

  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements/dev.txt

      - name: Run integration tests
        run: |
          cd backend
          pytest tests/integration -v

  frontend-tests:
    name: Frontend Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js 18
        uses: actions/setup-node@v4
        with:
          node-version: "18"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: |
          cd frontend
          npm ci

      - name: Run frontend tests
        run: |
          cd frontend
          npm run test -- --run

      - name: Run lint
        run: |
          cd frontend
          npm run lint

  e2e-tests:
    name: E2E Tests
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests, frontend-tests]
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Set up Node.js 18
        uses: actions/setup-node@v4
        with:
          node-version: "18"

      - name: Install dependencies
        run: |
          cd backend && pip install -r requirements/dev.txt
          cd ../frontend && npm ci

      - name: Install Playwright browsers
        run: |
          cd frontend
          npx playwright install chromium

      - name: Start backend & frontend
        run: |
          cd backend
          uvicorn app.main:app --host 0.0.0.0 --port 8000 &
          cd ../frontend
          npm run dev -- --port 3000 &
          sleep 5

      - name: Run E2E tests
        run: |
          cd frontend
          npx playwright test

      - name: Upload Playwright report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: frontend/playwright-report/
```

### 6.2 测试报告

- **覆盖率报告**：使用 `coverage.py`（Python）和 `c8`（TypeScript）生成 HTML 报告。
- **CI 集成**：上传到 Codecov 或 Coveralls。
- **失败通知**：测试失败时在 GitHub PR 中 @ 相关人员。

---

## 7. 质量门禁

### 7.1 PR 合并门禁

| 检查项 | 要求 | 工具 |
|--------|------|------|
| 单元测试 | 通过率 100% | pytest / Vitest |
| 集成测试 | 通过率 100% | pytest + httpx |
| 测试覆盖率 | ≥ 目标值 | coverage.py / c8 |
| Lint | 零错误 | Ruff / ESLint |
| 类型检查 | 零错误 | mypy / TypeScript |
| 格式化 | 符合规范 | Ruff / Prettier |
| 安全扫描 | 零高危漏洞 | pip-audit / npm audit |

### 7.2 覆盖率门禁

```yaml
# 在 CI 中配置覆盖率阈值
# backend/pyproject.toml
[tool.coverage.report]
fail_under = 40  # MVP 阶段
# exclude_lines 排除模板代码
exclude_lines = [
    "pragma: no cover",
    "if __name__ == .__main__.:",
    "def __repr__",
    "class Base",
]
```

### 7.3 门禁违规处理

| 违规类型 | 处理方式 |
|----------|----------|
| 测试失败 | PR 无法合并，需修复后重新运行 CI |
| 覆盖率不足 | 标记为警告，PR 可合并但需在后续 PR 补足 |
| Lint 错误 | PR 无法合并，需修复 |
| 安全漏洞 | PR 无法合并，需修复或提交安全例外申请 |

---

## 8. 测试最佳实践

### 8.1 通用准则

1. **测试名称应描述行为**：`test_<功能>_<输入条件>_<期望结果>`。
2. **每个测试只测一个行为**：如果一个测试需要多个断言，确保它们验证的是同一个行为的不同方面。
3. **使用 fixtures 共享设置**：避免在每个测试中重复 Arrange 代码。
4. **测试边界条件**：空值、最大值、负数、特殊字符、超长字符串。
5. **测试错误路径**：每个成功的分支都有一个对应的错误路径测试。

### 8.2 避免常见陷阱

```python
# ❌ 陷阱：测试实现而非行为
async def test_save_called_with_correct_data():
    repo.save.assert_called_with(title="测试")

# ✅ 改进：测试行为结果
async def test_create_novel_returns_correct_title():
    novel = await service.create_novel(data)
    assert novel.title == "测试"

# ❌ 陷阱：使用真实外部服务
async def test_agent_with_real_llm():
    agent = SceneSplitAgent(llm=OpenAIAdapter(api_key="real-key"))
    result = await agent.split("test")
    # 测试结果不稳定，依赖网络和 API 状态

# ✅ 改进：Mock 外部依赖
async def test_agent_with_mocked_llm(mock_llm):
    agent = SceneSplitAgent(llm=mock_llm)
    result = await agent.split("test")
    # 测试结果稳定可重复
```

### 8.3 测试数据管理

1. **测试数据独立**：每个测试生成自己的数据，不依赖其他测试的执行结果。
2. **清理测试数据**：集成测试使用事务回滚或内存数据库，确保测试之间互不影响。
3. **使用 fixture 工厂**：复杂测试数据使用工厂函数生成，减少样板代码。
4. **硬编码测试数据**：测试数据应为字面量而非随机生成，确保可重复性。

### 8.4 异步测试注意事项

1. **始终 await**：所有异步调用必须 await，确保测试执行顺序正确。
2. **设置超时**：`pytest.mark.timeout(5)`，避免测试被死锁挂起。
3. **避免 asyncio.run()**：pytest-asyncio 会自动管理事件循环。
4. **测试并发代码时使用 asyncio.gather**：验证并发行为符合预期。

---

## 附录：测试命令速查

```bash
# Python 后端
pytest tests/unit                       # 运行全部单元测试
pytest tests/unit/services              # 运行特定模块测试
pytest tests/unit -k "test_create"      # 按名称过滤
pytest tests/unit -x                    # 遇到第一个失败停止
pytest tests/unit --cov=app             # 带覆盖率
pytest tests/unit -v                    # 详细输出
pytest tests/integration                # 运行全部集成测试

# TypeScript 前端
npm run test                            # 运行全部测试
npm run test -- --run                   # 一次运行（非 watch 模式）
npm run test -- --coverage              # 带覆盖率
npm run test -- --reporter=verbose      # 详细输出
npx vitest run tests/unit/hooks         # 运行特定模块测试

# E2E 测试
npx playwright test                     # 运行全部 E2E 测试
npx playwright test --headed            # 显示浏览器窗口
npx playwright test --debug             # 调试模式
npx playwright show-report              # 查看测试报告
```
