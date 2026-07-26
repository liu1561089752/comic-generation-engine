﻿﻿﻿﻿﻿﻿# AI Webtoon Factory API 设计文档

> **项目名称**: AI Webtoon Factory（AI韩漫工厂）
> **后端框架**: Python FastAPI
> **文档版本**: v1.0
> **最后更新**: 2026-06-27
> **状态**: 草案

---

## 目录

1. [API 概览](#1-api-概览)
2. [认证 API](#2-认证-api)
2.5. [Dashboard API](#25-dashboard-api)
3. [项目管理 API](#3-项目管理-api)
4. [小说管理 API](#4-小说管理-api)
5. [世界观 API](#5-世界观-api)
6. [人物 IP API](#6-人物-ip-api)
7. [剧情拆解 API](#7-剧情拆解-api)
8. [分镜 API](#8-分镜-api)
9. [版式 API](#9-版式-api)
10. [气泡 API](#10-气泡-api)
11. [Prompt API](#11-prompt-api)
12. [生图 API](#12-生图-api)
13. [质量控制 API](#13-质量控制-api)
14. [漫画编辑器 API](#14-漫画编辑器-api)
15. [导出 API](#15-导出-api)
16. [资源 API](#16-资源-api)
17. [模型 API](#17-模型-api)
18. [系统 API](#18-系统-api)
19. [搜索 API](#19-搜索-api)
20. [WebSocket API](#20-websocket-api)

---


## 1. API 概览

### 1.1 Base URL

`
/api/v1
`

### 1.2 认证方式

所有受保护的 API 均需在 HTTP Header 中携带 JWT Bearer Token：

`
Authorization: Bearer <token>
`

### 1.3 统一响应格式

**成功响应：**

`json
{
  "code": 200,
  "message": "success",
  "data": {},
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 100
  }
}
`

| 字段 | 类型 | 说明 |
|------|------|------|
| code | int | HTTP 状态码 |
| message | string | 响应消息 |
| data | object/array | 响应数据体 |
| meta | object | 分页元信息（仅列表接口） |

**错误响应：**

`json
{
  "code": 400,
  "message": "请求参数错误",
  "details": {
    "field": "title",
    "error": "标题不能为空"
  }
}
`

| 字段 | 类型 | 说明 |
|------|------|------|
| code | int | HTTP 错误状态码（4xx/5xx） |
| message | string | 错误描述 |
| details | object | 详细错误信息（可选） |

### 1.4 通用错误码

| Code | 含义 |
|------|------|
| 400 | 请求参数错误 |
| 401 | 未认证 / Token 失效 |
| 403 | 无权限访问 |
| 404 | 资源不存在 |
| 409 | 资源冲突（如重复创建） |
| 422 | 请求体校验失败 |
| 429 | 请求频率超限 |
| 500 | 服务器内部错误 |
| 502 | 上游 AI 服务异常 |
| 503 | 服务暂不可用 |

### 1.5 通用查询参数（列表接口）

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码，从 1 开始 |
| page_size | int | 20 | 每页条数，最大 100 |
| sort_by | string | created_at | 排序字段 |
| sort_order | string | desc | 排序方向：asc / desc |
| search | string | - | 全局关键词搜索 |

---

## 2. 认证 API

### 2.1 登录

> **POST** /api/v1/auth/login

**请求体：**

`json
{
  "username": "admin@example.com",
  "password": "password123"
}
`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名或邮箱 |
| password | string | 是 | 密码 |

**响应示例：**

`json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "dGhpcyBpcyBhIHJlZnJl...",
    "token_type": "bearer",
    "expires_in": 86400,
    "user": {
      "id": "u-001",
      "username": "admin@example.com",
      "nickname": "管理员",
      "avatar": "/static/avatars/default.png",
      "role": "admin"
    }
  }
}
`

**权限要求：** 无需认证

---

### 2.2 登出

> **POST** /api/v1/auth/logout

**请求头：**

`
Authorization: Bearer <token>
`

**请求体：** 无

**响应示例：**

`json
{
  "code": 200,
  "message": "登出成功",
  "data": null
}
`

**权限要求：** 需认证

---

### 2.3 获取当前用户信息

> **GET** /api/v1/auth/me

**请求头：**

`
Authorization: Bearer <token>
`

**响应示例：**

`json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "u-001",
    "username": "admin@example.com",
    "nickname": "管理员",
    "email": "admin@example.com",
    "avatar": "/static/avatars/default.png",
    "role": "admin",
    "created_at": "2026-01-01T00:00:00Z",
    "last_login": "2026-06-27T10:30:00Z",
    "project_count": 5
  }
}
`

**权限要求：** 需认证

---

## 2.5 Dashboard API

所有 Dashboard 接口以 `/api/v1/dashboard` 为前缀。

### GET /stats

获取 Dashboard 统计数据。

**响应格式**：
```json
{
  "data": {
    "stats": {
      "total_projects": 12,
      "active_projects": 3,
      "monthly_chapters": 18,
      "pending_review_images": 47,
      "total_generated_images": 1284
    },
    "recent_projects": [...],
    "production_progress": {...},
    "pending_tasks": [...]
  }
}
```

**权限**：需登录

---

## 3. 项目管理 API

### 3.1 项目列表

> **GET** /api/v1/projects

**查询参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| page | int | 否 | 1 | 页码 |
| page_size | int | 否 | 20 | 每页条数 |
| sort_by | string | 否 | updated_at | 排序字段 |
| sort_order | string | 否 | desc | 排序方向 |
| search | string | 否 | - | 搜索项目名称 |
| status | string | 否 | - | 筛选状态：draft / active / archived |

**响应示例：**

`json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "id": "proj-001",
      "name": "我的第一部Webtoon",
      "description": "基于玄幻小说的漫画改编项目",
      "cover": "/static/covers/proj-001.png",
      "status": "active",
      "novel_id": "nov-001",
      "novel_title": "星辰变",
      "progress": {
        "novel_imported": true,
        "novel_analyzed": true,
        "characters_created": 5,
        "scenes_created": 12,
        "chapters_planned": 3,
        "panels_generated": 48,
        "panels_total": 60,
        "images_generated": 45,
        "images_confirmed": 30
      },
      "created_at": "2026-06-01T00:00:00Z",
      "updated_at": "2026-06-27T12:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 1
  }
}
`

**权限要求：** 需认证

---

### 3.2 创建项目

> **POST** /api/v1/projects

**请求体：**

`json
{
  "name": "我的第一部Webtoon",
  "description": "基于玄幻小说的漫画改编项目",
  "cover": null,
  "tags": ["玄幻", "修仙"],
  "template_id": null
}
`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 项目名称，1-100 字符 |
| description | string | 否 | 项目描述 |
| cover | string(uuid) | 否 | 封面图片资源 ID |
| tags | string[] | 否 | 项目标签 |
| template_id | string | 否 | 从模板创建时传入模板 ID |

**响应示例：**

`json
{
  "code": 200,
  "message": "项目创建成功",
  "data": {
    "id": "proj-002",
    "name": "我的第一部Webtoon",
    "description": "基于玄幻小说的漫画改编项目",
    "cover": null,
    "status": "draft",
    "tags": ["玄幻", "修仙"],
    "created_at": "2026-06-27T12:00:00Z"
  }
}
`

**权限要求：** 需认证

---

### 3.3 项目详情

> **GET** /api/v1/projects/{id}

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| id | string | 项目 ID |

**响应示例：**

`json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "proj-001",
    "name": "我的第一部Webtoon",
    "description": "基于玄幻小说的漫画改编项目",
    "cover": "/static/covers/proj-001.png",
    "status": "active",
    "tags": ["玄幻", "修仙"],
    "novel_id": "nov-001",
    "novel_title": "星辰变",
    "novel_status": "analyzed",
    "character_count": 5,
    "scene_count": 12,
    "chapter_count": 3,
    "panel_count": 60,
    "image_count": 45,
    "progress_percentage": 75,
    "created_at": "2026-06-01T00:00:00Z",
    "updated_at": "2026-06-27T12:00:00Z"
  }
}
`

**权限要求：** 需认证

---

### 3.4 更新项目

> **PUT** /api/v1/projects/{id}

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| id | string | 项目 ID |

**请求体：**

`json
{
  "name": "更新后的项目名",
  "description": "更新后的描述",
  "cover": "res-cover-001",
  "tags": ["玄幻", "修仙", "热血"]
}
`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 否 | 项目名称 |
| description | string | 否 | 项目描述 |
| cover | string | 否 | 封面资源 ID |
| tags | string[] | 否 | 项目标签 |

**响应示例：**

`json
{
  "code": 200,
  "message": "项目更新成功",
  "data": {
    "id": "proj-001",
    "name": "更新后的项目名",
    "updated_at": "2026-06-27T13:00:00Z"
  }
}
`

**权限要求：** 需认证

---

### 3.5 删除项目

> **DELETE** /api/v1/projects/{id}

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| id | string | 项目 ID |

**响应示例：**

`json
{
  "code": 200,
  "message": "项目已删除",
  "data": null
}
`

**权限要求：** 需认证

---

### 3.6 复制项目

> **POST** /api/v1/projects/{id}/duplicate

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| id | string | 源项目 ID |

**请求体：**

`json
{
  "name": "我的第一部Webtoon（副本）",
  "include_images": true,
  "include_characters": true
}
`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 副本项目名称 |
| include_images | bool | 否 | 是否复制已生成的图片（默认 true） |
| include_characters | bool | 否 | 是否复制人物 IP（默认 true） |

**响应示例：**

`json
{
  "code": 200,
  "message": "项目复制成功",
  "data": {
    "id": "proj-003",
    "name": "我的第一部Webtoon（副本）",
    "source_id": "proj-001",
    "created_at": "2026-06-27T14:00:00Z"
  }
}
`

**权限要求：** 需认证

---

## 4. 小说管理 API

### 4.1 上传小说

> **POST** /api/v1/projects/{project_id}/novels/upload

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| project_id | string | 项目 ID |

**请求体：** multipart/form-data

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | file | 是 | 小说文件，支持 .txt / .docx / .md / .epub，最大 50MB |
| title | string | 否 | 小说标题（留空则从文件名提取） |
| author | string | 否 | 作者 |
| language | string | 否 | 语言代码（默认 zh-CN） |

**权限要求：** 需认证

### 4.2 小说详情

> **GET** /api/v1/projects/{project_id}/novels/{id}

### 4.3 章节列表

> **GET** /api/v1/projects/{project_id}/novels/{id}/chapters

### 4.4 章节详情

> **GET** /api/v1/projects/{project_id}/novels/{id}/chapters/{ch_id}

### 4.5 启动预处理

> **POST** /api/v1/projects/{project_id}/novels/{id}/preprocess

### 4.6 预处理结果

> **GET** /api/v1/projects/{project_id}/novels/{id}/preprocess/result

### 4.7 启动 AI 分析

> **POST** /api/v1/projects/{project_id}/novels/{id}/analyze

**权限要求：** 需认证

---

## 5. 世界观 API

### 5.1 世界观列表

> **GET** /api/v1/projects/{project_id}/worlds

### 5.2 创建世界观

> **POST** /api/v1/projects/{project_id}/worlds

### 5.3 更新世界观

> **PUT** /api/v1/projects/{project_id}/worlds/{id}

### 5.4 场景资产列表

> **GET** /api/v1/projects/{project_id}/scenes-assets

### 5.5 创建场景资产

> **POST** /api/v1/projects/{project_id}/scenes-assets

### 5.6 道具列表

> **GET** /api/v1/projects/{project_id}/props

### 5.7 创建道具

> **POST** /api/v1/projects/{project_id}/props

### 5.8 建筑列表

> **GET** /api/v1/projects/{project_id}/buildings

### 5.9 服装列表

> **GET** /api/v1/projects/{project_id}/outfits

**权限要求：** 需认证

---

## 6. 人物 IP API

### 6.1 人物列表

> **GET** /api/v1/projects/{project_id}/characters

### 6.2 创建人物

> **POST** /api/v1/projects/{project_id}/characters

### 6.3 人物详情

> **GET** /api/v1/projects/{project_id}/characters/{id}

### 6.4 更新人物

> **PUT** /api/v1/projects/{project_id}/characters/{id}

### 6.5 删除人物

> **DELETE** /api/v1/projects/{project_id}/characters/{id}

### 6.6 人物关系列表

> **GET** /api/v1/projects/{project_id}/characters/{id}/relations

### 6.7 创建人物关系

> **POST** /api/v1/projects/{project_id}/characters/{id}/relations

### 6.8 人物服装列表

> **GET** /api/v1/projects/{project_id}/characters/{id}/outfits

### 6.9 添加人物服装

> **POST** /api/v1/projects/{project_id}/characters/{id}/outfits

### 6.10 参考图列表

> **GET** /api/v1/projects/{project_id}/characters/{id}/reference-images

### 6.11 上传参考图

> **POST** /api/v1/projects/{project_id}/characters/{id}/reference-images

### 6.12 AI 生成表情

> **POST** /api/v1/projects/{project_id}/characters/{id}/generate-expressions

### 6.13 AI 生成姿势

> **POST** /api/v1/projects/{project_id}/characters/{id}/generate-poses

**权限要求：** 需认证

---

## 7. 剧情拆解 API

### 7.1 Scene 列表

> **GET** /api/v1/projects/{project_id}/chapters/{ch_id}/scenes

### 7.2 启动剧情分析

> **POST** /api/v1/projects/{project_id}/chapters/{ch_id}/analyze-story

### 7.3 Panel 列表

> **GET** /api/v1/projects/{project_id}/scenes/{scene_id}/panels

### 7.4 启动语义切句

> **POST** /api/v1/projects/{project_id}/scenes/{scene_id}/semantic-split

### 7.5 更新 Panel

> **PUT** /api/v1/projects/{project_id}/panels/{panel_id}

### 7.6 拆分 Panel

> **POST** /api/v1/projects/{project_id}/panels/{panel_id}/split

### 7.7 合并 Panel

> **POST** /api/v1/projects/{project_id}/panels/{panel_id}/merge

**权限要求：** 需认证

---

## 8. 分镜 API

### 8.1 获取分镜

> **GET** /api/v1/projects/{project_id}/panels/{panel_id}/storyboard

### 8.2 设置分镜

> **POST** /api/v1/projects/{project_id}/panels/{panel_id}/storyboard

### 8.3 AI 自动分镜

> **POST** /api/v1/projects/{project_id}/scenes/{scene_id}/auto-storyboard

### 8.4 锁定分镜

> **POST** /api/v1/projects/{project_id}/panels/{panel_id}/storyboard/confirm

**权限要求：** 需认证

---

## 9. 版式 API

### 9.1 页面列表

> **GET** /api/v1/projects/{project_id}/pages

### 9.2 创建页面

> **POST** /api/v1/projects/{project_id}/pages

### 9.3 更新页面（含布局）

> **PUT** /api/v1/projects/{project_id}/pages/{page_id}

### 9.4 重排页面

> **PUT** /api/v1/projects/{project_id}/pages/{page_id}/reorder

### 9.5 版式模板列表

> **GET** /api/v1/projects/{project_id}/layout-templates

### 9.6 创建版式模板

> **POST** /api/v1/projects/{project_id}/layout-templates

**权限要求：** 需认证

---

## 10. 气泡 API

### 10.1 气泡列表

> **GET** /api/v1/projects/{project_id}/panels/{panel_id}/bubbles

### 10.2 创建气泡

> **POST** /api/v1/projects/{project_id}/panels/{panel_id}/bubbles

### 10.3 更新气泡

> **PUT** /api/v1/projects/{project_id}/bubbles/{bubble_id}

### 10.4 删除气泡

> **DELETE** /api/v1/projects/{project_id}/bubbles/{bubble_id}

### 10.5 AI 自动规划气泡

> **POST** /api/v1/projects/{project_id}/panels/{panel_id}/auto-bubbles

### 10.6 AI 精简对白

> **POST** /api/v1/projects/{project_id}/bubbles/{bubble_id}/optimize-text

**权限要求：** 需认证

---

## 11. Prompt API

### 11.1 Prompt 版本列表

> **GET** /api/v1/projects/{project_id}/panels/{panel_id}/prompts

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码 |
| page_size | int | 否 | 10 |
| status | string | 否 | 筛选状态：draft / tested / selected / archived |

**权限要求：** 需认证

### 11.2 创建 Prompt 版本

> **POST** /api/v1/projects/{project_id}/panels/{panel_id}/prompts

**请求体：**

`json
{
  "layers": {
    "character": "Qin Yu, a young man with black short hair, determined eyes, wearing white cultivation robe",
    "environment": "Waterfall, bamboo forest, mountain cliff, misty atmosphere",
    "action": "Sitting in meditation pose on a green rock, hands forming a mudra",
    "emotion": "Calm, focused, serene",
    "camera": "Medium shot, eye level, static",
    "lighting": "Natural lighting, soft sunlight filtering through bamboo leaves, warm tones",
    "composition": "Rule of thirds, character positioned at left third, waterfall in background",
    "webtoon_style": "Webtoon style, clean lines, cel shading, Korean webtoon aesthetic",
    "bubble": "No speech bubble in this panel",
    "negative": "Blurry, low quality, deformed hands, extra limbs, bad anatomy"
  },
  "is_active": true
}
`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| layers | object | 是 | 10 层 Prompt 结构，每层为 string |
| layers.character | string | 是 | 角色描述 |
| layers.environment | string | 是 | 环境描述 |
| layers.action | string | 是 | 动作描述 |
| layers.emotion | string | 是 | 情绪描述 |
| layers.camera | string | 是 | 镜头类型 |
| layers.lighting | string | 是 | 光线设定 |
| layers.composition | string | 是 | 构图设定 |
| layers.webtoon_style | string | 是 | 画风设定 |
| layers.bubble | string | 否 | 气泡描述 |
| layers.negative | string | 否 | 负向 Prompt |
| is_active | bool | 否 | 是否设为当前激活版本 |

**权限要求：** 需认证

### 11.3 Prompt 详情（含 10 层 JSON）

> **GET** /api/v1/projects/{project_id}/prompts/{prompt_id}

**响应示例：**

`json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "prm-001",
    "panel_id": "pnl-001",
    "version": 1,
    "is_active": true,
    "status": "selected",
    "layers": {
      "character": { "raw": "Qin Yu, a young man with black short hair...", "variables": {} },
      "environment": { "raw": "Waterfall, bamboo forest...", "variables": {} },
      "action": { "raw": "Sitting in meditation pose...", "variables": {} },
      "emotion": { "raw": "Calm, focused, serene", "variables": {} },
      "camera": { "raw": "Medium shot, eye level, static", "variables": {} },
      "lighting": { "raw": "Natural lighting...", "variables": {} },
      "composition": { "raw": "Rule of thirds...", "variables": {} },
      "webtoon_style": { "raw": "Webtoon style, clean lines, cel shading, Korean webtoon aesthetic", "variables": {} },
      "bubble": { "raw": "No speech bubble in this panel", "variables": {} },
      "negative": { "raw": "Blurry, low quality...", "variables": {} }
    },
    "merged_prompt": "...",
    "token_count": 180,
    "score": 85,
    "created_at": "2026-06-27T14:00:00Z"
  }
}
`

**权限要求：** 需认证

### 11.4 更新 Prompt

> **PUT** /api/v1/projects/{project_id}/prompts/{prompt_id}

### 11.5 AI 自动生成 Prompt

> **POST** /api/v1/projects/{project_id}/panels/{panel_id}/generate-prompt

### 11.6 Prompt 测试（调用生图）

> **POST** /api/v1/projects/{project_id}/prompts/{prompt_id}/test

### 11.7 A/B 测试

> **POST** /api/v1/projects/{project_id}/prompts/{prompt_id}/ab-test

### 11.8 Prompt 模板列表

> **GET** /api/v1/projects/{project_id}/prompt-templates

**权限要求：** 需认证

---

## 12. 生图 API

### 12.1 创建生图任务

> **POST** /api/v1/projects/{project_id}/generate

### 12.2 任务状态

> **GET** /api/v1/projects/{project_id}/tasks/{task_id}

### 12.3 取消任务

> **POST** /api/v1/projects/{project_id}/tasks/{task_id}/cancel

### 12.4 任务列表

> **GET** /api/v1/projects/{project_id}/tasks

### 12.5 Panel 的候选图列表

> **GET** /api/v1/projects/{project_id}/panels/{panel_id}/images

### 12.6 选择最终图片

> **PUT** /api/v1/projects/{project_id}/images/{image_id}/select

### 12.7 图片详情

> **GET** /api/v1/projects/{project_id}/images/{image_id}

### 12.8 批量生图

> **GET** /api/v1/projects/{project_id}/panels/{panel_id}/generate-batch

**权限要求：** 需认证

---

## 13. 质量控制 API

### 13.1 启动一致性检测

> **POST** /api/v1/projects/{project_id}/images/{image_id}/check-consistency

### 13.2 获取检测报告

> **GET** /api/v1/projects/{project_id}/images/{image_id}/consistency-report

### 13.3 待审核列表

> **GET** /api/v1/projects/{project_id}/quality-check/pending

### 13.4 提交审核结果

> **POST** /api/v1/projects/{project_id}/quality-check/{check_id}/review

### 13.5 AI 质量评分

> **POST** /api/v1/projects/{project_id}/images/{image_id}/quality-score

### 13.6 质量统计

> **GET** /api/v1/projects/{project_id}/quality-stats

**权限要求：** 需认证

---

## 14. 漫画编辑器 API

### 14.1 编辑器页面列表

> **GET** /api/v1/projects/{project_id}/editor/pages

### 14.2 页面详情（含所有图层数据）

> **GET** /api/v1/projects/{project_id}/editor/pages/{page_id}

### 14.3 更新图层顺序

> **PUT** /api/v1/projects/{project_id}/editor/pages/{page_id}/layers

### 14.4 更新气泡位置

> **PUT** /api/v1/projects/{project_id}/editor/bubbles/{bubble_id}/position

### 14.5 添加特效

> **POST** /api/v1/projects/{project_id}/editor/effects

### 14.6 删除特效

> **DELETE** /api/v1/projects/{project_id}/editor/effects/{effect_id}

**权限要求：** 需认证

---

## 15. 导出 API

### 15.1 创建导出任务

> **POST** /api/v1/projects/{project_id}/export

### 15.2 导出状态

> **GET** /api/v1/projects/{project_id}/export/{export_id}

### 15.3 下载导出文件

> **GET** /api/v1/projects/{project_id}/export/{export_id}/download

### 15.4 导出历史

> **GET** /api/v1/projects/{project_id}/export/history

**权限要求：** 需认证

---

## 16. 资源 API

### 16.1 图片资源库

> **GET** /api/v1/projects/{project_id}/resources/images

### 16.2 Prompt 资源库

> **GET** /api/v1/projects/{project_id}/resources/prompts

### 16.3 模板资源库

> **GET** /api/v1/projects/{project_id}/resources/templates

**权限要求：** 需认证

---

## 17. 模型 API

### 17.1 LLM 模型列表

> **GET** /api/v1/models/llm-models

### 17.2 测试 LLM 连接

> **POST** /api/v1/models/llm-models/test

### 17.3 设置当前 LLM

> **PUT** /api/v1/models/llm-models/active

### 17.4 生图模型列表

> **GET** /api/v1/models/image-models

### 17.5 测试生图模型

> **POST** /api/v1/models/image-models/test

### 17.6 设置当前生图模型

> **PUT** /api/v1/models/image-models/active

### 17.7 模型参数预设

> **GET** /api/v1/models/model-params

**权限要求：** 需认证

---

## 18. 系统 API

### 18.1 系统统计

> **GET** /api/v1/system/stats

### 18.2 操作日志

> **GET** /api/v1/system/logs

### 18.3 手动备份

> **POST** /api/v1/system/backup

### 18.4 备份列表

> **GET** /api/v1/system/backups

### 18.5 从备份恢复

> **POST** /api/v1/system/backups/{backup_id}/restore

### 18.6 系统设置

> **GET** /api/v1/system/settings

### 18.7 更新系统设置

> **PUT** /api/v1/system/settings

**权限要求：** 需认证，需 admin 角色

---

## 19. 搜索 API

搜索接口以 `/api/v1/search` 为前缀。

### GET /

全局搜索。

**参数**：`q` (必填), `module` (可选：all/projects/novels/characters/scenes/tasks)

**权限**：需登录

---

## 20. WebSocket API

### 20.1 任务实时状态推送

> **WebSocket** ws://host/ws/tasks/{task_id}

**认证方式：** 通过 URL 参数传递 Token

`
ws://host/ws/tasks/task-060?token=<jwt_token>
`

**服务端推送消息格式：**

`json
{
  "type": "task_progress",
  "task_id": "task-060",
  "timestamp": "2026-06-27T14:00:30Z",
  "data": {
    "status": "processing",
    "progress": 45,
    "total": 6,
    "completed": 3,
    "failed": 0
  }
}
`

### 20.2 通知推送

> **WebSocket** ws://host/ws/notifications

**权限要求：** 需认证（Token 放在查询参数中）

---

## 附录

### A. 数据模型关系图

`
Project (1) ---▶ Novel (1) ---▶ Chapter (N) ---▶ Scene (N) ---▶ Panel (N)
  │                                                             │
  ├── World (N)                                                ├── Storyboard (1)
  ├── Character (N)                                            ├── Bubble (N)
  ├── SceneAsset (N)                                           ├── Prompt (N) ---▶ Image (N)
  ├── Prop (N)                                                 └── Image (N)
  ├── Building (N)                                                   │
  ├── Outfit (N)                                                    └── QualityCheck (N)
  ├── Page (N) ---▶ Layout
  ├── Task (N)
  └── Export (N)
`

### B. 路由前缀约定

| 前缀 | 说明 |
|------|------|
| /api/v1/auth/ | 认证相关，无需项目上下文 |
| /api/v1/projects/{project_id}/ | 项目级资源，需要项目 ID |
| /api/v1/settings/ | 系统设置，无需项目上下文 |
| /api/v1/system/ | 系统管理，需 admin 权限 |

### C. 通用 ID 命名规范

| 前缀 | 对应实体 |
|------|----------|
| proj- | Project（项目） |
| 
ov- | Novel（小说） |
| ch- | Chapter（章节） |
| sc- | Scene（场景） |
| pnl- | Panel（画格） |
| ub- | Bubble（气泡） |
| prm- | Prompt |
| img- | Image（图片） |
| pg- | Page（页面） |
| char- | Character（人物） |
| wld- | World（世界观） |
| 	ask- | Task（任务） |
| exp- | Export（导出） |
| u- | User（用户） |

---

> **文档结束**
