# AI Webtoon Factory — Git 工作流规范

> 版本：v1.0  
> 最后更新：2026-06-27  
> 状态：草案  
> 适用范围：所有参与 AI Webtoon Factory 项目开发的团队成员

---

## 1. 分支策略

采用 **Trunk-Based Development + Feature Branch** 混合模式，以 `develop` 为集成分支，`main` 为生产分支。

```
main          ●──────●────────────────────● (v1.0.0)
               \    /                    /
develop         ●──●──●────●────●────●──●
                   \    /    \
feature/xxx        ●──●      \
                              \
release/v1.1        ●──────────●──●
```

### 1.1 分支类型

| 分支类型 | 命名格式 | 来源 | 合并目标 | 生命周期 | 说明 |
|----------|----------|------|----------|----------|------|
| `main` | `main` | — | — | 永久 | 生产分支，只接受 `release/*` 或 `hotfix/*` 的合并 |
| `develop` | `develop` | `main` | `main` | 永久 | 开发主分支，所有 Feature 在此集成 |
| `feature/*` | `feature/<module>-<description>` | `develop` | `develop` | 功能开发完成后删除 | 新功能开发分支 |
| `bugfix/*` | `bugfix/<description>` | `develop` | `develop` | 修复完成后删除 | 非紧急 Bug 修复 |
| `release/*` | `release/v<major>.<minor>.<patch>` | `develop` | `main` + `develop` | 发布完成后删除 | 版本发布准备 |
| `hotfix/*` | `hotfix/<description>` | `main` | `main` + `develop` | 修复完成后删除 | 紧急生产修复 |

### 1.2 分支操作流程

#### 1.2.1 创建 Feature 分支

```bash
# 确保 develop 是最新的
git checkout develop
git pull origin develop

# 创建并切换到 feature 分支
git checkout -b feature/scene-panel-split

# 推送至远程
git push origin feature/scene-panel-split
```

#### 1.2.2 Feature 分支合并到 develop

```bash
# 1. 先 rebase develop
git fetch origin
git rebase origin/develop

# 2. 如果有冲突，解决冲突后继续 rebase
git add <resolved-files>
git rebase --continue

# 3. 推送（可能需要 force push）
git push origin feature/scene-panel-split --force-with-lease

# 4. 在 GitHub/GitLab 上创建 Pull Request
#    等待 CI 通过 + Code Review 通过
```

#### 1.2.3 创建 Release 分支

```bash
# 当 develop 达到可发布状态时
git checkout develop
git pull origin develop
git checkout -b release/v1.0.0

# 在 release 分支上只做 Bug 修复和文档更新
# 修复的 Bug 需要 cherry-pick 回 develop
```

#### 1.2.4 Release 分支合并到 main

```bash
# 合并到 main
git checkout main
git merge --no-ff release/v1.0.0
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin main --tags

# 合并回 develop
git checkout develop
git merge --no-ff release/v1.0.0
git push origin develop

# 删除 release 分支
git branch -d release/v1.0.0
git push origin --delete release/v1.0.0
```

### 1.3 分支保护规则

| 分支 | 保护规则 |
|------|----------|
| `main` | 禁止直接推送；仅允许通过 PR 合并；需要至少 1 人 Code Review；CI 必须通过 |
| `develop` | 禁止直接推送；仅允许通过 PR 合并；CI 必须通过 |
| `feature/*` | 无保护，但推荐在 PR 前 rebase develop |

---

## 2. Commit 规范

### 2.1 提交信息格式

提交信息遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范。

```
<type>(<scope>): <subject>

<body>

<footer>
```

**示例：**

```
feat(agent): implement semantic split agent

- Add Scene → Panel splitting logic
- Support batch processing (5-10 panels per call)
- Add retry with exponential backoff

Closes #42
```

```
fix(scene): handle edge case with empty scene text

When a scene contains no text content, the agent now returns
a single placeholder panel instead of failing with a ValueError.

Fixes #58
```

```
refactor(panel): extract panel layout calculation to separate service

Panel layout logic was mixed with the API route handler. Moved
calculation logic to PanelLayoutService for testability.

No functional changes.
```

### 2.2 Type 类型

| Type | 用途 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(agent): implement text cleaning agent` |
| `fix` | Bug 修复 | `fix(api): fix pagination offset calculation` |
| `refactor` | 重构（不改变外部行为） | `refactor(service): extract validation logic` |
| `docs` | 文档变更 | `docs: add deployment guide` |
| `style` | 代码格式（不影响功能） | `style: format code with ruff` |
| `test` | 测试相关 | `test(agent): add unit tests for scene split` |
| `chore` | 工程化/依赖/CI | `chore(deps): upgrade fastapi to 0.110.0` |
| `perf` | 性能优化 | `perf(panel): cache panel layout calculation` |
| `ci` | CI 配置变更 | `ci: add GitHub Actions workflow` |

### 2.3 Scope 范围

| Scope | 所属层 | 说明 |
|-------|--------|------|
| `novel` | Backend/Agent | 小说管理模块 |
| `character` | Backend/Agent | 人物管理模块 |
| `scene` | Backend/Agent | 场景拆分模块 |
| `panel` | Backend/Agent | 分镜布局模块 |
| `prompt` | Backend/Agent | Prompt 生成模块 |
| `generation` | Backend/Agent | AI 生图模块 |
| `qc` | Backend/Agent | 质量控制模块 |
| `api` | Backend | API 路由层 |
| `service` | Backend | 服务层 |
| `agent` | Backend | Agent 层 |
| `model` | Backend | 数据模型层 |
| `db` | Backend | 数据库/迁移 |
| `frontend` | Frontend | 前端通用 |
| `editor` | Frontend | 漫画编辑器 |
| `export` | Both | 导出模块 |
| `deps` | Both | 依赖管理 |
| `ci` | Infra | CI/CD |

### 2.4 提交规则

#### 2.4.1 原子性

- **一个提交只做一件事**：将功能开发、重构、格式化、测试拆分为不同的提交。
- **保持提交粒度适中**：过大的提交难以 Review，过小的提交（如"fix typo"）可与相邻提交 squash。

#### 2.4.2 内容要求

- **正文（body）可选**：当 subject 不足以说明变更原因时，在 body 中补充。
- **关联 Issue**：使用 `Closes #42`、`Fixes #58` 等关键词关联 Issue。
- **破坏性变更**：在 body 中以 `BREAKING CHANGE:` 开头标记，并在 scope 后加 `!`，如 `feat(api)!: change panel response format`。

#### 2.4.3 禁止行为

- ❌ 禁止 `git commit -m "fix bug"` 等无意义信息。
- ❌ 禁止提交包含调试代码（`print()`、`console.log()`、`debugger`）。
- ❌ 禁止提交未解决冲突的合并标记。
- ❌ 禁止提交 .env 文件、凭据、密钥。

### 2.5 提交模板

```bash
# .gitmessage 模板文件内容
# feat/fix/refactor/docs/style/test/chore/perf/ci(scope): subject

# subject: 不超过 72 字，用英文祈使句，首字母小写，末尾无句号

# body（可选）：解释变更的"为什么"而非"是什么"
# 每行不超过 72 字符
# 可以使用列表

# footer（可选）：
# Closes #42
# Fixes #58
# BREAKING CHANGE: ...
```

使用方式：

```bash
git config commit.template .gitmessage
```

---

## 3. Pull Request 规范

### 3.1 PR 标题格式

```
[<Type>] <简要描述>
```

示例：

- `[Feat] 实现场景拆分 Agent`
- `[Fix] 修复面板排序越界问题`
- `[Refactor] 提取面板布局计算为独立 Service`

### 3.2 PR 描述模板

```markdown
## 变更说明

<!-- 简洁描述本次 PR 的目的和改动 -->

## 关联 Issue

<!-- 如果有关联 Issue，在此列出 -->

Closes #<issue_number>

## 变更类型

- [ ] 新功能 (feat)
- [ ] Bug 修复 (fix)
- [ ] 重构 (refactor)
- [ ] 性能优化 (perf)
- [ ] 测试 (test)
- [ ] 文档 (docs)
- [ ] 工程化 (chore)

## 测试说明

<!-- 说明如何验证本次变更 -->

- [ ] 单元测试已通过
- [ ] 手动测试已执行
- [ ] API 响应符合预期

## 截图/录屏（可选）

<!-- UI 变更请附截图 -->

## 检查清单

- [ ] 代码遵循项目编码规范
- [ ] 新增代码有对应的单元测试
- [ ] 所有测试通过
- [ ] Lint 无错误
- [ ] 文档已更新（如适用）
- [ ] 无调试代码残留
- [ ] 无敏感信息泄露
```

### 3.3 Code Review 规范

#### 3.3.1 Reviewer 职责

- **24 小时内响应**：工作日应在 24 小时内开始 Review。
- **关注逻辑正确性**：优先检查算法逻辑、边界条件、异常处理。
- **检查代码规范**：命名、注释、类型注解等是否符合编码规范。
- **拒绝低质量代码**：对于不符合标准的 PR，明确指出问题并要求修改。

#### 3.3.2 Review 评论规范

| 评论类型 | 标签 | 含义 |
|----------|------|------|
| 阻塞性问题 | `BLOCKING` | 必须修改后才能合并。如逻辑错误、安全漏洞 |
| 建议性改进 | `SUGGESTION` | 建议修改但非必须。如可读性优化、性能改进 |
| 疑问 | `QUESTION` | 对代码意图不明确时需要澄清 |
| 赞赏 | `PRAISE` | 对优秀实现的肯定 |

#### 3.3.3 CI 门禁

合并前必须满足以下条件：

1. ✅ **单元测试通过率 100%**
2. ✅ **集成测试通过率 100%**
3. ✅ **Lint 无错误**
4. ✅ **无合并冲突**
5. ✅ **至少 1 人 Code Review 通过**
6. ✅ **覆盖率未下降**

### 3.4 合并策略

| 场景 | 策略 | 命令 |
|------|------|------|
| Feature → Develop | **Squash Merge** | 将 feature 分支的所有提交压缩为一个，保持 develop 历史整洁 |
| Hotfix → Main | **Squash Merge** | 同上 |
| Release → Main | **Merge Commit (--no-ff)** | 保留发布分支的合并历史 |
| Release → Develop | **Merge Commit (--no-ff)** | 同上 |

**原则：**

- `develop` 分支历史保持线性整洁，使用 Squash Merge 合并 feature 分支。
- `main` 分支保留完整的合并点和 Tag，用于版本追溯。

---

## 4. 版本号规范

### 4.1 语义化版本

遵循 [SemVer 2.0](https://semver.org/) 规范：

```
MAJOR.MINOR.PATCH
  │     │     │
  │     │     └── PATCH：向下兼容的 Bug 修复
  │     └──────── MINOR：向下兼容的功能新增
  └────────────── MAJOR：不兼容的 API 变更
```

### 4.2 版本号生命周期

| 阶段 | 版本格式 | 说明 |
|------|----------|------|
| 开发阶段 | `0.MINOR.PATCH` | MAJOR=0 表示初始开发阶段，API 不稳定 |
| MVP 发布 | `1.0.0` | 首个稳定版本 |
| 正式版本 | `MAJOR.MINOR.PATCH` | 遵循 SemVer |
| 预发布 | `MAJOR.MINOR.PATCH-rc.N` | Release Candidate，如 `1.2.0-rc.1` |
| Beta | `MAJOR.MINOR.PATCH-beta.N` | Beta 版本，如 `1.2.0-beta.2` |

### 4.3 Tag 管理

```bash
# 创建标签
git tag -a v1.0.0 -m "Release v1.0.0 - MVP release"

# 推送标签
git push origin --tags

# 删除标签（如果打错）
git tag -d v1.0.0
git push origin --delete refs/tags/v1.0.0
```

---

## 5. 工作流规范

### 5.1 每日开发流程

```bash
# 1. 开始工作前同步 develop
git checkout develop
git pull origin develop

# 2. 基于最新 develop 创建/切换到 feature 分支
git checkout -b feature/my-feature

# 3. 日常开发：小步提交
git add -p
git commit -m "feat(scope): message"

# 4. 每天至少推送一次，避免代码丢失
git push origin feature/my-feature

# 5. 功能完成后，创建 PR
```

### 5.2 同步上游变更

```bash
# Feature 分支开发周期较长时，定期 rebase develop
git fetch origin
git rebase origin/develop

# 如果有冲突
# 1. 解决冲突
# 2. git add <resolved-files>
# 3. git rebase --continue
# 4. 强制推送
git push origin feature/my-feature --force-with-lease
```

### 5.3 紧急 Hotfix 流程

```bash
# 1. 从 main 创建 hotfix 分支
git checkout main
git pull origin main
git checkout -b hotfix/login-timeout

# 2. 修复并提交
git add -A
git commit -m "fix(auth): fix login timeout issue"

# 3. 创建 PR 合并到 main 和 develop
#    （GitHub/GitLab 上分别创建两个 PR）

# 4. 合并到 main 后打 tag
git checkout main
git merge --no-ff hotfix/login-timeout
git tag -a v1.0.1 -m "Hotfix v1.0.1 - fix login timeout"
git push origin main --tags

# 5. 合并到 develop
git checkout develop
git merge --no-ff hotfix/login-timeout
git push origin develop

# 6. 删除 hotfix 分支
git branch -d hotfix/login-timeout
git push origin --delete hotfix/login-timeout
```

### 5.4 仓库管理规范

#### 5.4.1 `.gitignore` 必须包含的内容

```
# 环境变量
.env
.env.local
*.env

# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.ruff_cache/

# Node
node_modules/
dist/
.next/

# IDE
.idea/
.vscode/
*.swp
*.swo
*~

# 操作系统
.DS_Store
Thumbs.db

# 日志
*.log
logs/

# 上传文件（保留目录结构）
uploads/*
!uploads/.gitkeep

# 数据库
*.db
*.sqlite3

# CI
.coverage
htmlcov/
.pytest_cache/
```

#### 5.4.2 敏感信息管理

- **禁止将任何密钥、Token、密码提交到 Git 仓库。**
- 所有敏感配置通过环境变量注入，使用 `.env.example` 提供模板。
- 生产环境的密钥通过密钥管理服务（如 Vault、AWS Secrets Manager）获取。

---

## 6. 工具配置

### 6.1 Git Hooks

项目使用 [husky](https://typicode.github.io/husky/) 管理 Git Hooks（前端）和等效的 Python pre-commit hooks：

**pre-commit（Python）：**

```bash
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-merge-conflict
      - id: detect-private-key
```

**commit-msg（TypeScript）：**

```bash
# .husky/commit-msg
npx --no -- commitlint --edit $1
```

### 6.2 Commitlint 配置

```javascript
// commitlint.config.js
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'scope-enum': [2, 'always', [
      'novel', 'character', 'scene', 'panel', 'prompt',
      'generation', 'qc', 'api', 'service', 'agent',
      'model', 'db', 'frontend', 'editor', 'export',
      'deps', 'ci', 'docs'
    ]],
    'subject-case': [2, 'never', ['start-case', 'pascal-case', 'upper-case']],
  },
};
```

### 6.3 Python 版本管理

```bash
# 使用 .python-version 文件指定 Python 版本
echo "3.11" > .python-version
```

### 6.4 Node 版本管理

```bash
# 使用 .nvmrc 或 .node-version 文件
echo "18" > .nvmrc
```

---

## 附录 A：Git 命令速查

| 场景 | 命令 |
|------|------|
| 新功能开始 | `git checkout -b feature/my-feature develop` |
| 同步上游 | `git fetch origin && git rebase origin/develop` |
| 修改最后一个 commit | `git commit --amend` |
| 撤销暂存 | `git restore --staged <file>` |
| 丢弃未提交修改 | `git restore <file>` |
| 暂存当前工作 | `git stash -u` |
| 恢复暂存 | `git stash pop` |
| 交互式 rebase | `git rebase -i HEAD~N` |
| 查看分支图 | `git log --graph --oneline --all` |

## 附录 B：常见问题处理

### B.1 不小心在 develop 上提交了

```bash
# 撤销最近一次提交，保留修改内容
git reset --soft HEAD~1
# 创建正确的 feature 分支
git checkout -b feature/correct-branch
# 在 feature 分支上重新提交
git commit -m "feat(...): ..."
```

### B.2 需要从 develop 上摘取一个提交到 feature 分支

```bash
# 获取 develop 上的提交 hash
git log develop --oneline
# 在 feature 分支上 cherry-pick
git cherry-pick <commit-hash>
```

### B.3 合并冲突后回退

```bash
# 如果冲突太多或解决错误，放弃当前合并/变基
# 合并冲突时
git merge --abort
# 变基冲突时
git rebase --abort
```

---
