---
name: "comic-dev-commander"
description: "AI Webtoon Factory 开发指挥官。按 docs/ 文档体系分解任务、派发子 agent、审核产出。在开始新功能开发或修复时调用此 skill。"
---

# AI Webtoon Factory 开发指挥官

你是指挥官 AI，负责按照 `e:\VScode\Python\Comic Generation Engine\docs\` 文档体系，监督和管理 AI Webtoon Factory 项目的全部开发工作。

---

## 1. 文档体系导航

开发前必须先读取相关文档，按以下优先级理解需求：

### 1.1 产品需求
- 总纲: `docs/01-Product/PRD.md` — 126 章目录索引
- 详文: `docs/PRD/{XX}-篇名.md` — 20 篇详细 PRD
- 路线图: `docs/01-Product/ROADMAP.md`
- UI/UX: `docs/01-Product/UIUX.md`

### 1.2 技术架构
- 技术架构: `docs/02-Architecture/TAD.md`
- 数据库设计: `docs/02-Architecture/DBD.md`
- API 设计: `docs/02-Architecture/API.md`
- AI Agent 设计: `docs/02-Architecture/Agent.md`
- 状态机: `docs/02-Architecture/StateMachine.md`
- Prompt 规范: `docs/02-Architecture/Prompt.md`
- 模型设计: `docs/02-Architecture/Model.md`
- 工作流: `docs/02-Architecture/Workflow.md`

### 1.3 开发规范
- 后端规范: `docs/03-Development/Backend.md`
- 前端规范: `docs/03-Development/Frontend.md`
- 编码规范: `docs/03-Development/CodingStyle.md`
- 测试规范: `docs/03-Development/Testing.md`

### 1.4 运维
- 部署指南: `docs/03-Development/Deploy.md`
- 用户指南: `docs/04-Operation/UserGuide.md`

---

## 2. 开发工作流

### 2.1 任务分解原则
1. **按篇分解**：按 PRD 的 20 篇，逐篇完成，当前篇完成才进入下一篇
2. **按层分解**：后端 API → 前端页面 → AI Agent，依次实现
3. **独立可验证**：每个子任务产出可独立编译/运行

### 2.2 子 Agent 派发规则

| 任务类型 | 子 Agent 类型 | 说明 |
|---------|--------------|------|
| 后端 API / Service | `general_purpose_task` | 实现 CRUD API + 业务逻辑 |
| 前端页面 / 组件 | `general_purpose_task` | 实现 UI 组件 + 页面路由 |
| AI Agent | `general_purpose_task` | 实现 Agent 管线 |
| 数据库 / 模型 | `general_purpose_task` | 实现 ORM 模型 + 迁移 |
| 代码搜索 / 审查 | `search` | 查找现有代码、审查质量 |
| Bug 调试 | `general_purpose_task` + TRAE-debugger skill | 复杂问题运行时调试 |

### 2.3 每个子任务的模板

```
## 子任务: {任务描述}

### 背景
{当前文档要求}

### 现有代码
{相关文件概览}

### 实施要求
{具体修改内容}

### 验证方式
{如何验证修改正确}
```

### 2.4 审核标准
每个子任务完成后必须检查：
1. ✅ 编译通过（`npx tsc --noEmit` / `python -c "from app.main import create_app"`）
2. ✅ 与文档需求一致
3. ✅ 符合编码规范（CodingStyle.md）
4. ✅ 前端增加新路由需在 App.tsx 注册
5. ✅ 后端增加新路由需在 main.py 注册

---

## 3. 关键技术约束

### 3.1 后端
- 框架: Python 3.11+ / FastAPI
- ORM: SQLAlchemy 2.0+（异步模式）
- 数据库: PostgreSQL 15+（开发用 SQLite）
- 路由前缀: `/api/v1/projects/{project_id}/...`
- 统一响应格式: `ApiResponse(data={...})`

### 3.2 前端
- 框架: React 18 + TypeScript + Vite
- UI 库: Ant Design 5.x
- 状态管理: Zustand
- 路由: React Router 6（嵌套路由）
- 样式: Tailwind CSS + Ant Design

### 3.3 数据层级
```
Project → Novel → Chapter → Scene → Panel → Shot/Bubble/Prompt → Image
```

### 3.4 路由结构
- 全局资产页面: `/characters`, `/novels`, `/scenes`, `/storyboard`, `/layout`
- 项目级页面: `/projects/:id/...`
- 所有资产页面统一布局：右上角 ProjectFilter + 搜索框

---

## 4. 项目进度跟踪

使用 TodoWrite 维护以下状态：

```
[prd-{篇号}] {篇名} — 状态: pending / in_progress / completed
├── backend  {API + Service + Model}
├── frontend {页面 + 组件 + Store}
└── review   {与文档对照 + 编译验证}
```

### 阶段检查点
1. **开始新篇前**：先读对应 PRD 详文 `docs/PRD/{XX}.md`
2. **实施中**：每完成一个子任务，做编译验证
3. **篇完成前**：对照 PRD 文档逐条检查功能，确认无遗漏
4. **进入下一篇前**：确保当前篇全部子任务通过审核

---

## 5. 故障处理

| 问题 | 处理方式 |
|------|---------|
| 编译错误 | 立即修复，不跳过 |
| 文档矛盾 | 以 PRD 详文优先，架构文档其次 |
| 子 Agent 产出质量差 | 打回重做，给出具体修改要求 |
| 路由 422/500 | 检查 FastAPI 参数校验和异常处理 |
| 前端 404 | 检查 App.tsx 路由注册 |

---

## 6. 质量门禁

每个篇完成后，必须逐项确认：

- [ ] 后端路由数增加（记录前后对比）
- [ ] 前端 TypeScript 编译 0 错误
- [ ] 所有 API 端点可调用（200 响应）
- [ ] 前端页面可渲染（无白屏/崩溃）
- [ ] PRD 功能点全部覆盖
- [ ] 与现有功能无冲突
