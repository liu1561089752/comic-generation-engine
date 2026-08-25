# AI Webtoon Factory（AI 漫画工厂）

小说 → AI Webtoon 漫画的自动化生产线：上传小说后，依次完成 **角色设计 → 世界观构建 → 脚本生成 → 分镜设计 → AI 排版 → 画面生成 → 导出**，全程由后台任务驱动，前端实时展示进度。

## 功能概览

- **8 阶段生产流水线**：小说导入、角色设计、世界观构建、脚本生成、分镜设计、AI 排版、画面生成、导出；Dashboard 展示最新项目整体进度，项目详情页实时跟踪当前项目。
- **人物 IP 管理**：角色提取、形象图生成、多表情状态形象；一项目一小说、一项目一世界观（数据库唯一索引保证）。
- **世界观资产库**：场景 / 道具 / 建筑 / 服装四类资产与生图任务。
- **任务中心**：21+ 种 AI 后台任务（脚本、分镜、排版、生图、提取等），排队去重、进度轮询、失败重试。
- **模型中心**：LLM 与生图模型统一由 [liteLLM](https://github.com/BerriAI/litellm) 接入，支持任意 OpenAI 兼容服务（`openai/` 前缀 + 自定义 api_base）。
- **导出中心**：将生成的漫画页导出为本地文件夹 / zip 包。
- **安全基线**：登录限流、Token 黑名单、刷新令牌撤销、API Key AES-256-GCM 加密存储。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.12+ / FastAPI / SQLAlchemy 2.0 (async) / PostgreSQL (asyncpg) / Alembic / pydantic v2 / liteLLM |
| 前端 | React 18 / TypeScript / Vite / Ant Design 5 / Zustand / ECharts |
| 测试 | pytest + pytest-asyncio（后端）；tsc / ESLint（前端） |

## 目录结构

```
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── core/             # 配置、数据库、安全、加密、任务类型常量
│   │   ├── infra/            # 适配器（llm / image_gen）、任务调度、存储
│   │   ├── middleware/       # 认证、限流等中间件
│   │   ├── models/           # SQLAlchemy ORM 模型
│   │   ├── modules/          # 业务模块（novel/character/world/export/...）
│   │   └── routers/          # API 路由
│   ├── migrations/           # Alembic 迁移
│   └── tests/                # pytest 测试
├── frontend/                 # React 前端
│   └── src/
│       ├── api/              # axios 接口封装
│       ├── components/       # 通用组件（LazyImage、TaskProgressBar...）
│       ├── pages/            # 页面（Dashboard、任务中心、角色、世界观、生图中心...）
│       ├── stores/           # zustand 状态
│       └── hooks/            # 自定义 hooks（任务进度轮询、自动保存...）
├── docs/                     # 项目文档（见下方文档索引）
└── .gitignore / .gitattributes
```

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- PostgreSQL（默认库名 `webtoon_factory`）

### 1. 后端

```bash
cd backend
pip install -r requirements.txt

# 配置环境变量（模板见 backend/.env.example，含 APP_SECRET_KEY 等必填项）
cp .env.example .env

# 初始化数据库
python -m alembic upgrade head

# 启动（默认 http://127.0.0.1:8000）
uvicorn app.main:app --reload --port 8000
```

首次启动会创建默认管理员账号（密码见 `ADMIN_INITIAL_PASSWORD`）。

### 2. 前端

```bash
cd frontend
npm install
npm run dev        # 开发模式 http://localhost:5173
npm run build      # 生产构建
```

前端通过 Vite 代理将 `/api` 转发到后端（见 `frontend/vite.config.ts`）。

### 3. 测试与检查

```bash
# 后端测试（Windows 沙箱环境需 -p no:cacheprovider）
cd backend && python -m pytest -p no:cacheprovider

# 前端类型检查 / Lint
cd frontend && npx tsc --noEmit && npx eslint src
```

## 环境变量清单（backend/.env）

完整模板见 [`backend/.env.example`](backend/.env.example)，关键项：

| 变量 | 说明 | 示例 |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL 连接串（asyncpg） | `postgresql+asyncpg://postgres:***@localhost:5432/webtoon_factory` |
| `APP_SECRET_KEY` | 应用密钥（JWT 签名 + API Key 加密派生，**生产必须固定**） | 48 位以上随机串 |
| `ADMIN_INITIAL_PASSWORD` | 首次启动创建管理员时使用的初始密码 | — |
| `LLM_API_BASE` / `LLM_API_KEY` / `LLM_MODEL` | LLM 服务地址 / 密钥 / 模型名（liteLLM，可带 `openai/` 前缀） | `http://127.0.0.1:5000` |
| `IMAGE_API_BASE` / `IMAGE_API_KEY` / `IMAGE_MODEL` | 生图服务地址 / 密钥 / 模型名 | `http://localhost:8567` |
| `IMAGE_MAX_CONCURRENT` | 生图并发数（默认 2，按服务能力调整） | `6` |
| `CORS_ORIGINS` | 允许的前端源，逗号分隔 | `http://localhost:5173` |
| `STORAGE_LOCAL_PATH` | 生成图片落盘目录（相对路径解析到 backend 下） | `./data/storage` |
| `EXPORT_TEMP_DIR` | 导出打包临时目录 | `./data/exports` |
| `EXPORT_TARGET_DIR` | 导出目标目录（本机路径，如 `F:\`） | `F:\` |
| `EXPORT_MAX_FILE_SIZE_MB` | 导出文件大小上限（MB） | `500` |
| `PAGE_LIMIT_ENABLED` | `true` 时只生成前 100 页（P1-P100），防止页数过多 | `true` |

> 安全提示：`.env` 已被 `.gitignore` 排除，**切勿提交真实密钥**。生产环境 `APP_ENV=production` 时 `APP_SECRET_KEY` 为空会直接启动失败。

## 文档索引

```
docs/
├── 00-Project-Bible/    # 项目圣经（总纲）
├── 01-Product/          # PRD / ROADMAP / UIUX
├── 02-Architecture/     # API / DBD / 模型 / 提示词 / 工作流等架构文档
├── 03-Development/      # 开发规范（Git/CodingStyle/Testing）、优化计划、ADR
├── 04-Operation/        # 部署 / 管理员 / 用户指南 / 变更日志
└── PRD/                 # 按功能模块拆分的产品需求
```

> 部分早期文档（如 TAD/旧 PRD 章节）与当前实现可能不一致，**以代码与 `docs/03-Development` 下的文档为准**。

## 开发规范

- **Git 提交**：`feat:` / `fix:` / `refactor:` / `perf:` / `docs:` / `chore:` + 简短中文描述，一次提交只做一件事；大批量重构完成后尽快做基准提交，避免工作区长期堆叠。
- **代码风格**：Python 遵循 `docs/03-Development/CodingStyle.md`；前端遵循 ESLint + Prettier 配置。
- **优化与决策记录**：见 `docs/03-Development/OptimizationPlan.md`（O1-O16）与 `docs/03-Development/ADR.md`。
