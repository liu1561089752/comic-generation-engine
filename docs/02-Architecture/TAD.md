# AI Webtoon Factory 技术架构文档（TAD）

> 版本：v1.0  
> 最后更新：2026-06-27  
> 状态：草案

---

## 1. 系统概述

### 1.1 项目定位

**AI Webtoon Factory** 是一个从小说导入到 Webtoon 导出的工业化 AI 生产管线。系统将传统韩漫工作室中编剧、分镜师、主笔、上色师、后期编辑等角色的工作流程全面 AI 化，使个人创作者能够独立完成从原始文本到可发布 Webtoon 的全部工序。

项目的核心价值主张是：**让一个人拥有一个韩漫工作室的生产力。**

### 1.2 核心架构原则

| 原则 | 说明 |
|------|------|
| **结构化优先** | 所有中间产物均为结构化数据（JSON），而非自然语言文本。Novel→Chapter→Scene→Panel→Shot→Bubble→Prompt→Image 每层数据严格建模，确保可解析、可追溯、可增量更新 |
| **模块化** | 系统由 10 个独立的 AI Agent 组成管线，每个 Agent 职责单一、输入输出明确、可独立替换/升级。前端模块与后端服务一一对应，便于分工开发 |
| **可追溯** | 每张生成图片均关联其完整的生产链路（原文段落→Scene→Panel→Prompt→模型参数→Seed），支持从成品图逆向追溯到原始文本和决策过程 |
| **可迭代** | 管线中的任意环节支持独立重做。修改某一 Scene 的文本后，下游 Panel/Shot/Prompt 自动标记为"需更新"，而非全部重新生成 |
| **AI 无关性** | 系统不绑定任何特定 AI 模型/服务。LLM 层兼容 OpenAI API 格式，生图层兼容 Stable Diffusion API 格式，用户可自由切换底层模型 |

### 1.3 系统边界

**覆盖范围：**
- 从 TXT/DOCX/Markdown 小说导入到 Webtoon 导出的全流程
- 支持 1:1.34（1080×1440+）标准 Webtoon 竖屏比例
- 支持 PNG/JPG/PSD/ZIP/长图等多种导出格式

**不覆盖范围：**
- AI 写小说（需外部导入文本源）
- 在线发布/分发平台
- 多人实时协同编辑（V1 为单用户模式）

---

## 2. 技术栈选型

### 2.1 后端

| 组件 | 选型 | 版本要求 | 选型理由 |
|------|------|----------|----------|
| 框架 | **FastAPI** | Python 3.11+ | 原生异步支持、自动 OpenAPI 文档生成、Pydantic 数据校验强类型 |
| ORM | **SQLAlchemy 2.0** | ≥2.0 | 异步查询支持、成熟稳定、与 Alembic 配合完成迁移管理 |
| 数据库迁移 | **Alembic** | ≥1.13 | SQLAlchemy 官方迁移工具，支持自动生成迁移脚本 |
| 任务队列 | **Celery** | ≥5.4 | 分布式任务调度成熟方案，支持优先级队列、定时任务、结果后端 |
| 消息代理 | **Redis** | ≥7.0 | 兼具 Celery Broker + Result Backend + 缓存三层职能 |
| API 风格 | RESTful + WebSocket | — | RESTful 用于 CRUD 操作，WebSocket 用于生图任务状态实时推送 |
| 异步 HTTP | **httpx** | ≥0.27 | 支持异步 HTTP 调用，用于访问 LLM/生图模型的 API 客户端 |

### 2.2 前端

| 组件 | 选型 | 版本要求 | 选型理由 |
|------|------|----------|----------|
| 框架 | **React 18 + TypeScript** | ≥18.0 | 类型安全、生态成熟、Hooks 范式适合复杂状态管理 |
| 构建工具 | **Vite** | ≥5.0 | 开发热更新速度快、构建产物体积小 |
| 状态管理 | **Zustand** | ≥4.5 | 轻量（<1KB）、无 Provider 嵌套、TypeScript 友好、中间件支持 |
| UI 组件库 | **Ant Design 5.x** | ≥5.0 | 企业级组件库、Table/Form/Modal 等开箱即用 |
| 样式方案 | **Tailwind CSS** | ≥3.4 | 原子化 CSS、设计系统一致性、配合 Ant Design 互补 |
| 漫画编辑器 | **Konva.js (react-konva)** | ≥9.3 | Canvas 操作库，支持图层、拖拽、缩放、变换，适合漫画编辑场景 |
| 图表 | **ECharts (echarts-for-react)** | ≥5.5 | 支持关系图（人物关系图）、热力图、统计图表 |
| 路由 | **React Router 6** | ≥6.22 | SPA 路由标准方案，支持嵌套路由、loader 数据预加载 |
| HTTP 客户端 | **Axios** | ≥1.6 | 请求/响应拦截器、取消请求、上传进度回调 |
| WebSocket | 原生 WebSocket / **Socket.IO 客户端** | — | 实时任务状态推送 |

### 2.3 数据库

| 组件 | 选型 | 说明 |
|------|------|------|
| 主库 | **PostgreSQL 15+** | 生产环境标准配置。利用 JSONB 字段存储结构化 AI 分析结果，GIN 索引支持全文搜索 |
| 开发备选 | **SQLite 3** | 开发/单机环境无需安装 PostgreSQL，SQLAlchemy 切换方言即可 |
| 缓存 | **Redis 7** | 任务队列（Celery Broker/Backend）、会话缓存、API 响应缓存、WebSocket Pub/Sub |
| 对象存储 | **MinIO**（生产） / **本地文件系统**（开发） | 图片文件存储，兼容 S3 API，支持分片上传 |

### 2.4 AI 模型

| 模型类别 | 兼容标准 | 可选实现 |
|----------|----------|----------|
| **LLM（大语言模型）** | OpenAI API 格式 | GPT-4 / GPT-4o / DeepSeek / 通义千问 / Claude（通过代理转换） |
| **生图模型** | Stable Diffusion API 格式 | SDXL / SD3 / 豆包 / Midjourney（通过 MJ-Proxy） / ComfyUI API |
| **Embedding 模型** | OpenAI Embedding API 格式 | text-embedding-3-small / bge-large-zh（本地部署） |
| **视觉检测模型** | — | YOLOv8 / Grounding DINO（角色检测、气泡 OCR 检测） |

---

## 3. 系统架构图

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Frontend (React 18 + TypeScript)                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │  工作台   │ │ 小说管理 │ │ 人物IP   │ │ 分镜中心 │ │ 版式中心 │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │文本中心  │ │Prompt中心│ │生图中心  │ │质量控制 │ │ 导出中心 │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────────────┐  │
│  │ 模型中心 │ │ 资源中心 │ │ 系统管理 │ │  漫画编辑器 (Konva.js) │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────────────┘  │
│                          │ HTTP REST / WebSocket                      │
├──────────────────────────┼───────────────────────────────────────────┤
│                    Backend (FastAPI + Python 3.11+)                    │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │                     API 路由层 (Routers)                       │   │
│  │  /api/v1/novels    /api/v1/characters    /api/v1/scenes       │   │
│  │  /api/v1/panels    /api/v1/shots         /api/v1/bubbles     │   │
│  │  /api/v1/prompts   /api/v1/generation    /api/v1/qa          │   │
│  │  /api/v1/export    /api/v1/resources     /api/v1/models      │   │
│  │  /api/v1/plugins   /api/v1/system        /ws/task/{id}       │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                             │                                         │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │                  服务层 (Services / Use Cases)                 │   │
│  │  NovelService | CharacterService | SceneService | PanelService│   │
│  │  ShotService  | BubbleService  | PromptService | ImageService  │   │
│  │  ExportService | QAService | ModelService | PluginService    │   │
│  │  TaskService (Celery 任务编排)                                │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                             │                                         │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │                   AI Agent 层 (10 Agents)                     │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐    │   │
│  │  │文本清洗 │ │剧情分析 │ │语义切句 │ │分镜规划 │ │镜头规划 │    │   │
│  │  │ Agent  │ │ Agent  │ │ Agent  │ │ Agent  │ │ Agent  │    │   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘    │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐    │   │
│  │  │版式规划 │ │气泡规划 │ │Prompt  │ │一致性  │ │质量评分 │    │   │
│  │  │ Agent  │ │ Agent  │ │生成Agent│ │检查Agent│ │ Agent  │    │   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘    │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                             │                                         │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │               AI 模型适配层 (Model Adapters)                   │   │
│  │  ┌─────────────────┐  ┌────────────────────────────────┐     │   │
│  │  │ LLMAdapter       │  │ ImageGenAdapter               │     │   │
│  │  │ ├─ OpenAIAdapter │  │ ├─ SDAPIAdapter               │     │   │
│  │  │ ├─ DeepSeekAdapter│  │ ├─ MidjourneyAdapter          │     │   │
│  │  │ └─ CustomAdapter │  │ └─ ComfyUIAdapter             │     │   │
│  │  └─────────────────┘  └────────────────────────────────┘     │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                             │                                         │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │                 数据访问层 (Repositories)                      │   │
│  │  NovelRepo | ChapterRepo | SceneRepo | PanelRepo | ShotRepo   │   │
│  │  BubbleRepo | PromptRepo | ImageRepo | CharacterRepo | ...    │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                             │                                         │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │              Celery 任务队列 (异步处理引擎)                    │   │
│  │  ├─ ai_generation_queue (AI 生图任务, 限并发 2-4)            │   │
│  │  ├─ ai_analysis_queue   (AI 分析任务, 限并发 8-16)           │   │
│  │  ├─ export_queue        (导出任务, 限并发 1-2)               │   │
│  │  └─ default_queue       (其他后台任务)                        │   │
│  └───────────────────────────────────────────────────────────────┘   │
├──────────────────────────┼───────────────────────────────────────────┤
│          ┌────────────────┴────────────────┐                        │
│          │        PostgreSQL 15+            │                        │
│          │  (Novel, Chapter, Scene, Panel,   │                        │
│          │   Shot, Bubble, Prompt, Image,     │                        │
│          │   Character, Worldview, Settings)  │                        │
│          └────────────────┬─────────────────┘                        │
│          ┌────────────────┴────────────────┐                        │
│          │        Redis 7 (Cache + Queue)    │                        │
│          └────────────────┬─────────────────┘                        │
│          ┌────────────────┴────────────────┐                        │
│          │  MinIO / 本地文件系统 (图片存储)   │                        │
│          └─────────────────────────────────┘                        │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. 模块架构（10 个 AI Agent）

### 4.1 Agent 管线总览

10 个 AI Agent 按以下顺序组成串行管线，每个 Agent 依赖前一个 Agent 的输出：

```
小说文本
   │
   ▼
┌──────────────┐
│ ① 文本清洗   │ ─── 标准化、去噪、格式统一
└──────┬───────┘
       ▼
┌──────────────┐
│ ② 剧情分析   │ ─── 提取 Scene 结构
└──────┬───────┘
       ▼
┌──────────────┐
│ ③ 语义切句   │ ─── Scene → Panel 拆分
└──────┬───────┘
       ▼
┌──────────────┐
│ ④ 分镜规划   │ ─── Panel → 视觉分镜方案
└──────┬───────┘
       ▼
┌──────────────┐
│ ⑤ 镜头规划   │ ─── 镜头类型、构图、景别
└──────┬───────┘
       ▼
┌──────────────┐
│ ⑥ 版式规划   │ ─── Panel → 页面布局
└──────┬───────┘
       ▼
┌──────────────┐
│ ⑦ 气泡规划   │ ─── 文本 → 气泡列表
└──────┬───────┘
       ▼
┌──────────────┐
│ ⑧ Prompt生成 │ ─── 10 层 Prompt 组装
└──────┬───────┘
       ▼
   ┌─────┴─────┐
   │           │
   ▼           ▼
┌────────┐ ┌────────┐
│⑨ 一致性│ │⑩ 质量  │ ← 图片生成后触发
│ 检查   │ │ 评分   │
└────────┘ └────────┘
```

### 4.2 Agent 详细定义

#### Agent ①：文本清洗 Agent

| 项目 | 内容 |
|------|------|
| **ID** | text_cleaner |
| **职责** | 对导入的原始小说文本进行标准化预处理，去除格式噪声，输出结构清晰的纯文本 |
| **输入** | 原始文本（TXT/DOCX/Markdown 格式，含可能的乱码、多余空行、特殊字符、错误的编码） |
| **输出** | `{\n  "chapter_title": "第X章 章名",\n  "clean_text": "清洗后的纯文本内容",\n  "paragraphs": ["段落1", "段落2", ...],\n  "meta": {\n    "word_count": 5000,\n    "paragraph_count": 30,\n    "has_dialogue": true\n  }\n}` |
| **处理规则** | 1. 移除多余空行（保留段落间距）<br>2. 统一全角/半角符号<br>3. 修正常见编码错误<br>4. 识别并保留章节标题<br>5. 检测对话引号格式并统一<br>6. 输出结构化段落列表 |
| **LLM 调用时机** | 每章一次。若文本很短（<500 字），可用规则引擎替代 LLM |

#### Agent ②：剧情分析 Agent

| 项目 | 内容 |
|------|------|
| **ID** | story_analyzer |
| **职责** | 对章节文本进行深度语义理解，提取剧情结构要素，识别场景边界，生成 Scene 结构列表 |
| **输入** | 清洗后的章节文本 + 段落列表（来自 Agent ①）<br>可选：已存在的世界观设定信息 |
| **输出** | `{\n  "chapter_id": "uuid",\n  "scenes": [\n    {\n      "scene_number": 1,\n      "summary": "主角在咖啡馆与神秘人见面",\n      "start_paragraph": 3,\n      "end_paragraph": 15,\n      "location": "都市咖啡馆",\n      "time": "傍晚",\n      "characters": ["主角", "神秘人"],\n      "emotion": "紧张/悬疑",\n      "plot_points": ["冲突引入", "信息交换"]\n    }\n  ],\n  "plot_structure": {\n    "beginning": "章节开头摘要",\n    "development": "发展部分摘要",\n    "climax": "高潮部分摘要",\n    "ending": "结局部分摘要"\n  }\n}` |
| **处理规则** | 1. 按时间/地点切换识别场景边界<br>2. 提取每个 Scene 的人物、地点、时间、情绪<br>3. 识别情节节点（开端/发展/高潮/结局）<br>4. 每个 Scene 关联对应的原文段落范围 |
| **LLM 调用时机** | 每章一次。单次 Prompt 包含完整章节，利用 LLM 的上下文理解能力 |

#### Agent ③：语义切句 Agent

| 项目 | 内容 |
|------|------|
| **ID** | semantic_splitter |
| **职责** | 将每个 Scene 的文本按语义粒度切分为 Panel（画格）级别的文本片段。每个 Panel 对应一个独立的漫画画格（单幅画面） |
| **输入** | Scene 对象（含 Scene 文本、人物、地点、情绪）|
| **输出** | `{\n  "scene_id": "uuid",\n  "panels": [\n    {\n      "panel_number": 1,\n      "text": "主角推开咖啡馆的门，铃声响起",\n      "paragraph_ref": 5,\n      "characters": ["主角"],\n      "emotion": "平静",\n      "panel_type": "action"\n    },\n    {\n      "panel_number": 2,\n      "text": "\"你终于来了。\"神秘人说。",\n      "paragraph_ref": 6,\n      "characters": ["主角", "神秘人"],\n      "emotion": "紧张",\n      "panel_type": "dialogue"\n    }\n  ]\n}` |
| **切句策略** | 1. **对话独立成格**：每句对话独立为一个 Panel<br>2. **动作拆解**：连续动作拆分为多个 Panel（推门→走进→坐下）<br>3. **描述合并**：同一场景的环境描述与首个动作合并<br>4. **情绪转折点**：情绪变化处切换 Panel<br>5. 每个 Panel 文本建议 10-50 字（单幅画面的合理信息量） |
| **LLM 调用时机** | 每个 Scene 一次。对较长的 Scene（>2000 字），可分批次处理 |

#### Agent ④：分镜规划 Agent

| 项目 | 内容 |
|------|------|
| **ID** | storyboard_planner |
| **职责** | 将 Panel 文本转化为视觉分镜方案，确定每个 Panel 的核心视觉元素、构图思路和画面描述 |
| **输入** | Panel 对象列表（文本、人物、动作、情绪）<br>场景氛围描述 |
| **输出** | `{\n  "panel_id": "uuid",\n  "shot_description": "主角半身正面，手持咖啡杯，目光警惕地看向画面右侧",\n  "composition": "三分法构图，主体在左1/3处",\n  "focus": "主角的面部表情",\n  "background": "咖啡馆模糊背景，暖色调灯光",\n  "key_elements": ["咖啡杯", "蒸汽", "窗外的雨"],\n  "color_palette": ["暖橙", "深棕", "冷蓝"],\n  "mood": "紧张中带着期待"\n}` |
| **处理规则** | 1. 基于 Panel 文本生成视觉描述，而非直接输出 SD Prompt<br>2. 考虑前后 Panel 的视觉连续性<br>3. 高潮/关键剧情 Panel 提供详细描述，过渡 Panel 从简 |
| **LLM 调用时机** | 每 5-10 个 Panel 批量处理一次（保持上下文连续性） |

#### Agent ⑤：镜头规划 Agent

| 项目 | 内容 |
|------|------|
| **ID** | camera_planner |
| **职责** | 为每个 Panel 确定具体的镜头类型、景别、运镜方式和视角 |
| **输入** | Panel 对象 + Scene 情绪 + 前后 Panel 的镜头信息 |
| **输出** | `{\n  "panel_id": "uuid",\n  "camera_type": "medium_shot",        // 远景/中景/近景/特写/POV\n  "camera_angle": "eye_level",        // 平视/俯拍/仰拍/侧面\n  "camera_movement": "fixed",         // 固定/平移/推进/拉远\n  "shot_size": "medium",              // extreme_long / long / medium / close / extreme_close\n  "composition_rule": "rule_of_thirds",\n  "transition_from_prev": "cut",      // cut / fade / dissolve / match_cut\n  "rationale": "使用中景+平视展示对话双方，营造平等对话氛围"\n}` |
| **镜头规则** | 1. 对话场景：正反打（shot-reverse-shot），中景为主<br>2. 动作场景：多角度切换，远景+特写结合<br>3. 情绪场景：特写+俯拍/仰拍强化情绪<br>4. 避免连续 3 个同类型镜头 |
| **LLM 调用时机** | 每 5-10 个 Panel 批量处理一次 |

#### Agent ⑥：版式规划 Agent

| 项目 | 内容 |
|------|------|
| **ID** | layout_planner |
| **职责** | 将 Panel 序列编排为 Webtoon 页面布局，确定每页包含的 Panel 数量、排列方式和相对比例 |
| **输入** | Panel 序列（长度不限）<br>节奏标记（紧张/舒缓/高潮）<br>可用模板列表 |
| **输出** | `{\n  "pages": [\n    {\n      "page_number": 1,\n      "layout_template": "panel_3_split",\n      "panels": [\n        {"panel_id": "uuid", "position": {"x": 0, "y": 0, "w": 1, "h": 0.4}},\n        {"panel_id": "uuid", "position": {"x": 0, "y": 0.4, "w": 1, "h": 0.3}},\n        {"panel_id": "uuid", "position": {"x": 0, "y": 0.7, "w": 1, "h": 0.3}}\n      ],\n      "page_intent": "对话推进"\n    }\n  ],\n  "pacing_analysis": {\n    "total_pages": 6,\n    "climax_page": 5,\n    "panel_density": "moderate"\n  }\n}` |
| **版式规则** | 1. 高潮场景使用大格/跨格/整页提升视觉冲击<br>2. 对话场景使用 3-4 格均分布局，节奏均匀<br>3. 过渡场景使用 5-6 格紧凑布局<br>4. 每页建议 3-6 个 Panel |
| **LLM 调用时机** | 每 30-50 个 Panel（约 1 话）集中处理一次 |

#### Agent ⑦：气泡规划 Agent

| 项目 | 内容 |
|------|------|
| **ID** | bubble_planner |
| **职责** | 从原文中识别对话、旁白、内心独白三种文本类型，生成气泡列表，并为每个气泡建议放置位置 |
| **输入** | Panel 原始文本 + Panel 分镜信息（人物位置） |
| **输出** | `{\n  "panel_id": "uuid",\n  "bubbles": [\n    {\n      "bubble_id": "uuid",\n      "type": "dialogue",          // narration / dialogue / thinking\n      "text": "你终于来了。",\n      "speaker": "神秘人",\n      "position_suggestion": "right",  // left / right / top / center\n      "style_ref": "speech_bubble_default",\n      "order": 1,                  // 阅读顺序\n      "source_text_id": "uuid"     // 关联的原文 ID\n    }\n  ]\n}` |
| **识别规则** | 1. 引号内容 → Dialogue（对白）<br>2. 含"心想""想道""觉得"等 → Thinking（内心独白）<br>3. 其余描述性文本 → Narration（旁白）<br>4. 旁白框默认左上角，对白框默认居右，内心独白默认左中 |
| **LLM 调用时机** | 每 10-20 个 Panel 批量处理一次 |

#### Agent ⑧：Prompt 生成 Agent

| 项目 | 内容 |
|------|------|
| **ID** | prompt_generator |
| **职责** | 聚合所有上游数据（角色、场景、动作、镜头、构图、画风、气泡等），组装为 10 层结构化 Prompt，供生图模型使用 |
| **输入** | - 角色数据（人物 IP 中心）<br>- 场景数据（世界观资产库）<br>- 动作/情绪（分镜数据）<br>- 镜头/构图（镜头规划数据）<br>- 版式数据（版式规划数据）<br>- 气泡数据<br>- 画风模板（风格模板库）<br>- Prompt 模板（Prompt 中心） |
| **输出** | `{\n  "panel_id": "uuid",\n  "prompt_version": "v1.2",\n  "layers": {\n    "1_character": "A young man with black hair and brown eyes, wearing a black leather jacket and white shirt",\n    "2_environment": "A cozy coffee shop at evening, warm ambient lighting, rain outside the window",\n    "3_action": "Sitting at a table, holding a coffee cup, looking cautiously to the right",\n    "4_emotion": "Nervous yet expectant, slight frown, tense shoulders",\n    "5_camera": "Medium shot, eye-level angle, fixed camera",\n    "6_lighting": "Warm ambient lighting from overhead lamps, cool blue fill from window",\n    "7_composition": "Rule of thirds, subject on left third, depth with blurred background",\n    "8_webtoon_style": "Webtoon style, semi-realistic, clean lines, cell shading, high contrast",\n    "9_bubble": "Empty speech bubble on the right side, with tail pointing left",\n    "10_negative": "nsfw, low quality, blurry, distorted hands, extra fingers, bad anatomy"\n  },\n  "merged_prompt": "（所有层合并后的完整 Prompt 字符串）",\n  "negative_prompt": "（第 10 层内容）",\n  "params": {\n    "width": 1080,\n    "height": 1440,\n    "cfg_scale": 7.5,\n    "steps": 30,\n    "seed": -1\n  }\n}` |
| **组装规则** | 1. 先从模板库加载 10 层 Prompt 模板<br>2. 逐层用实际数据替换模板中的 `{{变量}}`<br>3. 空层自动跳过，不注入空白内容<br>4. 合并后的 Prompt 控制在 SD 模型的 token 限制内（建议 < 150 tokens for CLIP）<br>5. 负向 Prompt 为系统预设 + 用户自定义的合并结果 |
| **LLM 调用时机** | 不需要 LLM。此 Agent 本质是模板引擎 + 数据聚合器，纯代码逻辑实现 |

#### Agent ⑨：一致性检查 Agent

| 项目 | 内容 |
|------|------|
| **ID** | consistency_checker |
| **职责** | 对生成的图片进行自动视觉检测，逐项比对角色外观特征与人物 IP 设定的一致性 |
| **输入** | - 生成的 Panel 图片（Base64 或文件路径）<br>- 该 Panel 中应出现的角色 ID 列表<br>- 人物 IP 中心的特征设定（发色、发型、瞳色、肤色、服装） |
| **输出** | `{\n  "panel_id": "uuid",\n  "checks": [\n    {\n      "character_id": "uuid",\n      "character_name": "主角",\n      "dimensions": [\n        {"dimension": "hair_color", "expected": "黑色", "detected": "黑色", "match": true, "confidence": 95},\n        {"dimension": "hair_style", "expected": "短发", "detected": "短发", "match": true, "confidence": 90},\n        {"dimension": "eye_color", "expected": "棕色", "detected": "黑色", "match": false, "confidence": 85, "note": "检测为黑色，与设定棕色不符"},\n        {"dimension": "clothing", "expected": "黑色皮夹克", "detected": "黑色夹克", "match": true, "confidence": 80}\n      ],\n      "overall_match": false,\n      "match_score": 0.75\n    }\n  ],\n  "passed": false\n}` |
| **技术方案** | 1. 使用 YOLOv8 + Face Recognition 检测图片中的人脸<br>2. 检测到人脸后，提取各特征维度的视觉特征<br>3. 与设定值进行语义/特征比对<br>4. 低于阈值的维度标记为不一致 |
| **执行时机** | 图片生成完成后自动触发，异步执行 |

#### Agent ⑩：质量评分 Agent

| 项目 | 内容 |
|------|------|
| **ID** | quality_scorer |
| **职责** | 对生成的图片进行多维度质量评估，输出量化评分报告，辅助用户筛选最佳候选图 |
| **输入** | 生成的 Panel 图片 |
| **输出** | `{\n  "panel_id": "uuid",\n  "scores": [\n    {"dimension": "composition", "score": 85, "comment": "构图合理，主体突出"},\n    {"dimension": "character_integrity", "score": 70, "comment": "手部略有变形"},\n    {"dimension": "lighting", "score": 90, "comment": "光影层次丰富"},\n    {"dimension": "detail", "score": 75, "comment": "背景细节略少"},\n    {"dimension": "style_consistency", "score": 88, "comment": "画风较一致"}\n  ],\n  "overall_score": 81.6,\n  "defects": [\n    {"type": "hand_deformity", "severity": "minor", "location": "bottom_right"}\n  ],\n  "recommendation": "acceptable"  // rejected / acceptable / recommended / best\n}` |
| **评分维度** | 构图质量、角色完整性（手指/面部无变形）、光影质量、细节丰富度、画风一致性 |
| **执行时机** | 图片生成完成后自动触发，与一致性检查 Agent 并行执行 |

---

## 5. 数据流设计

### 5.1 核心数据模型层次

系统以**严格分层的数据结构**组织所有漫画生产数据：

```
Novel（小说）
  └── Chapter（章节）
        └── Scene（场景）
              └── Panel（画格）
                    └── Shot（镜头描述）
                          └── Bubble（气泡）
                                └── Prompt（生成提示词）
                                      └── Image（生成图片）
```

### 5.2 完整数据流

```
【导入阶段】
TXT/DOCX/MD 文件
  │  (解析)
  ▼
Novel 对象 ───────────────────────────────────── (novels 表)
  │
  │ 导入后自动创建 Chapters
  ▼
Chapter[] ────────────────────────────────────── (chapters 表)

【文本处理管线】
Chapter.raw_text
  │
  │── Agent ① 文本清洗 ───────────────────────── 更新 Chapter.clean_text
  │
  │── Agent ② 剧情分析 ───────────────────────── 创建 Scene[]
  │       场景边界识别、情节节点提取
  │
  │── Agent ③ 语义切句 ──────────────────────── 创建 Panel[]
  │       每个 Scene 拆分为 N 个 Panel
  │
  │── Agent ④ 分镜规划 ──────────────────────── 更新 Panel.shot_description
  │       视觉描述、构图、关键元素
  │
  │── Agent ⑤ 镜头规划 ──────────────────────── 更新 Panel.camera_data
  │       镜头类型、景别、视角、运镜
  │
  │── Agent ⑥ 版式规划 ──────────────────────── 创建 Page[] + 更新 Panel.position
  │       Panel → 页面布局编排
  │
  │── Agent ⑦ 气泡规划 ──────────────────────── 创建 Bubble[]
  │       从原文识别对话/旁白/内心独白

【Prompt + 生图管线】
  │
  │── Agent ⑧ Prompt 生成 ───────────────────── 创建 Prompt (10层结构)
  │      聚合角色/场景/动作/镜头/画风等数据
  │
  │── 提交生图任务 ──────────────────────────── Celery 任务入队
  │      调用 Stable Diffusion API
  │
  │── 生图完成 ──────────────────────────────── 创建 Image[]
  │      生成候选图（通常每 Panel 4-8 张）

【质量检测管线】
  │
  │── Agent ⑨ 一致性检查 ───────────────────── 创建 ConsistencyReport
  │      角色特征逐维度比对
  │
  │── Agent ⑩ 质量评分 ─────────────────────── 创建 QualityReport
  │      多维度量化评分
  │
  │── 人工审核 ──────────────────────────────── 用户选择最佳图
  │      打回重生成 或 确认通过

【导出管线】
  │
  │── 漫画编辑器（手动微调）
  │      Konva.js Canvas 编辑
  │
  │── 导出
       PNG / JPG / PSD / ZIP / 长图
```

### 5.3 状态流转

```
Chapter     : 待处理 → 已清洗 → 已分析 → 已完成
Scene       : 待拆解 → 已拆解 → 已分镜 → 已出图 → 已完成
Panel       : 待处理 → 已分镜 → 已设定镜头 → 已排版 → 已生成 → 已审核
Page        : 待排版 → 已排版 → 已审核
Bubble      : 待识别 → 已识别 → 已确认
Prompt      : 待生成 → 已生成 → 已使用
Image       : 待生成 → 生成中 → 已生成 → 已通过 / 已拒绝
Task        : 排队中 → 进行中 → 已完成 / 失败 / 已取消
```

### 5.4 关键数据流原则

1. **无损追溯**：每个 Image 持有 `panel_id → scene_id → chapter_id → novel_id` 完整链路
2. **增量更新**：修改上游数据（如 Scene 文本）后，下游数据标记为 `stale`，但不自动删除
3. **版本控制**：Prompt、Image、气泡等关键资源支持版本管理，支持回退到历史版本
4. **批量处理**：AI Agent 支持逐 Panel、逐 Scene、逐 Chapter 三种粒度处理，适应不同场景

---

## 6. 部署架构

### 6.1 Docker 容器化方案（生产环境）

```
┌─────────────────────────────────────────────────────────────────┐
│                          Docker Compose                          │
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐        │
│  │  nginx:alpine │   │  frontend    │   │  backend     │        │
│  │  (反向代理)   │──▶│  (React SPA) │   │  (Uvicorn)   │        │
│  │  端口 80/443  │   │  :3000       │   │  :8000       │        │
│  └──────────────┘   └──────────────┘   └──────┬───────┘        │
│                                                │                │
│  ┌──────────────────────┐                      │                │
│  │  celery_worker       │◀─────────────────────┘                │
│  │  (AI 任务处理)       │                                       │
│  │  ├─ ai_generation    │                                       │
│  │  ├─ ai_analysis      │                                       │
│  │  ├─ export_worker    │                                       │
│  │  └─ default_worker   │                                       │
│  └──────────────────────┘                                       │
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐        │
│  │  postgres:15  │   │  redis:7     │   │  minio       │        │
│  │  :5432        │   │  :6379       │   │  :9000       │        │
│  └──────────────┘   └──────────────┘   └──────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 开发环境配置

开发环境使用简化配置，降低上手门槛：

| 组件 | 开发环境方案 |
|------|-------------|
| 数据库 | SQLite（`app.db`），无需安装 PostgreSQL |
| 缓存 | Redis 可选，Celery 使用 `Eager` 模式（同步执行任务） |
| 文件存储 | 本地 `./data/storage/` 目录 |
| 后端运行 | `uvicorn app.main:app --reload --port 8000` |
| 前端运行 | `npm run dev`（Vite HMR 开发服务器） |
| AI 模型 | 读取环境变量中的 API Key 连接外部服务 |

### 6.3 环境变量清单

```bash
# ============================================
# AI Webtoon Factory 环境变量清单
# ============================================

# ---- 通用 ----
APP_ENV=development                     # development / production / testing
APP_SECRET_KEY=change-me-to-random-key   # JWT 签名密钥（生产环境必须更换）
APP_DEBUG=true                           # 是否开启调试模式
APP_LOG_LEVEL=INFO                       # DEBUG / INFO / WARNING / ERROR

# ---- 数据库 ----
# 生产环境（PostgreSQL）
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/webtoon_factory
# 开发环境（SQLite）
# DATABASE_URL=sqlite+aiosqlite:///./data/app.db

# ---- Redis / Celery ----
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# ---- 文件存储 ----
STORAGE_BACKEND=local                    # local / minio
STORAGE_LOCAL_PATH=./data/storage
# MinIO 配置（当 STORAGE_BACKEND=minio 时）
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=webtoon-images

# ---- AI 模型 ----
# LLM 配置（兼容 OpenAI API 格式）
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
LLM_MODEL=gpt-4-turbo
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.7

# 生图模型配置（兼容 Stable Diffusion API 格式）
IMAGE_API_BASE=http://localhost:7860/sdapi/v1
IMAGE_API_KEY=
IMAGE_MODEL=sd_xl_base_1.0
IMAGE_DEFAULT_WIDTH=1080
IMAGE_DEFAULT_HEIGHT=1440
IMAGE_DEFAULT_STEPS=30
IMAGE_DEFAULT_CFG_SCALE=7.5
IMAGE_MAX_CONCURRENT=2                # 最大并发生图数

# 备用生图模型（可选）
# IMAGE_API_BASE_2=https://api.midjourney.com
# IMAGE_API_KEY_2=mj-xxxxxxxxx

# ---- CORS ----
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# ---- 导出 ----
EXPORT_TEMP_DIR=./data/exports
EXPORT_MAX_FILE_SIZE_MB=500
```

### 6.4 Docker Compose 示例

```yaml
# docker-compose.yml（生产环境参考）
version: "3.9"
services:
  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    volumes:
      - ./data/storage:/app/data/storage

  celery_worker:
    build: ./backend
    command: celery -A app.tasks worker -l info -Q ai_generation,ai_analysis,export,default -c 4
    env_file: .env
    depends_on:
      - backend
      - redis
    volumes:
      - ./data/storage:/app/data/storage

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: webtoon_factory
      POSTGRES_USER: webtoon
      POSTGRES_PASSWORD: secure_password
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U webtoon"]
      interval: 5s

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - miniodata:/data

volumes:
  pgdata:
  miniodata:
```

---

## 7. 安全性设计

### 7.1 API 认证

| 机制 | 说明 |
|------|------|
| **JWT Token** | 所有 API 请求（除登录/注册外）需在 Header 中携带 `Authorization: Bearer <token>` |
| **Token 有效期** | Access Token 有效期 2 小时，Refresh Token 有效期 7 天 |
| **Token 存储** | 前端存储在 httpOnly Cookie（非 localStorage），防范 XSS 窃取 |
| **密码存储** | 使用 bcrypt（`passlib` 库）哈希存储，不使用明文 |
| **API 限流** | 登录接口限流 5 次/分钟，通用 API 限流 120 次/分钟（基于 Redis） |

JWT Payload 结构：
```json
{
  "sub": "user_uuid",
  "exp": 1719500000,
  "iat": 1719496400,
  "type": "access"
}
```

### 7.2 文件上传安全

| 措施 | 说明 |
|------|------|
| **类型白名单** | 仅允许：`.txt`, `.docx`, `.md`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.zip` |
| **MIME 校验** | 除后缀名检查外，使用 `python-magic` 库校验文件 Magic Bytes |
| **大小限制** | 单文件 ≤ 50MB（小说）/ ≤ 10MB（图片） |
| **文件名安全** | 上传后文件重命名为 UUID，原始文件名存储在数据库 |
| **存储隔离** | 上传文件存储在应用数据目录内，不暴露至 Web 可访问路径（通过 API 代理访问） |

### 7.3 API Key 安全存储

| 措施 | 说明 |
|------|------|
| **加密存储** | LLM/生图模型的 API Key 在数据库中使用 AES-256-GCM 加密存储（`cryptography` 库） |
| **日志脱敏** | 所有日志输出前自动过滤 `api_key`、`secret`、`password`、`token` 字段，替换为 `***` |
| **内存安全** | API Key 在 Python 中仅加载到局部变量，使用后立即释放；禁止全局缓存 |
| **前端隔离** | API Key 仅在后端使用，前端永不接触原始 Key |

### 7.4 其他安全措施

- **HTTPS 强制**：生产环境 Nginx 配置 HTTP→HTTPS 重定向
- **CORS 白名单**：仅允许配置的前端域名访问
- **SQL 注入防护**：使用 SQLAlchemy ORM 参数化查询，禁止原生 SQL 拼接
- **依赖安全扫描**：CI 流水线集成 `pip-audit` 和 `npm audit`

---

## 8. 性能设计

### 8.1 数据库索引策略

```sql
-- novels 表
CREATE INDEX idx_novels_created_at ON novels(created_at DESC);
CREATE INDEX idx_novels_status ON novels(status);

-- chapters 表
CREATE INDEX idx_chapters_novel_id ON chapters(novel_id);
CREATE INDEX idx_chapters_status ON chapters(status);
CREATE INDEX idx_chapters_novel_status ON chapters(novel_id, status);

-- scenes 表
CREATE INDEX idx_scenes_chapter_id ON scenes(chapter_id);
CREATE INDEX idx_scenes_status ON scenes(status);
CREATE INDEX idx_scenes_chapter_status ON scenes(chapter_id, status);

-- panels 表
CREATE INDEX idx_panels_scene_id ON panels(scene_id);
CREATE INDEX idx_panels_status ON panels(status);
CREATE INDEX idx_panels_scene_status ON panels(scene_id, status);
CREATE INDEX idx_panels_page_id ON panels(page_id);

-- pages 表
CREATE INDEX idx_pages_chapter_id ON pages(chapter_id);
CREATE INDEX idx_pages_status ON pages(status);

-- images 表（高频查询）
CREATE INDEX idx_images_panel_id ON images(panel_id);
CREATE INDEX idx_images_status ON images(status);
CREATE INDEX idx_images_generated_at ON images(generated_at DESC);

-- prompts 表
CREATE INDEX idx_prompts_panel_id ON prompts(panel_id);
CREATE INDEX idx_prompts_version ON prompts(panel_id, version DESC);

-- bubbles 表
CREATE INDEX idx_bubbles_panel_id ON bubbles(panel_id);

-- tasks 表（高频写入+查询）
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_created_at ON tasks(created_at DESC);
CREATE INDEX idx_tasks_type_status ON tasks(task_type, status);

-- 全文搜索（PostgreSQL）
CREATE INDEX idx_chapters_fulltext ON chapters USING GIN(to_tsvector('simple', clean_text));
```

### 8.2 图片缓存策略

| 层级 | 策略 | 说明 |
|------|------|------|
| **浏览器缓存** | `Cache-Control: max-age=86400` + ETag | 已确认的 Panel 图片可缓存 24 小时 |
| **CDN 缓存** | 可选 Cloudflare / 自建 Nginx 缓存 | 生产环境启用，缓存 7 天 |
| **后端内存缓存** | Redis 缓存热门图片的缩略图（Base64 或 bytes） | 列表页/缩略图场景，缓存 1 小时 |
| **本地磁盘缓存** | 生成图片写入 `./data/storage/cache/` | LRU 淘汰策略，最大 50GB |
| **预加载缓存** | 用户浏览当前 Panel 时，预加载前后 3 个 Panel | 前端提前请求，减少等待 |

**缩略图生成**：
- 列表页缩略图：300px 宽，WebP 格式，质量 80%
- 编辑预览图：1080px 宽，WebP 格式，质量 90%
- 导出原图：原始分辨率，PNG 无损

### 8.3 并发控制

| 场景 | 控制策略 | 配置 |
|------|----------|------|
| **AI 生图任务** | Celery 队列限流 + 信号量 | 最大并发 2-4（取决于 GPU/API 配额） |
| **AI 分析任务** | Celery 队列限流 | 最大并发 8-16（轻量任务，主要受 LLM API 限制） |
| **导出任务** | 单队列单 Worker | 最大并发 2 |
| **API 请求** | 令牌桶限流（Redis 实现） | 全局 120 req/min，登录 5 req/min |
| **数据库连接池** | SQLAlchemy 连接池 | 最小 5，最大 20（生产）；SQLite 无需 |

**Celery 队列配置**：
```python
# 队列定义
CELERY_TASK_QUEUES = (
    Queue('ai_generation', Exchange('ai_generation'), routing_key='ai_generation'),
    Queue('ai_analysis', Exchange('ai_analysis'), routing_key='ai_analysis'),
    Queue('export', Exchange('export'), routing_key='export'),
    Queue('default', Exchange('default'), routing_key='default'),
)

# 优先级：ai_generation > ai_analysis > export > default
CELERY_TASK_DEFAULT_PRIORITY = 5  # 1-10, 10=最高
```

### 8.4 前端性能优化

| 策略 | 措施 |
|------|------|
| **虚拟滚动** | 漫画 Panel 列表使用 `react-virtual` / `@tanstack/react-virtual`，仅渲染可视区域 DOM 节点 |
| **图片懒加载** | 使用 `IntersectionObserver`，图片进入视口前 200px 开始加载 |
| **代码分割** | React.lazy + Suspense 按页面路由拆分 chunk，漫画编辑器单独打包 |
| **状态更新节流** | WebSocket 推送的任务状态更新，使用 `requestAnimationFrame` 合并渲染（30fps 限制） |
| **Web Worker** | 图片 Base64 编码/解码、缩略图生成在 Web Worker 中执行 |
| **缓存优先** | 使用 Zustand 持久化中间件 + IndexedDB 缓存大型数据集（Scene/Panel 列表） |

---

## 9. 可扩展性设计

### 9.1 插件系统接口设计

#### 插件定义规范

插件是一个包含 `plugin.json` 清单文件 + Python 代码的目录包：

```json
{
  "id": "com.example.my_plugin",
  "name": "示例插件",
  "version": "1.0.0",
  "min_app_version": "1.0.0",
  "author": "开发者",
  "description": "插件功能描述",
  "entry": "main.py",
  "hooks": [
    "on_panel_generated",
    "on_task_completed"
  ],
  "permissions": [
    "read:panel",
    "write:image"
  ]
}
```

#### 核心 Hook 接口

```python
# 插件基础类
class PluginBase(ABC):
    """所有插件必须实现的基类"""

    @abstractmethod
    async def initialize(self, context: PluginContext) -> None:
        """插件初始化，在应用启动时调用"""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """插件卸载时调用"""
        pass

    @property
    @abstractmethod
    def manifest(self) -> PluginManifest:
        """返回插件清单"""
        pass

# 预定义 Hook 接口
class PluginHooks:
    """插件可接入的 Hook 点"""

    # ---- Agent 管线 Hook ----
    async def before_text_clean(self, raw_text: str) -> str: ...
    async def after_text_clean(self, clean_text: str) -> str: ...
    async def before_story_analysis(self, text: str) -> str: ...
    async def after_story_analysis(self, scenes: list[Scene]) -> list[Scene]: ...
    async def before_prompt_generate(self, panel: Panel, prompt: Prompt) -> Prompt: ...
    async def after_prompt_generate(self, panel: Panel, prompt: Prompt) -> Prompt: ...

    # ---- 生图管线 Hook ----
    async def before_image_generate(self, prompt: Prompt, params: dict) -> dict: ...
    async def after_image_generate(self, prompt: Prompt, image: Image) -> Image: ...

    # ---- 事件 Hook ----
    async def on_panel_created(self, panel: Panel): ...
    async def on_panel_updated(self, panel: Panel): ...
    async def on_panel_generated(self, panel: Panel, images: list[Image]): ...
    async def on_task_completed(self, task: Task): ...
    async def on_export_started(self, export_job: ExportJob): ...
    async def on_export_completed(self, export_job: ExportJob, result: ExportResult): ...
```

### 9.2 第三方模型接入标准

#### LLM 模型适配器接口

```python
class BaseLLMAdapter(ABC):
    """LLM 适配器抽象基类"""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],        # [{"role": "system/user/assistant", "content": "..."}]
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> ChatResult:
        """调用 LLM 进行对话"""
        pass

    @abstractmethod
    async def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """调用 Embedding 模型获取文本向量"""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """返回当前使用的模型名称"""
        pass
```

**内置实现**：
- `OpenAICompatibleAdapter`：兼容所有 OpenAI API 格式的服务（GPT-4, DeepSeek, 通义千问等）
- 用户只需配置 API Base URL + API Key + Model Name，无需编写代码

#### 生图模型适配器接口

```python
class BaseImageGenAdapter(ABC):
    """生图模型适配器抽象基类"""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1080,
        height: int = 1440,
        steps: int = 30,
        cfg_scale: float = 7.5,
        seed: int = -1,
        batch_size: int = 4,
        **kwargs,
    ) -> ImageGenResult:
        """调用生图模型批量生成图片"""
        pass

    @abstractmethod
    async def get_models(self) -> list[str]:
        """查询模型支持列表"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """检查模型服务是否可用"""
        pass

class ImageGenResult:
    images: list[bytes]        # 生成的图片二进制数据
    seeds: list[int]           # 每张图片使用的 seed
    infos: list[dict]          # 每张图片的详细信息
    model: str                 # 使用的模型名称
```

**内置实现**：
- `SDAPIAdapter`：兼容 Stable Diffusion WebUI API 格式（SDXL, SD3 等）
- `MidjourneyAdapter`：通过 MJ-Proxy 中间件实现 Midjourney 接入
- `ComfyUIAdapter`：通过 ComfyUI API 接入自定义工作流

### 9.3 自定义工作流扩展点

系统通过以下机制支持工作流自定义：

#### 9.3.1 Agent 替换/升级

```python
# 在配置中声明自定义 Agent 实现（替换默认 Agent）
AGENT_REGISTRY = {
    "text_cleaner": {                 # Agent ID
        "default": "app.agents.text_cleaner.DefaultTextCleaner",
        "custom": "my_plugin.agents.MyTextCleaner",  # 插件注册的替代实现
    },
    "story_analyzer": {
        "default": "app.agents.story_analyzer.DefaultStoryAnalyzer",
        "custom": None,  # 未注册，使用默认
    },
    # ...
}
```

#### 9.3.2 自定义处理流程

用户可通过配置文件定义自定义处理流程：

```yaml
# workflow_custom.yaml
workflow:
  name: "快速预览模式"
  description: "跳过质量检测，加速出图流程"
  
  agents:
    - id: text_cleaner
      enabled: true
    - id: story_analyzer
      enabled: true
    - id: semantic_splitter
      enabled: true
    - id: storyboard_planner
      enabled: true
    - id: camera_planner
      enabled: true
    - id: layout_planner
      enabled: true
    - id: bubble_planner
      enabled: true
    - id: prompt_generator
      enabled: true
    - id: consistency_checker
      enabled: false      # 跳过一致性检查
    - id: quality_scorer
      enabled: false      # 跳过质量评分

  parallel_groups:
    - [text_cleaner, story_analyzer]
    - [semantic_splitter, storyboard_planner, camera_planner]
    - [layout_planner, bubble_planner]
    - [prompt_generator]
    - [consistency_checker, quality_scorer]
```

#### 9.3.3 外部系统集成

| 集成方式 | 说明 | 适用场景 |
|----------|------|----------|
| **Webhook** | 关键节点触发 HTTP 回调 | 对接第三方翻译、审核、通知系统 |
| **API 导出** | 通过 REST API 导出中间数据 | 对接外部渲染管线、资产管理平台 |
| **文件监控** | 监听文件系统变化自动触发生成 | 批量导入、自动处理 |
| **CLI 工具** | 提供命令行脚本执行完整管线 | CI/CD 集成、批量处理 |

---

## 附录 A：项目目录结构（建议）

```
webtoon-factory/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI 应用入口
│   │   ├── config.py                  # 配置加载（环境变量）
│   │   ├── database.py                # 数据库连接 + Session 管理
│   │   │
│   │   ├── routers/                   # API 路由层
│   │   │   ├── __init__.py
│   │   │   ├── novels.py
│   │   │   ├── characters.py
│   │   │   ├── scenes.py
│   │   │   ├── panels.py
│   │   │   ├── shots.py
│   │   │   ├── pages.py
│   │   │   ├── bubbles.py
│   │   │   ├── prompts.py
│   │   │   ├── generation.py
│   │   │   ├── quality.py
│   │   │   ├── export.py
│   │   │   ├── resources.py
│   │   │   ├── models.py
│   │   │   ├── plugins.py
│   │   │   ├── system.py
│   │   │   └── ws.py                  # WebSocket 路由
│   │   │
│   │   ├── services/                  # 服务层（业务逻辑）
│   │   │   ├── __init__.py
│   │   │   ├── novel_service.py
│   │   │   ├── character_service.py
│   │   │   ├── scene_service.py
│   │   │   ├── panel_service.py
│   │   │   ├── shot_service.py
│   │   │   ├── page_service.py
│   │   │   ├── bubble_service.py
│   │   │   ├── prompt_service.py
│   │   │   ├── generation_service.py
│   │   │   ├── quality_service.py
│   │   │   ├── export_service.py
│   │   │   ├── model_service.py
│   │   │   ├── pipeline_service.py    # 管线编排
│   │   │   └── task_service.py        # 任务调度服务
│   │   │
│   │   ├── agents/                    # AI Agent 层
│   │   │   ├── __init__.py
│   │   │   ├── base_agent.py          # Agent 基类
│   │   │   ├── text_cleaner.py
│   │   │   ├── story_analyzer.py
│   │   │   ├── semantic_splitter.py
│   │   │   ├── storyboard_planner.py
│   │   │   ├── camera_planner.py
│   │   │   ├── layout_planner.py
│   │   │   ├── bubble_planner.py
│   │   │   ├── prompt_generator.py
│   │   │   ├── consistency_checker.py
│   │   │   └── quality_scorer.py
│   │   │
│   │   ├── adapters/                  # AI 模型适配层
│   │   │   ├── __init__.py
│   │   │   ├── base_llm.py
│   │   │   ├── openai_adapter.py
│   │   │   ├── base_image_gen.py
│   │   │   ├── sd_api_adapter.py
│   │   │   └── midjourney_adapter.py
│   │   │
│   │   ├── models/                    # SQLAlchemy ORM 模型
│   │   │   ├── __init__.py
│   │   │   ├── novel.py
│   │   │   ├── chapter.py
│   │   │   ├── scene.py
│   │   │   ├── panel.py
│   │   │   ├── shot.py
│   │   │   ├── page.py
│   │   │   ├── bubble.py
│   │   │   ├── prompt.py
│   │   │   ├── image.py
│   │   │   ├── character.py
│   │   │   ├── worldview.py
│   │   │   ├── task.py
│   │   │   ├── quality_report.py
│   │   │   ├── model_config.py
│   │   │   └── plugin.py
│   │   │
│   │   ├── repositories/              # 数据访问层
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── novel_repo.py
│   │   │   ├── chapter_repo.py
│   │   │   ├── scene_repo.py
│   │   │   ├── panel_repo.py
│   │   │   ├── shot_repo.py
│   │   │   ├── page_repo.py
│   │   │   ├── bubble_repo.py
│   │   │   ├── prompt_repo.py
│   │   │   ├── image_repo.py
│   │   │   └── ...
│   │   │
│   │   ├── schemas/                   # Pydantic 数据模型（API 请求/响应）
│   │   │   ├── __init__.py
│   │   │   ├── novel_schema.py
│   │   │   ├── chapter_schema.py
│   │   │   ├── scene_schema.py
│   │   │   ├── panel_schema.py
│   │   │   ├── shot_schema.py
│   │   │   ├── page_schema.py
│   │   │   ├── bubble_schema.py
│   │   │   ├── prompt_schema.py
│   │   │   ├── image_schema.py
│   │   │   └── ...
│   │   │
│   │   ├── tasks/                     # Celery 任务定义
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py
│   │   │   ├── generation_tasks.py
│   │   │   ├── analysis_tasks.py
│   │   │   └── export_tasks.py
│   │   │
│   │   ├── plugins/                   # 插件引擎
│   │   │   ├── __init__.py
│   │   │   ├── base_plugin.py
│   │   │   ├── plugin_manager.py
│   │   │   └── hook_registry.py
│   │   │
│   │   ├── middleware/                # 中间件
│   │   │   ├── __init__.py
│   │   │   ├── auth.py               # JWT 认证
│   │   │   ├── cors.py
│   │   │   ├── log_sanitizer.py      # 日志脱敏
│   │   │   └── rate_limit.py         # 限流
│   │   │
│   │   └── utils/                     # 工具函数
│   │       ├── __init__.py
│   │       ├── security.py           # 加密/哈希
│   │       ├── file_utils.py
│   │       ├── image_utils.py
│   │       └── text_utils.py
│   │
│   ├── migrations/                    # Alembic 迁移脚本
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx                   # 应用入口
│   │   ├── App.tsx                    # 路由配置
│   │   │
│   │   ├── pages/                     # 页面级组件
│   │   │   ├── Dashboard/
│   │   │   ├── NovelManager/
│   │   │   ├── CharacterManager/
│   │   │   ├── SceneManager/
│   │   │   ├── StoryboardCenter/
│   │   │   ├── LayoutCenter/
│   │   │   ├── TextCenter/
│   │   │   ├── PromptCenter/
│   │   │   ├── GenerationCenter/
│   │   │   ├── QualityCenter/
│   │   │   ├── ComicEditor/
│   │   │   ├── ExportCenter/
│   │   │   ├── ResourceCenter/
│   │   │   ├── ModelCenter/
│   │   │   ├── PluginCenter/
│   │   │   └── SystemSettings/
│   │   │
│   │   ├── components/                # 通用组件
│   │   │   ├── Layout/
│   │   │   ├── PanelPreview/
│   │   │   ├── ImageGallery/
│   │   │   ├── TaskQueue/
│   │   │   ├── CharacterRelationGraph/
│   │   │   └── ...
│   │   │
│   │   ├── stores/                    # Zustand 状态存储
│   │   │   ├── novelStore.ts
│   │   │   ├── sceneStore.ts
│   │   │   ├── panelStore.ts
│   │   │   ├── taskStore.ts
│   │   │   └── ...
│   │   │
│   │   ├── hooks/                     # 自定义 Hooks
│   │   │   ├── useWebSocket.ts
│   │   │   ├── useIntersectionObserver.ts
│   │   │   └── ...
│   │   │
│   │   ├── api/                       # API 客户端
│   │   │   ├── client.ts             # Axios 实例
│   │   │   ├── novelApi.ts
│   │   │   ├── characterApi.ts
│   │   │   └── ...
│   │   │
│   │   ├── types/                     # TypeScript 类型定义
│   │   │   ├── novel.ts
│   │   │   ├── scene.ts
│   │   │   ├── panel.ts
│   │   │   └── ...
│   │   │
│   │   └── utils/
│   │       ├── canvas.ts             # Konva.js 工具
│   │       └── format.ts
│   │
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml
├── .env.example
└── README.md
```
