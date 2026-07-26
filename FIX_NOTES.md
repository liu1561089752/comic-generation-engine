# 修复说明与待人工执行清单

配套文档：[BUG_REPORT.md](BUG_REPORT.md)（问题清单与成因分析）

本次修复共落地约 80 项，改动 47 个文件。**本项目没有 git 仓库**，所有修复均为就地最小编辑，未删除任何文件。

---

## ⚠️ 一、必须人工执行（不做会出问题）

### 1. 回填 `projects.user_id` 为空的历史项目 —— 最高优先级

`_check_project_owner` 已从"宽松放行"改为**默认拒绝**（这是修复认证绕过 S5 的必要改动）。副作用：**库中 `user_id` 为 NULL 或空串的历史项目，现在对所有登录用户都返回 403**（查看、更新、归档、恢复、复制、删除全部受影响）。

先排查影响范围：

```bash
psql -c "SELECT id, name, status, created_at FROM projects WHERE user_id IS NULL OR user_id = '';"
```

确认后回填给 admin（迁移 `9e3b1c7d2f4a` 建的列是 `String(100)`，故需 `::text`）：

```bash
psql -c "UPDATE projects SET user_id = (SELECT id::text FROM users WHERE username = 'admin' LIMIT 1) WHERE user_id IS NULL OR user_id = '';"
```

> 注意：`list_projects` 走的是 `user_id == user_id` 过滤，这些项目本来就不在列表里，所以用户感知主要是**通过直链访问时 403**。

### 2. 执行新增迁移 `b3d7a1e5c8f2`

```bash
cd backend && alembic upgrade head
```

版本链已验证为线性、单一 head：`f059c9246c6d → 1fc8b9ef86fc → 9e3b1c7d2f4a → b3d7a1e5c8f2`。

**执行前必须知晓**：该迁移会创建任务去重唯一索引 `uq_tasks_active_dedup`，为此**会把同 `(project_id, task_type, novel_id)` 下重复的活跃任务除最新一条外全部置为 `failed`**（`error_message` 带 `[migration b3d7a1e5c8f2]` 前缀便于审计）。建议先跑 SELECT 版本确认影响条数：

```bash
psql -c "SELECT project_id, task_type, input_data->>'novel_id' AS novel_id, count(*) FROM tasks WHERE status IN ('queued','running') GROUP BY 1,2,3 HAVING count(*) > 1;"
```

迁移内容：给 `characters` 补 `aliases`/`description` 列；把 `layout_pages` 的四个废弃非空列（`image_prompt`/`image_url`/`reference_ids`/`shots`）与 `characters.config` 放宽为 nullable（**刻意不 drop，避免丢数据**）；`style_templates.width` 转 String(20)；建去重索引。`downgrade()` 已写全。

### 3. 收紧 `projects.user_id` 约束（需在第 1 步之后单独出一版迁移）

本次**刻意未做** —— 库里可能有 NULL 或非 UUID 文本的行，直接加约束迁移会失败。顺序：

```bash
psql -c "SELECT count(*) FROM projects WHERE user_id IS NULL;"
psql -c "SELECT count(*) FROM projects WHERE user_id IS NOT NULL AND user_id !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';"
```

两条都返回 0 后，再新出一版迁移（`down_revision='b3d7a1e5c8f2'`）执行：`alter_column` 转 UUID（`postgresql_using='user_id::uuid'`）→ 设 `nullable=False` → `create_foreign_key` 指向 `users.id`。

---

## 二、需要决策的遗留问题（本次未改）

### `PUT /system/config` 仍缺管理员权限校验

已加 pydantic 类型与范围约束（`image_max_concurrent` 限 1–32 整数），**"传非法值导致全站生图崩溃"的路径已封堵**。但**任何登录用户仍可调用**该接口。

未修的原因：`User` 模型只有 `id/username/password_hash/email/is_active/...`，**没有 `is_admin` 也没有 `role`**，全项目不存在任何角色机制。按约束我没有自造权限体系。

建议单独做一件事：给 `User` 加 `is_admin` 布尔字段 + 一个 `require_admin` 依赖，套在 `PUT /system/config`、`/system/backup`、`/system/storage/clear-cache`、`/system/plugins/{id}/toggle` 上。

另注：该接口改的是**进程级全局 settings 对象**，多 worker 下只对处理该请求的 worker 生效且重启即回退——这本身是有缺陷的设计。

### 未注册的 router：注册会导致启动崩溃

`quality`/`pages`/`panels`/`scenes`/`bubbles` 均未在 `main.py` 注册，其中 4 个**注册后会直接崩溃**（依赖已删除的模型）：

| router | 缺失的模型 |
|---|---|
| `pages.py` | `app.models.page` 不存在 |
| `panels.py`、`scenes.py` | `app.models.scene` 不存在 |
| `bubbles.py` | `app.models.bubble` 不存在 |

`quality.py` 是唯一例外，import 链看起来是通的，但未核对其路由是否都带 `project_id`、service 是否引用已删表。

这些是 Panel 流程重构后的死代码。**因为没有 git 兜底，我没有删除它们** —— 建议确认后再清理，或恢复模型并补迁移。

### 其他产品/接口决策

- **`DuplicateProjectRequest` 三个开关收了参数但从未实现**：`copy_storyboard_templates`（默认 True）、`copy_prompt_templates`（默认 True）、`copy_images`（默认 False）。前两个默认 True 会让用户以为分镜/Prompt 模板已复制，属静默功能缺失。要么补实现，要么从 schema 删除（属接口变更，需前端配合）。
- **重新预处理小说现在会清空该小说全部章节**（这是幂等语义的必然结果，旧实现是留下脏数据更糟），**连同编辑器的修改与版本历史一起级联删除**。`POST /preprocess` 目前无二次确认，建议前端加提示。
- **英文缩写误判为对话**：`bubble_planner` 的 ASCII 单引号规则 `r"'([^']+)'"` 会把 `don't ... isn't` 匹配成一段对话（捕获 `t ... isn`）。这是修复前就存在的问题，且 `text_cleaner` 刻意不转换单引号以保护缩写。是否要求"单引号两侧不能紧邻字母"需产品定调，未擅自改。

---

## 三、前端需要配合的行为变化

| 变化 | 影响 | 建议 |
|---|---|---|
| `GET /api/v1/tasks` 的 `project_id` 参数类型改为 UUID | 未选项目时传字符串 `"undefined"` 会返回 **422**（原为 500） | 该参数为空时**不要带上** |
| `/auth/refresh` 对已禁用/已删除用户返回 401 | 原来恒成功 | refresh 失败分支应走强制登出 |
| `/ws/tasks/{task_id}` 新增 **4003** 关闭码 | 无权或任务不存在时关闭 | `onclose` 若只处理 4001 需补 4003 的提示与不重连逻辑 |
| `recover_images` 任务重试**必然失败** | 凭证刻意不落库，`error_message` 为「补图凭证已失效，请重新发起补图任务」 | 任务中心需**透出 error_message**，否则用户不知要重新发起 |
| 导出单页文件名 `P1.png` → `{小说标题}_{章节标题}_P1.png` | 修复跨小说/跨章节同名覆盖的必要改动 | 若有下游脚本依赖旧命名需同步调整（长图模式仍是 `export.png`） |
| 章节数组顺序由 `created_at` 倒序改为 `chapter_number` 升序 | `get_novel_detail`、`list_chapters` | 若前端某处依赖原倒序（"最新章节在上"）需核对 |

---

## 四、已验证项

| 验证项 | 结果 |
|---|---|
| 后端 `python -m compileall app migrations` | 零错误 |
| `from app.main import app` | 成功，162 条路由 |
| 项目级归属校验覆盖 | 100 条路由挂 `require_project`；余 6 条为 `projects.py`，已逐个确认调用 `_check_project_owner` |
| 小说级归属校验覆盖 | 34 条路由挂 `require_project_novel`，**越权缺口 0** |
| `/api/v1/dashboard/stats` 已注册 | 是 |
| Alembic 版本链 | 线性、单一 head，无分支 |
| 路径穿越（9 个攻击载荷） | 全部清洗并限制在 `EXPORT_TARGET_DIR` 内；空值回退默认目录名，不写盘根 |
| 引号配对 | `"hi"` → 左右引号正确配对；`don't` 撇号保留 |
| SQL 编译（PostgreSQL 方言） | `CAST(details AS TEXT) ILIKE` 正确；WebSocket 归属过滤子查询正确 |
| 编辑器 undo/redo | 逐状态推演：撤销精确一步、最后一次修改可 redo 找回、新分支正确丢弃重做栈、`MAX_HISTORY` 截断索引同步修正 |
| 前端 `tsc --noEmit` | 65 条报错，**均为既有基线问题**（`ApiResponse<T>` 与 axios 拦截器返回值不匹配，同样出现在未触碰的 `pipelineStore`/`projectStore`/`scriptStore`）；修复前为 72 条，本次**未引入新错误** |

**未做的验证**：没有连接数据库做端到端冒烟测试，也没有启动服务。上面的 SQL 与路由验证都是静态编译/依赖树层面的。建议按第一部分执行完回填与迁移后，手工验证一遍主流程（上传小说 → 预处理 → 提取角色 → 生成分镜 → 排版 → 生图 → 导出）。
