# AI Webtoon Factory — 状态机设计文档（State Machine Design）

> 版本：v1.0  
> 最后更新：2026-06-27  
> 状态：草案

---

## 概述

本文档定义系统中所有核心实体对象的生命周期状态机，确保整个系统的状态流转一致、可预测、可追溯。所有状态转移必须通过统一的状态管理服务（`StateMachineService`）执行，并记录到 `system_log` 表。

### 状态机设计原则

1. **确定性**：每个状态的转移条件是确定的，不存在歧义
2. **可追溯**：所有状态变更记录时间戳和操作人
3. **可回退**：关键实体支持回退到之前的状态
4. **非法转移保护**：非法的状态转移应触发明确的异常

---

## 1. 项目状态机（Project）

### 状态流转图

```
                    ┌─────────┐
                    │  Draft  │  (草稿)
                    └────┬────┘
                         │ start_planning
                    ┌────▼────┐
                    │Planning │  (规划中)
                    └────┬────┘
                         │ start_generation
                    ┌────▼────┐
                    │Generating│  (生成中)
                    └────┬────┘
                         │ generation_done
                    ┌────▼────┐
                    │Editing  │  (编辑中)
                    └────┬────┘
                         │ complete_project
                    ┌────▼────┐
                    │Completed│  (已完成)
                    └────┬────┘
               ┌─────────┴─────────┐
               ▼                   ▼
         ┌─────────┐         ┌─────────┐
         │Archived │         │ Deleted │
         │ (归档)  │         │ (已删除)│
         └─────────┘         └─────────┘
```

### 状态定义

| 状态 | 标识 | 说明 | 可操作 |
|------|------|------|--------|
| **Draft** | `draft` | 项目创建，无内容 | 编辑基本信息、删除 |
| **Planning** | `planning` | 小说已导入，角色/世界观设定中 | 编辑所有设定、启动管线 |
| **Generating** | `generating` | AI 管线正在执行 | 查看进度、暂停 |
| **Editing** | `editing` | 图片已生成，人工编辑中 | 编辑漫画、审核、导出 |
| **Completed** | `completed` | 已导出，项目完成 | 归档、删除 |
| **Archived** | `archived` | 归档（只读） | 取消归档、删除 |
| **Deleted** | `deleted` | 已删除（软删除） | 恢复、永久删除 |

### 转移事件

| 事件 | 源状态 | 目标状态 | 触发条件 |
|------|--------|----------|----------|
| `start_planning` | Draft | Planning | 用户点击"开始制作" |
| `start_generation` | Planning | Generating | 用户点击"启动管线"或自动管线触发 |
| `generation_done` | Generating | Editing | 所有 Panel 的人工审核完成 |
| `complete_project` | Editing | Completed | 用户点击"完成项目" |
| `archive` | Completed | Archived | 用户点击"归档"（仅从 Completed） |
| `unarchive` | Archived | Completed | 用户点击"取消归档" |
| `delete` | 任意（除 Deleted） | Deleted | 用户点击"删除"（Completed 需二次确认）|
| `restore` | Deleted | Draft | 用户点击"恢复" |
| `permanent_delete` | Deleted | - | 7 天后自动执行，或用户手动永久删除 |

### 特殊规则

- **软删除**：删除操作不物理删除数据，仅标记 `status = "deleted"` 和 `deleted_at`
- **自动清理**：Deleted 状态保留 7 天，超时自动永久删除
- **归档保护**：Archived 状态下的项目所有字段为只读，不可编辑
- **并行限制**：同一项目一次只能处于一个 Generating 管线中

---

## 2. 小说状态机（Novel）

### 状态流转图

```
Uploaded ──→ Preprocessing ──→ Cleaned ──→ Analyzing ──→ Analyzed
                │                │                         │
                │                ├──→ Failed                │
                │                │                         │
                └──→ Failed      └──→ Failed               │
                                                            │
                                                            ├──→ Failed
                                                            │
                                                            └─ (分析完成)
```

### 状态定义

| 状态 | 标识 | 说明 |
|------|------|------|
| **Uploaded** | `uploaded` | 文件已上传，原始文本已提取 |
| **Preprocessing** | `preprocessing` | 文本清洗任务执行中 |
| **Cleaned** | `cleaned` | 文本清洗完成，结构化和段落化 |
| **Analyzing** | `analyzing` | 剧情分析/世界观分析/人物分析执行中 |
| **Analyzed** | `analyzed` | 所有分析完成，可进入下一阶段 |
| **Failed** | `failed` | 处理失败，需要人工介入 |

### 转移事件

| 事件 | 源状态 | 目标状态 | 说明 |
|------|--------|----------|------|
| `upload` | - | Uploaded | 文件上传完成 |
| `start_preprocessing` | Uploaded | Preprocessing | 启动文本清洗 |
| `preprocessing_done` | Preprocessing | Cleaned | 清洗完成 |
| `preprocessing_failed` | Preprocessing | Failed | 清洗失败 |
| `start_analyzing` | Cleaned | Analyzing | 启动剧情/世界观/人物分析 |
| `analyzing_done` | Analyzing | Analyzed | 分析完成 |
| `analyzing_failed` | Analyzing | Failed | 分析失败 |
| `retry` | Failed | Uploaded 或 Preprocessing | 人工修正后重新触发 |

### 相关数据

| 字段 | 说明 |
|------|------|
| `status` | 当前状态 |
| `raw_text` | 原始文本（Uploaded 后写入） |
| `cleaned_text` | 清洗后文本（Cleaned 后写入）|
| `failure_reason` | 失败原因（Failed 时写入）|
| `retry_count` | 重试次数 |

---

## 3. 章节状态机（Chapter）

### 状态流转图

```
Pending ──→ Processing ──→ Cleaned ──→ Analyzing ──→ Analyzed
              │                            │
              └──→ Failed                  └──→ Failed
```

### 状态定义

| 状态 | 标识 | 说明 |
|------|------|------|
| **Pending** | `pending` | 章节已创建，等待处理 |
| **Processing** | `processing` | 文本处理中 |
| **Cleaned** | `cleaned` | 文本清洗完成 |
| **Analyzing** | `analyzing` | Scene 分析中 |
| **Analyzed** | `analyzed` | 分析完成，Scene 已生成 |
| **Failed** | `failed` | 处理失败 |

### 转移事件

| 事件 | 源状态 | 目标状态 | 说明 |
|------|--------|----------|------|
| `start_processing` | Pending | Processing | 启动文本处理 |
| `processing_done` | Processing | Cleaned | 处理完成 |
| `processing_failed` | Processing | Failed | 处理失败 |
| `start_analyzing` | Cleaned | Analyzing | 启动分析 |
| `analyzing_done` | Analyzing | Analyzed | 分析完成 |
| `analyzing_failed` | Analyzing | Failed | 分析失败 |

---

## 4. 场景状态机（Scene）

### 状态流转图

```
Pending ──→ Splitting ──→ Split ──→ Storyboarding ──→ Storyboarded
              │              │           │
              └──→ Failed    │           └──→ Failed
                             │
                             ├──→ Generating ──→ Generated ──→ Approved
                             │       │              │
                             │       └──→ Failed    │
                             │                      └──→ Failed
                             │
                             └──→ (等待 Panel 状态影响)
```

### 状态定义

| 状态 | 标识 | 说明 |
|------|------|------|
| **Pending** | `pending` | Scene 已创建，等待语义切句 |
| **Splitting** | `splitting` | 语义切句执行中 |
| **Split** | `split` | 语义切句完成，Panel 已生成 |
| **Storyboarding** | `storyboarding` | 分镜规划执行中 |
| **Storyboarded** | `storyboarded` | 分镜规划完成 |
| **Generating** | `generating` | 生图任务进行中（包含所有下属 Panel）|
| **Generated** | `generated` | 所有 Panel 生图完成 |
| **Approved** | `approved` | 所有 Panel 审核通过 |
| **Failed** | `failed` | 处理失败 |

### 转移事件

| 事件 | 源状态 | 目标状态 | 说明 |
|------|--------|----------|------|
| `start_splitting` | Pending | Splitting | 启动语义切句 |
| `splitting_done` | Splitting | Split | 语义切句完成 |
| `splitting_failed` | Splitting | Failed | 语义切句失败 |
| `start_storyboarding` | Split | Storyboarding | 启动分镜规划 |
| `storyboarding_done` | Storyboarding | Storyboarded | 分镜规划完成 |
| `storyboarding_failed` | Storyboarding | Failed | 分镜规划失败 |
| `start_generation` | Storyboarded | Generating | 启动生图任务 |
| `all_panels_generated` | Generating | Generated | 所有下属 Panel 生图完成 |
| `generation_failed` | Generating | Failed | 生图失败 |
| `all_panels_approved` | Generated | Approved | 所有下属 Panel 审核通过 |
| `approval_failed` | Generated | Failed | 审核全部打回 |
| `retry` | Failed | 上一个成功状态 | 重试 |

---

## 5. 画格状态机（Panel）

Panel 是系统中**最核心的状态机**，包含最详细的状态定义和最多的转移路径。

### 状态流转图

```
Created ──→ Split ──→ Storyboarded ──→ CameraSet ──→ LayoutSet
  │
  └──→ (直接标记失败)

LayoutSet ──→ PromptReady ──→ Generating ──→ Generated
                                        │
                                        └──→ Failed

Generated ──→ Reviewed ──→ Approved ──→ Exported
                │
                ├──→ Generating (打回重生成)
                │
                └──→ Failed
```

### 状态定义

| 状态 | 标识 | 说明 |
|------|------|------|
| **Created** | `created` | Panel 已创建，内容已分配 |
| **Split** | `split` | 语义切句完成，Panel 边界确定 |
| **Storyboarded** | `storyboarded` | 分镜规划完成，视觉描述就绪 |
| **CameraSet** | `camera_set` | 镜头规划完成 |
| **LayoutSet** | `layout_set` | 版式位置已分配 |
| **PromptReady** | `prompt_ready` | Prompt 已组装，等待生成 |
| **Generating** | `generating` | 生图任务执行中 |
| **Generated** | `generated` | 候选图已生成（4-8 张）|
| **Reviewed** | `reviewed` | 人工审核完成 |
| **Approved** | `approved` | 图片已选中确认 |
| **Exported** | `exported` | 已随 Page 导出 |
| **Failed** | `failed` | 处理失败（任一环节）|

### 转移事件

| 事件 | 源状态 | 目标状态 | 触发条件 |
|------|--------|----------|----------|
| `create` | - | Created | Scene 切分完成，创建 Panel 记录 |
| `split_done` | Created | Split | 语义切句完成 |
| `split_failed` | Created | Failed | 语义切句失败 |
| `storyboard_done` | Split | Storyboarded | 分镜规划完成 |
| `storyboard_failed` | Split | Failed | 分镜规划失败 |
| `camera_done` | Storyboarded | CameraSet | 镜头规划完成 |
| `camera_failed` | Storyboarded | Failed | 镜头规划失败 |
| `layout_assigned` | CameraSet | LayoutSet | 版式位置分配完成 |
| `prompt_ready` | LayoutSet | PromptReady | Prompt 组装完成 |
| `start_generation` | PromptReady | Generating | 提交生图任务 |
| `generation_done` | Generating | Generated | 4-8 张候选图全部生成 |
| `generation_failed` | Generating | Failed | 生图失败 |
| `start_review` | Generated | Reviewed | 人工审核开始（状态变更即进入）|
| `approve` | Reviewed | Approved | 用户选中一张图 |
| `regenerate` | Reviewed | Generating | 用户打回重生成 |
| `skip_review` | Generated | Approved | 快速模式自动选中第一张 |
| `exported` | Approved | Exported | 页面导出完成 |
| `retry` | Failed | 上游状态 | 人工修复后重试 |

### 打回路径

```
Reviewed ──→ [用户选择"重新生成"]
    │
    └──→ Generating (保留原 Prompt，更换 seed)
         │
         └──→ Generated (新候选图)
              │
              └──→ Reviewed (再次审核)
```

**打回规则：**
- 打回时保留原 Prompt、镜头数据、版式数据
- 可指定新的 seed 值（默认随机）
- 打回次数无限制（但超过 3 次将提示人工检查上游数据）
- 打回后原候选图标记为 `rejected` 保留在系统中

---

## 6. 图片状态机（Image）

### 状态流转图

```
Pending ──→ Generating ──→ Generated ──→ Selected
                              │
                              ├──→ Rejected
                              │
                              └──→ Superseded
```

### 状态定义

| 状态 | 标识 | 说明 |
|------|------|------|
| **Pending** | `pending` | 图片记录已创建，等待生成 |
| **Generating** | `generating` | 图片正在生成 |
| **Generated** | `generated` | 图片生成完成 |
| **Selected** | `selected` | 用户在审核中选择了此图 |
| **Rejected** | `rejected` | 用户在审核中拒绝了此图 |
| **Superseded** | `superseded` | 被后续生成的图片取代（重新生成后）|

### 转移事件

| 事件 | 源状态 | 目标状态 | 说明 |
|------|--------|----------|------|
| `start` | Pending | Generating | 提交生图任务 |
| `complete` | Generating | Generated | 图片生成完成 |
| `fail` | Generating | Rejected | 生成失败 |
| `select` | Generated | Selected | 用户选择此图 |
| `reject` | Generated | Rejected | 用户拒绝此图 |
| `supersede` | Generated / Selected | Superseded | 重新生成后，旧图被取代 |

### 特殊规则

- 每个 Panel 同时最多有 4 张 Generated 状态的候选图
- 重新生成时，旧的生成的图片标记为 Superseded
- 被 Selected 的图片在重新生成后也被标记为 Superseded
- 每张图片保留完整元数据（Prompt、Seed、模型参数）

---

## 7. Prompt 状态机（Prompt）

### 状态流转图

```
Draft ──→ Completed ──→ Used ──→ Superseded
                  │
                  └──→ (直接关联生图)
```

### 状态定义

| 状态 | 标识 | 说明 |
|------|------|------|
| **Draft** | `draft` | Prompt 模板加载，等待数据填充 |
| **Completed** | `completed` | 10 层 Prompt 组装完成 |
| **Used** | `used` | 已用于生图（关联了 Image 记录）|
| **Superseded** | `superseded` | 被新版本的 Prompt 取代 |

### 转移事件

| 事件 | 源状态 | 目标状态 | 说明 |
|------|--------|----------|------|
| `create` | - | Draft | Prompt 模板加载完成 |
| `compile` | Draft | Completed | 所有变量替换完成，Prompt 就绪 |
| `compile_fail` | Draft | Draft | 编译失败（保留已填充字段）|
| `use` | Completed | Used | Prompt 提交给生图模型 |
| `supersede` | Used | Superseded | 用户编辑 Prompt 后生成新版本 |

### 版本管理

- 每个 Panel 可关联多个 Prompt 版本
- Superseded 状态的 Prompt 关联的历史 Image 仍可查看
- 系统保留所有 Prompt 版本历史

---

## 8. 气泡状态机（Bubble）

### 状态流转图

```
Pending ──→ Identified ──→ Confirmed ──→ Edited
                │              │
                └──→ Failed    └──→ (人工确认)
```

### 状态定义

| 状态 | 标识 | 说明 |
|------|------|------|
| **Pending** | `pending` | 气泡记录已创建但未识别 |
| **Identified** | `identified` | AI 已完成气泡识别和类型分类 |
| **Confirmed** | `confirmed` | 用户已确认或自动确认（审核通过）|
| **Edited** | `edited` | 用户在漫画编辑器中手动修改了气泡 |
| **Failed** | `failed` | 识别失败 |

### 转移事件

| 事件 | 源状态 | 目标状态 | 说明 |
|------|--------|----------|------|
| `start` | Pending | Identified | AI 识别完成 |
| `fail` | Pending | Failed | 识别失败 |
| `auto_confirm` | Identified | Confirmed | 管线自动确认（无人工审核时）|
| `manual_confirm` | Identified | Confirmed | 用户手动确认 |
| `edit` | Confirmed | Edited | 用户在编辑器中修改 |
| `re_identify` | Edited | Identified | 重新识别（撤销手动编辑）|

---

## 9. 页面状态机（Page）

### 状态流转图

```
Empty ──→ Layouted ──→ Populated ──→ Edited ──→ Completed
                                          │
                                          └──→ (导出完成)
```

### 状态定义

| 状态 | 标识 | 说明 |
|------|------|------|
| **Empty** | `empty` | 页面创建，无 Panel 内容 |
| **Layouted** | `layouted` | 版式规划完成，Panel 位置已分配 |
| **Populated** | `populated` | 所有 Panel 的选中图片已填充 |
| **Edited** | `edited` | 用户已完成漫画编辑器的手动调整 |
| **Completed** | `completed` | 页面最终确认，可用于导出 |

### 转移事件

| 事件 | 源状态 | 目标状态 | 说明 |
|------|--------|----------|------|
| `create` | - | Empty | 页面创建 |
| `layout` | Empty | Layouted | 版式规划分配 Panel 位置 |
| `populate` | Layouted | Populated | 所有 Panel 审核通过，图片填充 |
| `start_edit` | Populated | Edited | 用户在漫画编辑器中打开页面 |
| `edit_done` | Edited | Edited | 编辑保存（停留在 Edited）|
| `mark_complete` | Edited | Completed | 用户标记页面完成 |
| `re_edit` | Completed | Edited | 用户重新编辑已完成页面 |

### 特殊规则

- Populated → Edited 的转移是手动触发的（用户开始编辑）
- Edited 状态可多次保存（不改变状态）
- 页面完成前，本章所有 Panel 必须处于 Approved 或 Exported 状态
- Page 的 Completed 状态是 Export 的前置条件

---

## 10. 任务状态机（Task）

### 状态流转图

```
Queued ──→ Running ──→ Completed
              │
              ├──→ Failed ──→ Retrying ──→ Running
              │
              └──→ Cancelled
```

### 状态定义

| 状态 | 标识 | 说明 |
|------|------|------|
| **Queued** | `queued` | 任务已提交，在 Celery 队列中等待 |
| **Running** | `running` | 任务正在执行 |
| **Completed** | `completed` | 任务执行成功 |
| **Failed** | `failed` | 任务执行失败 |
| **Cancelled** | `cancelled` | 用户取消任务 |
| **Retrying** | `retrying` | 自动重试中 |

### 转移事件

| 事件 | 源状态 | 目标状态 | 说明 |
|------|--------|----------|------|
| `enqueue` | - | Queued | 任务提交到队列 |
| `start` | Queued | Running | Worker 开始执行任务 |
| `complete` | Running | Completed | 任务成功完成 |
| `fail` | Running | Failed | 任务执行失败 |
| `cancel` | Queued / Running | Cancelled | 用户手动取消 |
| `retry` | Failed | Retrying | 自动重试调度 |
| `retry_start` | Retrying | Running | 重试任务开始执行 |
| `retry_exhausted` | Retrying | Failed | 超过最大重试次数 |

### 任务字段

| 字段 | 说明 |
|------|------|
| `id` | UUID |
| `task_type` | `text_clean` / `story_analyze` / `semantic_split` / `storyboard` / `camera_plan` / `layout_plan` / `bubble_plan` / `prompt_gen` / `image_gen` / `consistency_check` / `quality_score` / `export` |
| `status` | 当前状态 |
| `progress` | 0-100 进度百分比 |
| `message` | 人类可读的状态消息 |
| `result` | JSON 结果数据 |
| `error` | 错误信息（失败时）|
| `retry_count` | 已重试次数 |
| `max_retries` | 最大重试次数 |
| `queue_name` | 队列名 |
| `priority` | 优先级 (1-10) |
| `created_at` | 创建时间 |
| `started_at` | 开始时间 |
| `completed_at` | 完成时间 |

---

## 11. 导出任务状态机（ExportJob）

### 状态流转图

```
Pending ──→ Packaging ──→ Completed
              │
              └──→ Failed
```

### 状态定义

| 状态 | 标识 | 说明 |
|------|------|------|
| **Pending** | `pending` | 导出请求已提交，等待处理 |
| **Packaging** | `packaging` | 图片渲染 + 打包中 |
| **Completed** | `completed` | 导出完成，文件已就绪 |
| **Failed** | `failed` | 导出失败 |

### 转移事件

| 事件 | 源状态 | 目标状态 | 说明 |
|------|--------|----------|------|
| `submit` | - | Pending | 用户提交导出请求 |
| `start` | Pending | Packaging | Worker 开始处理导出 |
| `complete` | Packaging | Completed | 导出完成 |
| `fail` | Packaging | Failed | 导出失败 |
| `retry` | Failed | Packaging | 用户手动重试 |

### 导出结果字段

```
ExportJob {
  id: UUID,
  project_id: UUID,
  format: "png" | "jpg" | "psd" | "long_image" | "project_package",
  status: "pending" | "packaging" | "completed" | "failed",
  options: { quality, dpi, include_metadata },
  progress: number,             // 0-100
  file_paths: string[],         // 完成后的下载路径
  file_size: number,
  error: string,
  expires_at: datetime,         // 导出文件下载链接过期时间（默认 7 天）
}
```

---

## 12. 状态转移总表

### 所有实体状态转移汇总

| 实体 | 状态集合 | 非法转移例 |
|------|----------|-----------|
| **Project** | draft, planning, generating, editing, completed, archived, deleted | archived → generating, deleted → editing |
| **Novel** | uploaded, preprocessing, cleaned, analyzing, analyzed, failed | analyzed → preprocessing, failed → analyzed |
| **Chapter** | pending, processing, cleaned, analyzing, analyzed, failed | analyzed → processing, cleaned → pending |
| **Scene** | pending, splitting, split, storyboarding, storyboarded, generating, generated, approved, failed | approved → splitting, split → generating (必须先经过 storyboarding) |
| **Panel** | created, split, storyboarded, camera_set, layout_set, prompt_ready, generating, generated, reviewed, approved, exported, failed | approved → generating (必须先经过 reviewed), exported → created |
| **Image** | pending, generating, generated, selected, rejected, superseded | selected → pending, superseded → generated |
| **Prompt** | draft, completed, used, superseded | superseded → draft, completed → superseded (必须先 used) |
| **Bubble** | pending, identified, confirmed, edited, failed | edited → pending, confirmed → identified (但 edited → identified 允许) |
| **Page** | empty, layouted, populated, edited, completed | completed → empty, layouted → edited (必须先 populated) |
| **Task** | queued, running, completed, failed, cancelled, retrying | completed → running, cancelled → retrying |
| **ExportJob** | pending, packaging, completed, failed | completed → packaging, failed → pending (但 failed → packaging 允许重试) |

### 统一状态值枚举

```python
# 统一状态值定义（参考）
class EntityStatus(str, Enum):
    # 通用
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    
    # 项目
    DRAFT = "draft"
    PLANNING = "planning"
    GENERATING = "generating"
    EDITING = "editing"
    ARCHIVED = "archived"
    DELETED = "deleted"
    
    # Novel
    UPLOADED = "uploaded"
    PREPROCESSING = "preprocessing"
    CLEANED = "cleaned"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    
    # Chapter
    PROCESSING = "processing"
    CLEANED = "cleaned"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    
    # Scene
    SPLITTING = "splitting"
    SPLIT = "split"
    STORYBOARDING = "storyboarding"
    STORYBOARDED = "storyboarded"
    GENERATED = "generated"
    APPROVED = "approved"
    
    # Panel
    CREATED = "created"
    SPLIT = "split"
    STORYBOARDED = "storyboarded"
    CAMERA_SET = "camera_set"
    LAYOUT_SET = "layout_set"
    PROMPT_READY = "prompt_ready"
    GENERATING = "generating"
    GENERATED = "generated"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    EXPORTED = "exported"
    
    # Image
    GENERATING = "generating"
    GENERATED = "generated"
    SELECTED = "selected"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    
    # Prompt
    DRAFT = "draft"
    COMPLETED = "completed"
    USED = "used"
    SUPERSEDED = "superseded"
    
    # Bubble
    IDENTIFIED = "identified"
    CONFIRMED = "confirmed"
    EDITED = "edited"
    
    # Page
    EMPTY = "empty"
    LAYOUTED = "layouted"
    POPULATED = "populated"
    EDITED = "edited"
    
    # Task
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    
    # ExportJob
    PACKAGING = "packaging"
```

---

## 13. 状态机实现规范

### 13.1 数据库字段规范

所有具备状态机的实体应在数据库中包含以下字段：

```sql
-- 标准状态字段模板
ALTER TABLE <entity_name> ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT '<initial_status>';
ALTER TABLE <entity_name> ADD COLUMN previous_status VARCHAR(32);          -- 上一状态（用于回退）
ALTER TABLE <entity_name> ADD COLUMN status_changed_at TIMESTAMP;          -- 最后状态变更时间
ALTER TABLE <entity_name> ADD COLUMN failure_reason TEXT;                  -- 失败原因
ALTER TABLE <entity_name> ADD COLUMN retry_count INTEGER DEFAULT 0;        -- 重试次数
```

### 13.2 状态变更记录

所有状态转移必须记录到 `system_log` 表：

```sql
-- 状态变更日志表
CREATE TABLE system_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(32) NOT NULL,          -- 'project' / 'novel' / 'panel' / etc.
    entity_id UUID NOT NULL,                   -- 状态变更的实体 ID
    from_status VARCHAR(32),                   -- 变更前状态（NULL = 初始创建）
    to_status VARCHAR(32) NOT NULL,            -- 变更后状态
    event VARCHAR(64) NOT NULL,                -- 触发事件名
    operator VARCHAR(128),                     -- 操作人（'system' / user_id / 'agent:<agent_id>'）
    metadata JSONB,                            -- 附加信息（错误信息、耗时等）
    created_at TIMESTAMP DEFAULT NOW()
);

-- 常用查询索引
CREATE INDEX idx_system_log_entity ON system_log(entity_type, entity_id);
CREATE INDEX idx_system_log_created_at ON system_log(created_at DESC);
```

### 13.3 状态管理服务接口

```python
class StateMachineService:
    """
    统一状态管理服务。
    所有实体的状态变更必须通过此服务执行。
    """
    
    @staticmethod
    async def transition(
        entity: Any,              # ORM 实体对象
        event: str,               # 转移事件名
        operator: str = "system", # 操作人
        metadata: dict = None,    # 附加元数据
        session: AsyncSession,    # 数据库会话
    ) -> Any:
        """
        执行状态转移。
        
        步骤：
        1. 验证当前状态是否允许该事件（查转移矩阵）
        2. 执行前置钩子（如有）
        3. 更新 entity.status 和 entity.status_changed_at
        4. 记录 system_log
        5. 执行后置钩子（如有）
        6. 返回更新后的 entity
        """
        pass
    
    @staticmethod
    async def get_valid_transitions(
        entity_type: str,
        current_status: str,
    ) -> list[dict]:
        """
        查询实体当前状态下所有合法的转移事件。
        
        返回：
        [
            {"event": "start_generation", "to_status": "generating", "description": "启动管线生成"},
            {"event": "delete", "to_status": "deleted", "description": "删除项目"},
        ]
        """
        pass
    
    @staticmethod
    async def get_history(
        entity_type: str,
        entity_id: UUID,
    ) -> list[dict]:
        """
        获取实体的完整状态变更历史。
        """
        pass
```

### 13.4 状态转移矩阵定义

```python
# 状态转移矩阵定义（每个实体一个矩阵）
PANEL_TRANSITIONS = {
    "created": {
        "split_done": ("split", "语义切句完成"),
        "split_failed": ("failed", "语义切句失败"),
    },
    "split": {
        "storyboard_done": ("storyboarded", "分镜规划完成"),
        "storyboard_failed": ("failed", "分镜规划失败"),
    },
    "storyboarded": {
        "camera_done": ("camera_set", "镜头规划完成"),
        "camera_failed": ("failed", "镜头规划失败"),
    },
    "camera_set": {
        "layout_assigned": ("layout_set", "版式位置分配"),
    },
    "layout_set": {
        "prompt_ready": ("prompt_ready", "Prompt 组装完成"),
    },
    "prompt_ready": {
        "start_generation": ("generating", "提交生图任务"),
    },
    "generating": {
        "generation_done": ("generated", "4-8 张候选图生成完成"),
        "generation_failed": ("failed", "生图失败"),
    },
    "generated": {
        "start_review": ("reviewed", "进入人工审核"),
        "skip_review": ("approved", "快速模式自动选中"),
    },
    "reviewed": {
        "approve": ("approved", "用户选中图片"),
        "regenerate": ("generating", "用户打回重生成"),
    },
    "approved": {
        "exported": ("exported", "已随页面导出"),
    },
    "failed": {
        "retry": ("created", "重试（从创建开始）"),
        "retry_from_storyboard": ("storyboarded", "重试（从分镜开始）"),
        "retry_from_generating": ("generating", "重试（从生图开始）"),
    },
}
```

### 13.5 状态变更流程图（数据流视角）

```
用户操作 / AI Agent / 系统调度
        │
        ▼
  ┌─────────────────┐
  │  API 路由层      │
  │  (Routers)       │
  └────────┬─────────┘
           │
  ┌────────▼─────────┐
  │  服务层            │
  │  (Services)       │
  │  调用状态管理服务    │
  └────────┬─────────┘
           │
  ┌────────▼─────────┐      ┌─────────────────┐
  │  StateMachine     │──────│  system_log 表   │
  │  Service          │ 记录 │  (状态变更日志)    │
  │  校验 → 更新 → 记录 │      └─────────────────┘
  └────────┬─────────┘
           │
  ┌────────▼─────────┐
  │  ORM 实体          │
  │  (status 字段更新)  │
  └────────┬─────────┘
           │
  ┌────────▼─────────┐
  │  数据库 (PostgreSQL)│
  │  持久化状态         │
  └──────────────────┘
```

### 13.6 非法转移处理

```python
class IllegalStateTransitionError(Exception):
    """非法状态转移异常"""
    
    def __init__(self, entity_type: str, entity_id: UUID,
                 current_status: str, event: str):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.current_status = current_status
        self.event = event
        valid_events = StateMachineService.get_valid_transitions(
            entity_type, current_status
        )
        super().__init__(
            f"非法状态转移: {entity_type}[{entity_id}] "
            f"当前状态={current_status}, 尝试事件={event}. "
            f"合法事件: {[e['event'] for e in valid_events]}"
        )
```

### 13.7 前端状态同步

前端通过 WebSocket 实时接收关键实体的状态变更：

```json
// WebSocket 消息格式
{
  "type": "state_change",
  "entity_type": "panel",
  "entity_id": "uuid",
  "from_status": "generating",
  "to_status": "generated",
  "event": "generation_done",
  "timestamp": "2026-06-27T12:00:00Z",
  "metadata": {
    "images_count": 4,
    "generation_time_ms": 45230
  }
}
```

**前端状态管理策略：**
| 场景 | 策略 |
|------|------|
| Panel 状态变更 | WebSocket 实时推送，更新 Zustand store |
| 批量状态变更 | 后端聚合后推送（避免大量小消息） |
| 任务进度更新 | 每秒最多推送一次（节流） |
| 离线恢复 | 页面加载时全量拉取当前状态 |

---

## 附录 A：实体状态汇总

| 实体 | 状态数 | 状态列表 |
|------|--------|----------|
| Project | 7 | draft, planning, generating, editing, completed, archived, deleted |
| Novel | 6 | uploaded, preprocessing, cleaned, analyzing, analyzed, failed |
| Chapter | 6 | pending, processing, cleaned, analyzing, analyzed, failed |
| Scene | 9 | pending, splitting, split, storyboarding, storyboarded, generating, generated, approved, failed |
| Panel | 12 | created, split, storyboarded, camera_set, layout_set, prompt_ready, generating, generated, reviewed, approved, exported, failed |
| Image | 6 | pending, generating, generated, selected, rejected, superseded |
| Prompt | 4 | draft, completed, used, superseded |
| Bubble | 5 | pending, identified, confirmed, edited, failed |
| Page | 5 | empty, layouted, populated, edited, completed |
| Task | 6 | queued, running, completed, failed, cancelled, retrying |
| ExportJob | 4 | pending, packaging, completed, failed |

## 附录 B：状态变更通知事件

| 事件 | 触发条件 | 通知对象 |
|------|----------|----------|
| `project.status_changed` | Project 状态变更 | 项目管理页面、Dashboard |
| `novel.status_changed` | Novel 状态变更 | 小说管理页面 |
| `scene.status_changed` | Scene 状态变更 | 剧情拆解中心 |
| `panel.generation_done` | Panel 从 generating → generated | 生图中心、审核页面 |
| `panel.review_needed` | Panel 进入 reviewed 状态 | 审核中心通知 |
| `panel.approved` | Panel 从 reviewed → approved | 漫画编辑器 |
| `task.status_changed` | Task 状态变更 | 任务中心、全局通知 |
| `export.completed` | ExportJob → completed | 导出中心、下载通知 |
| `pipeline.stalled` | 管线长时间无进度 | 系统管理员通知 |
