# 漫画生成引擎 — Bug 审查报告

> 通过多智能体分子系统审查 + 对抗性验证生成。共报告 67 条，验证确认 **61 条真实缺陷**（合并重复项后约 52 个独立问题）。按主题与严重程度排序，每条给出：位置 → 问题 → 触发场景 → 修复建议。

严重程度：**Critical/High**=安全漏洞、数据损坏、核心功能不可用；**Medium**=特定操作出错；**Low**=次要缺陷/死代码。

---

## 一、安全漏洞（最高优先级）

### S1. 所有项目级端点缺少归属校验（水平越权）— HIGH
- **位置**：`backend/app/routers/novels.py`、`characters.py`、`worlds.py`、`export.py`、`generation.py`、`tasks.py`（项目级端点）
- **问题**：这些路由都声明了 `user_id = Depends(get_current_user)`，但拿到 `user_id` 后从不校验 path 中的 `project_id` 是否属于该用户，也不校验 `novel_id/character_id/...` 是否隶属该项目。全项目只有 `projects.py` 的 `_check_project_owner` 做了归属校验。
- **触发**：用户 A 用自己的 token，向 `DELETE /api/v1/projects/<B的project_id>/novels/<B的novel_id>/layout-pages` 发请求，服务端不做任何归属判断即删除 B 的全部漫画页记录与磁盘图片，返回 200；`PUT .../novels/{id}/text` 可改写他人小说正文，`GET` 可读取他人全文。
- **修复**：抽出公共依赖 `async def require_project(project_id, user_id, db) -> Project`，查询并校验 `Project.user_id == user_id`，所有 `/{project_id}/...` 路由用 `Depends` 强制引入；service 层对子资源做 `project_id` 归属过滤（`select(Novel).where(Novel.id==novel_id, Novel.project_id==project_id)`）。

### S2. 两个 WebSocket 端点只验签不校验归属，泄漏全库任务数据 — HIGH
- **位置**：`backend/app/routers/ws.py:108`（`/ws/tasks/{task_id}` 与 `/ws/tasks`）
- **问题**：仅校验 token 合法，不做 user/project 过滤。`/ws/tasks` 每 10 秒 `select(Task)...limit(250)` 把全库最近任务推给任意连接者；`/ws/tasks/{task_id}` 直接把含 logs/error/project_id 的消息推给客户端。REST 侧已有的 `_check_task_belongs_to_user` 被完全绕过。
- **触发**：用户 A 连 `ws://host/ws/tasks?token=<A>`，每 10 秒收到 B、C 全部任务的 task_id、错误堆栈日志；再用拿到的 task_id 连 `/ws/tasks/{task_id}` 持续读取他人任务详情。
- **修复**：从 token 取 user_id，`/ws/tasks` 查询加 `Task.project_id.in_(select(Project.id).where(Project.user_id==user_id))`；`/ws/tasks/{task_id}` accept 后复用归属校验，不属于则 `close(code=4003)`。

### S3. 导出目录直接拼接用户传入的 alias_name → 路径穿越/任意文件写入 — HIGH
- **位置**：`backend/app/modules/export/service.py:244`
- **问题**：`folder_name` 直接取自请求体 `alias_name`（无任何校验），`export_dir = os.path.join(settings.EXPORT_TARGET_DIR, folder_name)`。`alias_name` 含 `..\..\` 可逃逸；为绝对路径（如 `C:\...\Startup`）时 `os.path.join` 直接丢弃基目录。随后在该目录 `makedirs` 并写入/覆盖 `{page_label}.png`。
- **触发**：登录用户 `POST /{project_id}/export`，body `{"alias_name":"C:\\Users\\Public\\Startup"}` → 服务进程在任意可写目录创建文件夹并写 PNG（可覆盖同名文件）。
- **修复**：白名单清洗 `alias_name`（只留中英数字下划线连字符，去掉分隔符与 `..`），拼接后用 `os.path.realpath` 校验结果仍位于 `EXPORT_TARGET_DIR` 内，否则拒绝；schema 加 `max_length` 与正则约束。

### S4. refresh 端点不校验用户状态，账号封禁后仍可无限续签 — HIGH
- **位置**：`backend/app/routers/auth.py:68`
- **问题**：`/auth/refresh` 只验 refresh token 签名与 `type=="refresh"`，不查库、不检查 `is_active`（login 有此检查），且每次刷新都签发新的 7 天 refresh token，形成可无限续期的凭证链。
- **触发**：管理员把某用户 `is_active` 置 False 或删除该行，用户手持未过期 refresh token 仍可 `POST /auth/refresh` 换新令牌，持续访问所有受保护端点，封禁形同无效。
- **修复**：refresh 端点注入 `db`，按 sub 查 User，用户不存在或非 active 时返回 401/403；可引入 token 版本号或黑名单使禁用/改密即时失效。

### S5. `_check_project_owner` 对空 user_id 放行 + 迁移 user_id 可为 NULL → 认证绕过 — MEDIUM
- **位置**：`backend/app/routers/projects.py:52`
- **问题**：`if project_uid and project_uid != user_id` 才抛 403，即 `user_id` 为 NULL/空的项目跳过全部校验。而迁移 `9e3b1c7d2f4a` 把 `projects.user_id` 建成 `nullable=True`（与模型 `nullable=False` 不一致），DB 中允许存在 NULL 用户的历史项目。
- **触发**：库中有迁移前创建的项目（user_id IS NULL），任意登录用户可读取/篡改/删除（连带级联删小说、角色、任务并 rmtree 存储目录）。
- **修复**：改默认拒绝 `if str(project.user_id or "") != user_id: raise HTTPException(403)`；补迁移把 `user_id` 回填后改 `NOT NULL` 并加外键。

### S6. `PUT /system/config` 无权限、无类型校验，可让全站生图崩溃 — MEDIUM
- **位置**：`backend/app/routers/system.py:389`
- **问题**：接收裸 `dict`，对白名单键直接 `setattr(settings, k.upper(), v)`。Settings 未开 `validate_assignment`，无类型校验；改的是进程级全局对象；且任何普通登录用户都能调用。
- **触发**：`PUT /system/config` body `{"image_max_concurrent":"abc"}` → 之后任意用户触发批量生图，`asyncio.Semaphore("abc")` 抛 TypeError，全站生图失效且重启前无法恢复。
- **修复**：用显式 pydantic 模型（`image_max_concurrent: int = Field(ge=1, le=32)` 等）替换裸 dict，或开 `validate_assignment=True`；加管理员权限校验。

---

## 二、核心功能崩溃（一用即 500 / 完全不可用）

### C1. `create_character` 传入不存在的 `config` 字段 → 手动创建角色必定 500 — HIGH
- **位置**：`backend/app/modules/character/service.py:91`
- **问题**：`char_repo.create(..., config=config)` → `Character(**kwargs)`，但 Character 模型无 `config` 列，SQLAlchemy 抛 `TypeError`，路由只捕 `ValueError` → 500。
- **修复**：改为 `await self.char_repo.create(project_id=project_id, name=data.name, aliases="", description="")`。

### C2. `duplicate_project` 读取 Character 上不存在的字段 → 复制含角色项目必定 500 — HIGH
- **位置**：`backend/app/routers/projects.py:294`
- **问题**：复制角色时读 `c.age/c.height/c.personality/...` 等模型不存在的字段 → `AttributeError`；即便通过，`Character(**kwargs)` 也会 `TypeError`。`copy_characters` 默认 True。
- **触发**：对任何已提取过角色的项目 `POST /projects/{id}/duplicate` 立即 500，且新项目已被创建、留下半成品。
- **修复**：按真实字段复制 `name/aliases/description/role_type/status/stable_key`；整个 duplicate 放同一事务，失败回滚。

### C3. `tasks.py` 使用未导入的 `desc()` → 任务看板必定 500 — HIGH
- **位置**：`backend/app/routers/tasks.py:261`
- **问题**：顶部只 `from sqlalchemy import select, func, update as sa_update`，未导入 `desc`，但 `get_queue_kanban` 用了 `desc(Task.created_at)` → `NameError` → 500。
- **修复**：`from sqlalchemy import select, func, desc, update as sa_update`，或改用 `Task.created_at.desc()`。

### C4. dashboard 路由从未注册 → 首页统计恒 404 — HIGH
- **位置**：`backend/app/main.py`（未 `include_router(dashboard.router)`）
- **问题**：`dashboard.py` 定义了 `GET /stats`，但 main.py 未注册（同样未注册的还有 quality/pages/panels/scenes/bubbles，而前端仍在调用）。前端 catch 里只 console.error，`stats` 保持 null。
- **触发**：打开首页 → `GET /api/v1/dashboard/stats` 404 → 统计卡片、生产进度、待处理任务全为空且无提示。
- **修复**：补 `app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["仪表盘"])`；清理或修复已废弃的 quality/pages/panels/scenes/bubbles 路由。

### C5. 迁移脚本与 ORM 模型严重不一致 → 全新部署角色/排版写入必崩 — HIGH
- **位置**：`backend/migrations/versions/f059c9246c6d_...py`
- **问题**：`characters` 表缺模型要求的 `aliases`/`description` 列；`layout_pages` 仍保留已废弃的 `image_prompt`/`image_url`/`reference_ids`/`shots`（NOT NULL）；`style_templates.width` 类型不一致（Integer vs String）；`projects.user_id` 类型/约束不一致。
- **触发**：干净库 `alembic upgrade head` 后，创建角色 → `column "aliases" does not exist` 500；生成排版 → `layout_pages` NOT NULL 违约，排版任务全失败。
- **修复**：基于当前 models `alembic revision --autogenerate` 重新对齐迁移。

### C6. `recover_images` 补图功能在任何输入下都无法工作 — HIGH
- **位置**：`backend/app/modules/image_recovery/service.py:143`
- **问题**：(1) 查询 LayoutPage 未 `selectinload(shots)`，async 上下文访问 `p.shots` 触发同步懒加载 → `MissingGreenlet`；(2) 代码把 `LayoutShot` ORM 对象当 dict（`isinstance(shots[0], dict)` 恒 False → `first_shot={}` → shot_id 永远空）。
- **修复**：查询加 `.options(selectinload(LayoutPage.shots))`，按 ORM 对象取值 `first_shot = min(p.shots, key=lambda s: s.sort_order); shot_id = first_shot.shot_id`；映射键加章节维度。

### C7. 系统日志搜索对 JSON 列用 `ilike` → 带关键词必定 500 — MEDIUM
- **位置**：`backend/app/routers/system.py:414`
- **问题**：`SystemLog.details` 是 `Column(JSON)`，`details.ilike(...)` 在 PostgreSQL 无 `json ~~* text` 操作符 → `UndefinedFunctionError` → 500。
- **修复**：`cast(SystemLog.details, Text).ilike(f"%{search}%")`，或改搜 action/module 字符串列。

---

## 三、数据损坏 / 业务逻辑错误

### D1. 章节重编号使用 `created_at` 倒序列表 → 全书章节顺序被颠倒 — HIGH
- **位置**：`backend/app/modules/novel/service.py:194`（`preprocess_novel`）
- **问题**：`chapter_repo.list_all(novel_id)` 默认 `order_by created_at.desc()`，`enumerate` 赋号后最后一章变第 1 章。
- **触发**：上传小说后执行预处理（主流程必经步骤），全书章节编号与故事顺序完全相反，后续脚本/分镜/排版全部基于错误顺序。
- **修复**：重编号前显式 `sorted(..., key=lambda c: c.chapter_number)`，或 `list_all(order_by=Chapter.chapter_number.asc())`。

### D2. `extract_characters_from_novel` 表级 DELETE 删角色 → 外键违约崩溃 — HIGH
- **位置**：`backend/app/modules/character/service.py:289`
- **问题**：`Character.__table__.delete()` 绕过 ORM 级联，而迁移中子表（states/outfits/reference_images/relations）外键均无 `ON DELETE CASCADE`（PostgreSQL 强制），旧角色有任何子记录即触发 `ForeignKeyViolation`。
- **触发**：首次提取或生成过角色形象后，再次「提取角色」→ 写库阶段 `IntegrityError` → 事务回滚，LLM 结果作废，功能对有数据的项目永久失败。
- **修复**：先显式删子表记录再删 Character，或逐个 `session.delete(character)` 触发级联，或迁移补 `ondelete='CASCADE'`。

### D3. 导出完全忽略 `chapter_id` → 单章导出实际导出整个项目所有页 — HIGH
- **位置**：`backend/app/modules/export/service.py:193`
- **问题**：`create_export_task` 把 `chapter_id` 存入 input_data，但 `_process_export` 只读 format/quality/add_alias/alias_name，查询仅按 `Novel.project_id` 拉全项目所有页；不同小说的 `page_label`（各自 P1、P2…）互相冲突覆盖。
- **触发**：选「仅导出第 3 章」，实际导出全项目所有小说所有章节，多小说时同名 P1.png 相互覆盖。
- **修复**：查询按 `LayoutChapter.id == chapter_id` 过滤（无则至少限 novel_id）；文件名加小说/章节前缀。

### D4. `split_shot` 全局递增所有后续章节的 shot_id → 破坏其他章节映射 — HIGH
- **位置**：`backend/app/modules/script/service.py:249`
- **问题**：拆分镜头时把「当前镜头之后的所有镜头」跨全部章节 `shot_id+1`，但 shot_id 是按章编号的；StoryboardShot/LayoutShot 中的旧 shot_id 不变，导致按 `(chapter, shot_id)` 关联的剧本内容全部错位。
- **触发**：第 1 章拆分镜头 → 第 2 章的分镜/排版里每个镜头显示的剧本内容整体错位一位，后续按 shot_id 的匹配（如补图）全部错乱。
- **修复**：只对被拆分镜头所在章节内、sort_order 更大的 ScriptShot 递增 shot_id，不跨章节；同步更新该章下游或标记为 stale。

### D5. 单页重生成不清理旧 GeneratedImage 记录 → 导出时同页重复拼接 — HIGH
- **位置**：`backend/app/modules/generation/service.py:228`
- **问题**：重新生成直接 add 一条新 `GeneratedImage(is_selected="selected")`，不删旧记录（image_recovery 同样）；export 用 INNER JOIN 且不去重、不按 is_selected 过滤，一条记录一行。
- **触发**：对 P5 点「重新生成」一次后导出 → P5 出现两行 → 长图模式拼接两遍，每再生成一次多重复一次。
- **修复**：写入前 `sa_delete(GeneratedImage).where(page_id==...)`，或改 UPDATE；导出查询按 page_id 去重。

### D6. `merge_chapters` 未校验源==目标 → 自并导致整章被删 — MEDIUM
- **位置**：`backend/app/modules/novel/service.py:529`
- **问题**：无 `source_chapter_id == target_chapter_id` 守卫。相同时先把段落复制追加到自身，再 `delete(source_chapter_id)` 删掉的就是目标本身，段落随 cascade 一起删。
- **触发**：`POST .../chapters/{id}/merge` 且 target 等于 path chapter_id → 该章及全部段落永久删除，还返回 `merged: true`。
- **修复**：方法开头加 `if source==target: raise ValueError("源章节与目标章节不能相同")`。

### D7. 重新提取世界观资产更换全部 UUID → 已保存参考图匹配全部失效且无法重匹配 — MEDIUM
- **位置**：`backend/app/modules/world/service.py:192`
- **问题**：`ai_extract_scene_assets/props/buildings/outfits` 先 DELETE 再重建（全新 UUID），`ReferenceMatch.ref_ids` 中旧 UUID 全成死链；生成图时静默跳过无效 ID，而 `match_references` 又跳过 ref_ids 非空的页面 → 死 ID 既不生效也无法自动修复。
- **触发**：完成参考图匹配后重新提取场景/道具 → 所有页 ref_ids 变死链，参考图静默丢失，重点匹配也被跳过，必须手动逐页清空。
- **修复**：按 name 做 upsert 保留原 id；或重建后按「旧 id→新 id」映射修正 ref_ids；至少清空受影响页面的 ReferenceMatch。

### D8. `split_chapter` 把后半章编号为 max+1 → 拆分结果排到全书末尾 — MEDIUM
- **位置**：`backend/app/modules/novel/service.py:594`
- **问题**：新章节 `chapter_number = max+1`，重编号只做致密化，后半章永远排到最后。
- **触发**：5 章小说拆第 2 章 → 后半变第 6 章，阅读顺序变 1,2(前),3,4,5,2(后)。
- **修复**：先把 `chapter_number > 原章节` 的全部 +1，再以原编号+1 创建新章节。

### D9. `duplicate_project` 风格模板复制被错误嵌套在 `copy_world_settings` 分支内 — MEDIUM
- **位置**：`backend/app/routers/projects.py:270`
- **问题**：`if data.copy_layout_templates:` 被缩进在 `if data.copy_world_settings:` 内部，只有同时勾选世界观才复制风格模板，与两个独立开关的语义矛盾。
- **触发**：`copy_world_settings:false, copy_layout_templates:true` → 返回成功但新项目无 StyleTemplate，后续生图取不到默认风格。
- **修复**：把 `if data.copy_layout_templates:` 反缩进到同级；顺带处理未实现的 copy_storyboard_templates/copy_prompt_templates/copy_images 开关。

### D10. 恢复状态形象图时读取未 flush 的 `state_char.id`（恒 None）→ 状态图被存为默认形象 — MEDIUM
- **位置**：`backend/app/modules/character/service.py:337`
- **问题**：`CharacterState.id` 是列级 default，未 flush 时为 None，`CharacterReferenceImage(state_id=state_char.id)` 实际写 NULL（表示"默认形象"）。
- **触发**：重提取时某状态命中 old_image_map → 参考图 state_id 为 NULL，与默认形象串图，状态本身仍无图。
- **修复**：先 `add` + `await flush()` 让 id 生成后再构造 state_ref，或构造时显式 `id=uuid.uuid4()`。

---

## 四、前端编辑器缺陷

### F1. undo/redo 差一错误：首次撤销无效、连续撤销跳步、最新状态永久丢失 — HIGH
- **位置**：`frontend/src/stores/editorStore.ts:300`
- **问题**：所有变更都是「先 saveSnapshot（存修改前）再改」，当前状态从未入栈；而 undo 恢复 `history[index-1]`。只改过一次时 undo 只把 index 设 -1、画布不还原（无效）；改过两次时一次 undo 回退两步；最新状态从未快照，redo 永远丢最后一次修改。
- **修复**：改「修改后快照」模型，或 undo 前先把当前状态压栈、恢复 `history[index]` 再 `index--`，redo 对称。

### F2. 拖拽 Panel 把 Group 偏移量当绝对坐标写回 → 位置跳变且脏数据被持久化 — HIGH
- **位置**：`frontend/src/components/editor/PanelWithImage.tsx:36`
- **问题**：`draggable` 加在无受控 x/y 的 Group 上，`onDragEnd` 里 `e.target.x()` 返回的是拖拽 delta 而非新绝对坐标，写回后渲染位置变成 `group.x + panel.x = 2*delta`，面板"弹回"且坐标已被改错。
- **修复**：`<Group x={panel.x} y={panel.y} draggable>`，子 Rect/Text 改用相对坐标 `x={0} y={0}`，则 `e.target.x()` 即新绝对坐标。

### F3. thinking 气泡（Ellipse）拖拽后坐标错位，每拖一次向右下偏移半个尺寸 — HIGH
- **位置**：`frontend/src/components/editor/BubbleShape.tsx:119`
- **问题**：Ellipse 的 x/y 是中心点，但共用 onDragEnd 直接把中心坐标存为 bubble.x/y（左上角语义），重渲染又加 width/2、height/2。
- **修复**：thinking 分支 `onDragEnd(e.target.x() - width/2, e.target.y() - height/2)`。

### F4. `PageThumbnails` useParams 参数名与路由不符 → 页面缩略图点击完全失效 — HIGH
- **位置**：`frontend/src/components/editor/PageThumbnails.tsx:10`
- **问题**：路由是 `projects/:id/editor/:pageId`，组件却 `useParams<{projectId}>()` 取 `projectId`（恒 undefined），`if (projectId)` 恒 false，navigate 从不执行。
- **修复**：`const { id: projectId } = useParams<{ id: string }>()`。

### F5. `handleSave` 不 await 异步 save() → 保存失败仍提示"保存成功" — MEDIUM
- **位置**：`frontend/src/pages/editor/[pageId].tsx:218`
- **问题**：`save` 是 async 且失败会 throw，但 handleSave 同步调用后立刻 `message.success`，不等待不捕获。
- **触发**：后端不可用/token 失效时 PUT 500/401，界面仍弹"保存成功"，用户关闭页面丢失全部编辑，并产生 unhandled rejection。
- **修复**：`try { await save(projectId); message.success('保存成功') } catch { message.error('保存失败') }`。

### F6. `markDirty` 从未被调用 → useBeforeUnload 离开警告全部失效 — MEDIUM
- **位置**：`story-breakdown/detail.tsx`、`storyboard/project-storyboard.tsx`、`generation/index.tsx`、`layout/project-layout.tsx`
- **问题**：设计上编辑时应调 `markDirty()` 置 saveStatus='unsaved'，但全仓无任何调用点，四个页面的 useBeforeUnload 全是死代码。
- **触发**：在剧情拆解页手改几十条镜头文案（仅存前端 store）未保存，关闭标签页无任何确认框，编辑直接丢失。
- **修复**：在各本地编辑回调中调用 `markDirty()`。

### F7. Transformer 缩放后未同步节点位移 → 保存重载后气泡位置错误 — MEDIUM
- **位置**：`frontend/src/components/editor/BubbleShape.tsx:48`
- **问题**：`handleTransformEnd` 只把 scale 换算成 width/height，从 top-left/top-right/bottom-left 锚点缩放时改变的 x/y 未写回 store。
- **触发**：用左上角锚点放大气泡后 Ctrl+S 刷新，气泡以旧 x/y + 新尺寸渲染，位置偏移。
- **修复**：transform 结束时同时读 `node.x()/node.y()`（thinking 需换算）连同 width/height 一起 updateBubble。

---

## 五、前端网络 / 竞态

### N1. 401 拦截器未排除 `/auth/login` → 登录失败触发整页跳转，错误提示永不显示 — MEDIUM
- **位置**：`frontend/src/api/client.ts:67`
- **问题**：对所有 401（仅排除 `/auth/refresh`）先尝试 refresh，失败即 `logout()` → `window.location.href='/login'` 整页跳转。登录密码错误的 401 也走进此分支，`message.error('用户名或密码错误')` 被页面刷新冲掉；且用 `refreshError` 替换了原始 401，丢失服务端 detail。
- **修复**：进入刷新分支前排除 `/auth/login`，对其 401 直接 `return Promise.reject(error)`；刷新失败时 reject 原始 error。

### N2. `startPolling` 不清理旧轮询循环，并发任务互相覆盖并误触发对方完成回调；卸载后轮询永续 — MEDIUM
- **位置**：`frontend/src/hooks/useTaskProgress.ts:47` / `:84`（`useMultiTaskProgress.ts` 同）
- **问题**：(1) 开新任务前不 `clearTimeout`，两条循环共享同一 timerRef 与 state，旧任务先完成会调 stopPolling 清掉新任务定时器并触发 onCompleted；(2) 卸载 cleanup 只清当前定时器，若请求在途则返回后又 `setTimeout(fetchStatus)`，轮询在卸载后无限继续（setState 泄漏）。
- **触发**：先点「生成提示词」（A 轮询）再点「生成图片」（B startPolling），A 先完成时页面误认为图片已完成并重置 loading，B 真实进度不再更新；或运行中切换路由，请求在途返回后每 2 秒持续请求。
- **修复**：startPolling 开头 `clearTimeout` 并引入代次标识（`generationRef.current++`，fetchStatus 闭包捕获自身代次，await 返回后不匹配则 return）；卸载/停止同样递增代次使 in-flight 回调失效。

### N3. 全局搜索无防抖、无竞态保护 → 慢的旧响应覆盖新关键词结果 — MEDIUM
- **位置**：`frontend/src/components/SearchBar.tsx:117`
- **问题**：每次 onChange 直接发请求，无防抖、无请求序号/AbortController，响应乱序时旧关键词结果覆盖新结果。
- **修复**：引入请求序号（响应回来比对是否最新）或 AbortController，加 200-300ms 防抖。

### N4. 部分 store 缺请求 ID 防竞态守卫 → 慢的旧响应覆盖新结果 — LOW
- **位置**：`frontend/src/stores/characterStore.ts:38`（fetch 全系列）、`worldStore`（fetchWorld/fetchWorlds/fetchSceneAssets 等）
- **问题**：projectStore/editorStore 等已加请求 ID 守卫，但 characterStore/worldStore 未加，直接 set 响应。
- **触发**：角色页搜 'a'（慢）后 allowClear 清空（快），空搜索先返回，随后 'a' 的旧响应覆盖成过滤结果，与空搜索框不一致。
- **修复**：套用同款 `_requestId` 计数守卫。

### N5. `fetchChapterDetail` 用 `Date.now()` 作请求 ID → 同毫秒两次调用守卫失效 — LOW
- **位置**：`frontend/src/stores/novelStore.ts:188`
- **问题**：其他 store 用单调递增计数器，唯独此处用 `Date.now()`，同毫秒两次调用 requestId 相同，防竞态守卫失效。
- **修复**：改用 `get()._chapterDetailRequestId + 1`。

### N6. 任务中心无初始数据加载 → 打开/筛选/翻页后最长 5 秒空白无 loading — MEDIUM
- **位置**：`frontend/src/pages/tasks/index.tsx:57`
- **问题**：数据获取只由 5 秒 setInterval（silent=true）驱动，无挂载/依赖变化时的立即请求。
- **触发**：进入任务中心看到空列表（无 loading），5 秒后才出现；切筛选后最长 5 秒仍显示旧数据。
- **修复**：effect 中启动 interval 前先 `fetchTasks()`（首次非 silent）。

### N7. 项目卡片「复制」「归档」图标未阻止事件冒泡 → 点击同时触发卡片导航 — LOW
- **位置**：`frontend/src/pages/projects/index.tsx:505`
- **问题**：Card 有 onClick 导航，删除图标已 `stopPropagation`，但 CopyOutlined/InboxOutlined 未阻止冒泡。
- **触发**：点「复制」图标时同时跳转到项目详情页，看不到复制结果。
- **修复**：`onClick={(e) => { e.stopPropagation(); onDuplicate(project) }}`，归档同理。

---

## 六、基础设施 / 并发

### I1. `os.makedirs(path, exist_ok)` 位置参数被当作 mode → Linux 部署目录权限损坏 — MEDIUM
- **位置**：`backend/app/infra/file_utils.py:41`
- **问题**：签名是 `makedirs(name, mode=0o777, exist_ok=False)`，`to_thread(os.makedirs, path, exist_ok)` 把 True 绑到 mode（=1，权限 0o001），真正的 exist_ok 保持 False。Windows 忽略 mode 暂无症状，Linux 上创建的目录属主自己都无读写执行权。
- **触发**：Linux 非 root 部署，生图创建存储目录后，`write_bytes_atomic` 在该目录建临时文件抛 PermissionError，所有图片保存、角色图、补图全部失败。
- **修复**：`to_thread(lambda: os.makedirs(path, exist_ok=exist_ok))` 或 `functools.partial`。

### I2. `APP_SECRET_KEY` 生产校验读 `os.getenv` 而非 .env 解析值 → 防线失效 — MEDIUM
- **位置**：`backend/app/core/config.py:59`
- **问题**：校验器用 `os.getenv("APP_ENV")` 判断环境，而 APP_ENV 来自 .env 文件不在进程环境变量里，返回 None，raise 分支永不触发（同文件 init_db 用 `settings.APP_ENV`，口径不一）。
- **触发**：生产 .env 写 `APP_ENV=production` 但忘设 SECRET_KEY，本应启动报错，实际静默生成随机密钥 → 每次重启用户被集体登出；多 worker 时各 worker 密钥不同，认证间歇性 401。
- **修复**：校验器改用 `model_validator(mode="after")` 读 `self.APP_ENV`，或用 `info.data.get("APP_ENV")`。

### I3. WebSocket `broadcast` 对每个订阅者 send 无超时 → 一个死连接阻塞全部任务进度 — MEDIUM
- **位置**：`backend/app/infra/websocket.py:93`
- **问题**：`broadcast` 用 `gather` 等所有 send 完成，`ws.send_json` 无超时。某客户端半死连接的发送缓冲区被填满后 send 无限挂起，整个 broadcast 挂起；而进度上报内联 `await _broadcast()`，全局订阅者是每条 task_update 的目标 → 一个卡死的看板客户端冻结所有运行中任务的进度。
- **修复**：`asyncio.wait_for(ws.send_json(msg), timeout=5)` 包裹，超时视为失败清理该订阅者；或改 fire-and-forget + 有界队列。

### I4. 查重与任务创建之间 TOCTOU 竞态 → 可产生并发重复任务 — MEDIUM
- **位置**：`backend/app/infra/task_progress.py:217`、`backend/app/routers/novels.py:503`（各 generate_* 端点）
- **问题**：先 SELECT 查有无同类 queued/running 任务，再在独立 session INSERT，两步间无锁/无约束，并发请求都查到 None 各自建任务。
- **触发**：双击「生成分镜」→ 两个 POST 并发通过检查 → 起两条 LLM 管线，重复消耗 API 费用并对同一 novel 删除重建互相覆盖。
- **修复**：给 `(project_id, task_type, novel_id)` 加部分唯一索引（`WHERE status IN ('queued','running')`），冲突时返回已有任务；或用 PG advisory lock 串行化。

### I5. `recover_images` 任务 input_data 未存凭证 → 重试必然失败 — MEDIUM/LOW
- **位置**：`backend/app/routers/novels.py:124` / `:487`
- **问题**：创建补图任务时 input_data 只存 `{"novel_id"}`，但 `_redispatch_recover_images` 从 input_data 取 `authorization`/`xtx`（从未写入）→ 重试时空凭证，limit 也从请求值变成硬编码默认。
- **触发**：补图失败后点「重试」→ 用空凭证调 GRS AI → 全部 401，任务再次 failed，重试多少次都不成功且错误指向外部 API。
- **修复**：创建时把 authorization/xtx/limit 写入 input_data（可加密）；或对该类任务直接返回"不支持重试/请重新提交凭证"。

### I6. `init_db` 创建默认管理员无并发保护 → 多 worker 启动可因唯一约束冲突崩溃 — LOW
- **位置**：`backend/app/core/database.py:60`
- **问题**：lifespan 里「查 admin 不存在则 INSERT」，`username` 唯一。多 worker 首次对空库启动时同时 INSERT，后到者 commit 抛 `IntegrityError` 无捕获，worker 启动失败。
- **修复**：`INSERT ... ON CONFLICT (username) DO NOTHING`，或捕获 IntegrityError 回滚忽略。

---

## 七、LLM / 适配器健壮性

### L1. `HTTPStatusError` 处理中 `aread()` 必因流已关闭失败 → 错误响应体恒空，Cloudflare 检测成死代码 — MEDIUM
- **位置**：`backend/app/infra/adapters/llm_adapter.py:266`
- **问题**：`raise_for_status()` 在 `async with client.stream(...)` 块内抛出，异常先穿过 __aexit__ 关闭流，外层再对已关闭流 `await e.response.aread()` → `StreamClosed` 被内层 except 吞掉，body 恒空 → `if "Cloudflare" in body` 永不触发，4xx/5xx 响应体永远进不了日志。
- **修复**：在 stream 上下文内、raise_for_status 前 `if resp.status_code >= 400: await resp.aread()` 再 raise，使异常携带已缓存 content。

### L2. `Retry-After` 为 HTTP 日期格式时 `float()` 抛 ValueError → 重试崩溃且错误误导 — LOW
- **位置**：`backend/app/infra/adapters/llm_adapter.py:281`、`grsai_api_adapter.py:162`
- **问题**：`delay = float(retry_after)`，但 Retry-After 允许 HTTP-date，`float()` 抛 ValueError 且发生在 except 内不被捕获，直接冒泡，业务层收到"could not convert string to float"而非限流提示。
- **修复**：`try: delay = min(float(retry_after), 60) except (TypeError, ValueError): delay = 2 ** attempt`，两个 adapter 同步改。

### L3. LLM 返回 JSON 数组时 `parsed.items()` 抛 AttributeError → 跳过降级路径，整个 Agent 失败 — LOW
- **位置**：`backend/app/infra/agents/bubble_planner.py:218`（storyboard_planner.py:144、camera_planner.py:161 类似）
- **问题**：except 只捕 `(JSONDecodeError, IndexError, ValueError)`，LLM 返回顶层数组时 `parsed.items()` 抛 AttributeError，越过「对每个 Panel 规则重试」的降级分支直接失败。
- **修复**：`json.loads` 后校验 `isinstance(parsed, dict)`，为 list 则按位置映射或走降级；except 扩展 `AttributeError, TypeError`。

### L4. LLM 返回非纯数字 key 时 `panel_index` 兜底为 0 → 所有气泡塌缩覆盖到第一个 Panel — LOW
- **位置**：`backend/app/infra/agents/bubble_planner.py:231`
- **问题**：`int(key)-1 if key.isdigit() else 0`，LLM 常返回 "Panel 1"/"panel_2"，全被映射到 panels[0] 反复覆盖，最终只有第一个 Panel 拿到（最后一个 key 的）气泡。
- **修复**：用 `re.search(r'\d+', key)` 提取数字，失败则 `continue`；循环后对未覆盖 panel 补降级。

### L5. 批次内 Panel 编号用固定 `BATCH_SIZE`，与动态 batch_size 不一致 → 提示词序号跳号 — LOW
- **位置**：`backend/app/infra/agents/storyboard_planner.py:95`、`camera_planner.py:103`
- **问题**：实际 `batch_size = min(BATCH_SIZE, max(5, len//3+1))`（可能 5-8），但编号用 `i+1+batch_index*BATCH_SIZE`（固定 8），跨批跳号。
- **修复**：把实际 batch_size 作为参数传入 `_process_batch`，编号用 `i+1+batch_index*batch_size`。

### L6. `text_cleaner` 引号归一化两次 replace 源字符相同 → 闭引号从文本中永久消失 — LOW
- **位置**：`backend/app/infra/agents/text_cleaner.py:65`
- **问题**：`.replace('"','“').replace('"','”')` 两次搜索都是同一 ASCII 双引号，第一次全换成左引号后第二次匹配不到；单引号同理。（该 Agent 目前尚未接线，属休眠缺陷）
- **修复**：按配对状态交替替换（奇数次 → 左引号，偶数次 → 右引号），或干脆不做直引号转弯引号。

---

## 八、死代码 / Windows 特定

### O1. `scene` 模块 import 不存在的 `app.models.scene` → 该模块无法导入 — LOW
- **位置**：`backend/app/modules/scene/service.py:23`、`repositories/scene_repo.py:2`
- **问题**：Scene/Panel 模型已删，但仍 `from app.models.scene import Scene, Panel`。目前 main.py 未注册 scenes/panels 路由所以能启动，但任何 import 都 `ModuleNotFoundError`。
- **修复**：删除 scene 模块与 scenes.py/panels.py/scene_repo.py 死代码；若需保留则恢复模型并补迁移。

### O2. `delete_all_*` 系列先删图片文件再执行 DB 事务 → DB 失败时留悬挂记录 — LOW
- **位置**：`backend/app/modules/generation/service.py:561`
- **问题**：先 `rmtree` 图片目录再打开写事务删记录，文件删除不可回滚，DB 删除失败则 image_url 指向已删文件。
- **修复**：先在事务中删 DB 记录并 commit，成功后再删文件目录。

### O3. `_set_file_times_windows` 的 `INVALID_HANDLE_VALUE` 判断错误 → 失败分支永不命中 — LOW
- **位置**：`backend/app/modules/export/service.py:387`
- **问题**：`CreateFileW` 未设 restype，默认按 c_int 返回 -1，而比较对象 `c_void_p(-1).value` 在 64 位是 18446744073709551615，永不相等；随后以无效句柄调 SetFileTime 静默失败。
- **修复**：设 `CreateFileW.restype = c_void_p` 并用 `c_void_p(-1).value` 比较，或判 `handle in (None, INVALID_HANDLE_VALUE)`。

### O4. `list_all_tasks` 对 project_id 直接 `UUID()` 未捕获 → 非法参数返回 500 — LOW
- **位置**：`backend/app/routers/tasks.py:195`
- **问题**：`project_id: Optional[str]` 直接 `UUID(project_id)`，非法值抛 ValueError → 500（同函数 date_from/date_to 都有 try/except）。
- **触发**：前端未选项目时常传字符串 "undefined" → `GET /tasks?project_id=undefined` → 500。
- **修复**：改 `Optional[UUID] = Query(None)` 让 FastAPI 自动 422，或 try/except 返回 400。

### O5. 上传小说先整体读入内存再判大小 → 大文件可打爆内存 — MEDIUM
- **位置**：`backend/app/routers/novels.py:67`
- **问题**：`contents = await file.read()` 先完整读入 bytes 再比较大小，100MB 上限对内存无保护。
- **触发**：上传 3GB .txt，服务端先分配 3GB 再返回 413，并发几个即可 OOM。
- **修复**：先校验扩展名，再分块读取累计大小超阈值立即 `raise HTTPException(413)`；或在反代/ASGI 层限制 body 大小。

---

## 建议修复顺序

1. **立即修（安全）**：S1 越权、S2 WebSocket 泄漏、S3 路径穿越、S4 refresh、S5 空 user_id 放行、S6 system/config。
2. **尽快修（核心崩溃）**：C1–C7（角色创建、复制项目、任务看板、首页、迁移、补图、日志搜索）。
3. **数据完整性**：D1 章节倒序、D2 外键崩、D3/D5 导出、D4 shot_id、D6 自并删章、D7 参考图失效。
4. **前端可用性**：F1 undo/redo、F2–F4 编辑器坐标/导航、F5/F6 保存与离开提示、N1 登录跳转、N2 轮询泄漏。
5. **健壮性收尾**：I1–I6、L1–L6、O1–O5。
