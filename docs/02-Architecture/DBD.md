# AI Webtoon Factory 数据库设计文档（DBD）

> **版本**：v1.0  
> **最后更新**：2026-06-27  
> **状态**：草案  
> **数据库**：PostgreSQL 15+（开发可用 SQLite 替代）  
> **ORM**：SQLAlchemy 2.0+（Async）  
> **迁移工具**：Alembic

---

## 目录

1. [数据层级总览](#1-数据层级总览)
2. [ER关系图](#2-er关系图)
3. [核心表定义](#3-核心表定义)
4. [索引策略](#4-索引策略)
5. [数据流向](#5-数据流向)
6. [迁移策略](#6-迁移策略)
7. [附录：命名规范](#7-附录命名规范)

---

## 1. 数据层级总览

AI Webtoon Factory 的核心数据模型采用树形层级结构，从小说到最终漫画图片，每一层逐步细化：

```
Project（项目）
  │
  ├── Novel（小说）
  │     └── Chapter（章节）
  │           ├── Scene（场景）
  │           │     └── Panel（画格）← 最核心的数据单元
  │           │           ├── Shot（镜头）
  │           │           ├── Bubble（气泡）
  │           │           │     ├── Narration（旁白）
  │           │           │     ├── Dialogue（对白）
  │           │           │     └── Thinking（内心独白）
  │           │           ├── Prompt（多个版本）
  │           │           └── Image（多个候选 → 选中1张）
  │           └── Page（漫画页面）
  │
  ├── WorldBuilding（世界观）
  │     └── SceneAsset（场景资产）
  │
  ├── Character（人物IP）
  │     ├── CharacterRelation（人物关系）
  │     ├── CharacterOutfit（人物服装）
  │     └── CharacterReferenceImage（人物参考图）
  │
  ├── StyleTemplate（风格模板）
  ├── Task（任务）
  ├── Plugin（插件）
  └── SystemLog（系统日志）
```

### 核心生产管线数据流向

```
Novel → Chapter → Scene → Panel → Prompt → Image
  │         │         │        │        │        │
  │         │         │        │        │        └── ConsistencyCheck
  │         │         │        │        └── (10层Prompt组装)
  │         │         │        └── Shot + Bubble + Page
  │         │         └── (语义切句 → Panel切分)
  │         └── (章节拆分)
  └── (导入+清洗)
```

---

## 2. ER关系图

### 2.1 项目-小说-章节-场景-画格 核心链路

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PROJECT (项目)                              │
└──────┬──────────────────────────┬───────────────────┬──────────────┘
       │                          │                   │
       ▼                          ▼                   ▼
┌────────────┐         ┌──────────────────┐  ┌──────────────────┐
│   NOVEL    │         │ WORLD_BUILDING   │  │   CHARACTER      │
│  (小说)    │1:N      │   (世界观)        │  │   (人物IP)       │
└──────┬─────┘         └──────────────────┘  └──────┬───────────┘
       │                                            │
       ▼ 1:N                                        │ 1:N
┌────────────┐         ┌──────────────────┐         │
│  CHAPTER   │1:N      │  SCENE_ASSET     │         │
│  (章节)    │────────▶│  (场景资产)       │         │
└──────┬─────┘         └──────────────────┘         │
       │                                            │
       ▼ 1:N                                        │
┌────────────┐         ┌──────────────────┐         │
│   SCENE    │1:N      │  CHARACTER_REL   │         │
│  (场景)    │         │  (人物关系)       │         │
└──────┬─────┘         └──────────────────┘         │
       │                                            │
       ▼ 1:N                                        │
┌────────────┐         ┌──────────────────┐         │
│   PANEL    │1:N      │  CHARACTER_OUTFIT│         │
│  (画格)    │         │  (人物服装)       │         │
└──┬───┬───┬─┘         └──────────────────┘         │
   │   │   │                                         │
   │   │   │         ┌──────────────────┐             │
   │   │   └────────▶│   CHARACTER_REF  │             │
   │   │             │  (人物参考图)     │             │
   │   │             └──────────────────┘             │
   │   │                                              │
   │   ▼ 1:N                                          │
   │ ┌────────┐      ┌──────────────────┐             │
   │ │  SHOT  │      │   BUBBLE ────────│─────────────┘
   │ │ (镜头) │      │  (气泡)   speaker_id FK
   │ └────────┘      └───────┬──────────┘
   │                         │ bubble_type
   │                         ├── narration (旁白)
   │                         ├── dialogue  (对白)
   │                         └── thinking  (内心独白)
   │
   ▼ 1:N
┌────────────┐
│   PROMPT   │1:N
│  (提示词)   │─────────▶ ┌──────────────────┐
└────────────┘           │      IMAGE       │
                         │  (图片)           │
                         └────────┬─────────┘
                                  │
                                  ▼ 1:N
                          ┌──────────────────┐
                          │ CONSISTENCY_CHECK│
                          │ (一致性检测)      │
                          └──────────────────┘

┌────────────┐
│   TASK     │── project_id FK ──▶ PROJECT
│  (任务)    │
└────────────┘

┌────────────┐
│   PAGE     │── chapter_id FK ──▶ CHAPTER
│  (页面)    │
└────────────┘

┌──────────────────┐
│  STYLE_TEMPLATE  │── project_id FK ──▶ PROJECT
│  (风格模板)      │
└──────────────────┘

┌────────────┐
│   PLUGIN   │
│  (插件)    │
└────────────┘

┌──────────────────┐
│  SYSTEM_LOG      │
│  (系统日志)       │
└──────────────────┘
```

### 2.2 层级关系总结（主体链）

| 父表 | 子表 | 关系 | 外键字段 |
|------|------|------|---------|
| project | novel | 1:N | novel.project_id |
| project | world_building | 1:N | world_building.project_id |
| project | character | 1:N | character.project_id |
| project | style_template | 1:N | style_template.project_id |
| project | task | 1:N | task.project_id |
| project | character_relation | 1:N | character_relation.project_id |
| novel | chapter | 1:N | chapter.novel_id |
| chapter | scene | 1:N | scene.chapter_id |
| chapter | page | 1:N | page.chapter_id |
| scene | panel | 1:N | panel.scene_id |
| panel | shot | 1:N | shot.panel_id |
| panel | bubble | 1:N | bubble.panel_id |
| panel | prompt | 1:N | prompt.panel_id |
| panel | image | 1:N | image.panel_id |
| prompt | image | 1:N | image.prompt_id |
| image | consistency_check | 1:N | consistency_check.image_id |
| character | character_outfit | 1:N | character_outfit.character_id |
| character | character_reference_image | 1:N | character_reference_image.character_id |
| world_building | scene_asset | 1:N | scene_asset.world_id |
| bubble | character | N:1 | bubble.speaker_id (nullable) |

---

## 3. 核心表定义

### 通用约定

| 项目 | 约定 |
|------|------|
| 主键 | UUID v4，字段名统一为 `id` |
| 时间戳 | `created_at` / `updated_at`，类型 TIMESTAMP WITH TIME ZONE，默认值 `NOW()` |
| 软删除 | 不使用软删除，物理删除 |
| 字符集 | UTF-8 |
| JSONB | PostgreSQL 使用 JSONB 类型；SQLite 兼容模式下使用 TEXT 存储 JSON 字符串 |
| ENUM | 在 PostgreSQL 中使用原生 ENUM 类型；SQLite 中使用 VARCHAR + CHECK 约束 |
| 命名 | 表名使用小写 snake_case，字段名使用小写 snake_case |
| 外键 | 显式命名：`fk_源表_目标表` |

---

### 3.1 project（项目）

项目为顶层聚合根，一个项目包含一部完整的 Webtoon 制作管线。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 主键 |
| name | VARCHAR(255) | NOT NULL | 项目名称 |
| description | TEXT | DEFAULT '' | 项目描述 |
| status | ENUM('draft','planning','generating','editing','completed','archived','deleted') | NOT NULL, DEFAULT 'draft' | 项目状态 |
| cover_image_url | VARCHAR(1024) | NULLABLE | 封面图存储路径/URL |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW(), ON UPDATE NOW() | 更新时间 |

**备注**：
- `status` 流转：`draft` → `planning` → `generating` → `editing` → `completed` → `archived` / `deleted`
- `status = 'draft'`：新建项目，尚未开始制作
- `status = 'planning'`：小说已导入，角色/世界观设定中
- `status = 'generating'`：AI 管线正在执行
- `status = 'editing'`：图片已生成，人工编辑中
- `status = 'completed'`：已导出，项目完成
- `status = 'archived'`：已归档，不再活跃使用
- `status = 'deleted'`：已删除（软删除）

**DDL 示例**：
```sql
CREATE TYPE project_status AS ENUM ('draft', 'planning', 'generating', 'editing', 'completed', 'archived', 'deleted');

CREATE TABLE project (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT DEFAULT '',
    status project_status NOT NULL DEFAULT 'draft',
    cover_image_url VARCHAR(1024),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_project_status ON project(status);
CREATE INDEX idx_project_created_at ON project(created_at DESC);
```

---

### 3.2 novel（小说）

存储用户导入的原始小说文本及清洗后的文本。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK | 主键 |
| project_id | UUID | FK → project.id, NOT NULL, ON DELETE CASCADE | 所属项目 |
| title | VARCHAR(500) | NOT NULL | 小说标题 |
| author | VARCHAR(255) | DEFAULT '' | 作者 |
| raw_text | TEXT | NOT NULL | 原始文本（未处理） |
| cleaned_text | TEXT | NOT NULL DEFAULT '' | 清洗后文本 |
| word_count | INTEGER | NOT NULL DEFAULT 0 | 字数统计 |
| format | ENUM('txt','docx','md') | NOT NULL | 导入文件格式 |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'uploaded' | 小说处理状态 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |

**备注**：
- `status` 枚举值：`uploaded, preprocessing, cleaned, analyzing, analyzed, failed`
- 流转：`uploaded` → `preprocessing` → `cleaned` → `analyzing` → `analyzed`，任一环节失败进入 `failed`
- `raw_text` 保存导入时的原始内容，用于溯源
- `cleaned_text` 经过清洗（去除非正文内容、统一标点、段落编号等）
- `word_count` 为 `cleaned_text` 的实际字数

**DDL 示例**：
```sql
CREATE TYPE novel_format AS ENUM ('txt', 'docx', 'md');

CREATE TABLE novel (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    author VARCHAR(255) DEFAULT '',
    raw_text TEXT NOT NULL,
    cleaned_text TEXT NOT NULL DEFAULT '',
    word_count INTEGER NOT NULL DEFAULT 0,
    format novel_format NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'uploaded',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_novel_project_id ON novel(project_id);
CREATE INDEX idx_novel_status ON novel(status);
```

---

### 3.3 chapter（章节）

小说拆分后的章节。每个章节对应漫画中的"一话"（Episode）。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK | 主键 |
| novel_id | UUID | FK → novel.id, NOT NULL, ON DELETE CASCADE | 所属小说 |
| chapter_number | INTEGER | NOT NULL | 章节编号 |
| title | VARCHAR(500) | DEFAULT '' | 章节标题 |
| content | TEXT | NOT NULL DEFAULT '' | 章节文本内容 |
| start_paragraph_id | INTEGER | NOT NULL DEFAULT 0 | 起始段落ID（对应 cleaned_text 中的段落编号） |
| end_paragraph_id | INTEGER | NOT NULL DEFAULT 0 | 结束段落ID |
| status | ENUM('pending','processing','cleaned','analyzing','analyzed','completed','failed') | NOT NULL, DEFAULT 'pending' | 处理状态 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |

**备注**：
- 段落ID 对应 `cleaned_text` 中按段落拆分后的序号（从1开始）
- `status` 流转：`pending` → `processing` → `cleaned` → `analyzing` → `analyzed` → `completed`，任一环节失败进入 `failed`

**DDL 示例**：
```sql
CREATE TYPE chapter_status AS ENUM ('pending', 'processing', 'cleaned', 'analyzing', 'analyzed', 'completed', 'failed');

CREATE TABLE chapter (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    novel_id UUID NOT NULL REFERENCES novel(id) ON DELETE CASCADE,
    chapter_number INTEGER NOT NULL,
    title VARCHAR(500) DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    start_paragraph_id INTEGER NOT NULL DEFAULT 0,
    end_paragraph_id INTEGER NOT NULL DEFAULT 0,
    status chapter_status NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(novel_id, chapter_number)
);

CREATE INDEX idx_chapter_novel_id ON chapter(novel_id);
CREATE INDEX idx_chapter_status ON chapter(status);
```

---

### 3.4 world_building（世界观）

定义故事的世界观设定，包含时代背景和自定义设定。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK | 主键 |
| project_id | UUID | FK → project.id, NOT NULL, ON DELETE CASCADE | 所属项目 |
| name | VARCHAR(255) | NOT NULL | 世界观名称 |
| era | ENUM('modern','ancient','future','campus','city','xianxia','fantasy','sci_fi','horror','wuxia','other') | NOT NULL | 时代/题材类型 |
| description | TEXT | DEFAULT '' | 世界观描述 |
| settings | JSONB | NOT NULL DEFAULT '{}' | 自定义设定键值对 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |

**备注**：
- `settings` 存储自定义的设定，例如 `{"magic_system": "元素魔法", "political_system": "君主制", "currency": "金币"}`

**DDL 示例**：
```sql
CREATE TYPE world_era AS ENUM ('modern', 'ancient', 'future', 'campus', 'city', 'xianxia', 'fantasy', 'sci_fi', 'horror', 'wuxia', 'other');

CREATE TABLE world_building (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    era world_era NOT NULL,
    description TEXT DEFAULT '',
    settings JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_world_building_project_id ON world_building(project_id);
```

---

### 3.5 scene_asset（场景资产）

具体的场景资产，关联世界观。用于 AI 生图时的场景一致性参考。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK | 主键 |
| world_id | UUID | FK → world_building.id, NOT NULL, ON DELETE CASCADE | 所属世界观 |
| name | VARCHAR(255) | NOT NULL | 场景名称 |
| description | TEXT | DEFAULT '' | 场景描述 |
| season | ENUM('spring','summer','autumn','winter') | NULLABLE | 季节 |
| weather | ENUM('sunny','rainy','cloudy','snowy','stormy','foggy','windy') | NULLABLE | 天气 |
| time_of_day | ENUM('dawn','morning','noon','afternoon','dusk','night') | NULLABLE | 时段 |
| lighting | VARCHAR(500) | DEFAULT '' | 光照描述 |
| atmosphere | VARCHAR(500) | DEFAULT '' | 氛围描述 |
| reference_images | JSONB | NOT NULL DEFAULT '[]' | 参考图URL数组 |
| tags | JSONB | NOT NULL DEFAULT '[]' | 标签数组 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |

**备注**：
- `reference_images` 格式：`["url1.jpg", "url2.jpg"]`
- `tags` 格式：`["校园", "教室", "白天"]`

**DDL 示例**：
```sql
CREATE TYPE season_type AS ENUM ('spring', 'summer', 'autumn', 'winter');
CREATE TYPE weather_type AS ENUM ('sunny', 'rainy', 'cloudy', 'snowy', 'stormy', 'foggy', 'windy');
CREATE TYPE time_of_day_type AS ENUM ('dawn', 'morning', 'noon', 'afternoon', 'dusk', 'night');

CREATE TABLE scene_asset (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    world_id UUID NOT NULL REFERENCES world_building(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT DEFAULT '',
    season season_type,
    weather weather_type,
    time_of_day time_of_day_type,
    lighting VARCHAR(500) DEFAULT '',
    atmosphere VARCHAR(500) DEFAULT '',
    reference_images JSONB NOT NULL DEFAULT '[]',
    tags JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_scene_asset_world_id ON scene_asset(world_id);
```

---

### 3.6 character（人物IP）

人物IP是整个系统中最重要的资产之一。定义了角色的外貌、性格、背景等对AI生图至关重要的属性。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK | 主键 |
| project_id | UUID | FK → project.id, NOT NULL, ON DELETE CASCADE | 所属项目 |
| name | VARCHAR(255) | NOT NULL | 角色名称 |
| age | INTEGER | NULLABLE | 年龄 |
| height | FLOAT | NULLABLE | 身高（cm） |
| weight | FLOAT | NULLABLE | 体重（kg） |
| hair_color | VARCHAR(100) | DEFAULT '' | 发色 |
| hair_style | VARCHAR(200) | DEFAULT '' | 发型 |
| eye_color | VARCHAR(100) | DEFAULT '' | 瞳色 |
| skin_tone | VARCHAR(100) | DEFAULT '' | 肤色 |
| personality | JSONB | NOT NULL DEFAULT '[]' | 性格标签数组 |
| occupation | VARCHAR(255) | DEFAULT '' | 职业 |
| background_story | TEXT | DEFAULT '' | 背景故事 |
| key_features | TEXT | DEFAULT '' | 对AI生图至关重要的特征描述 |
| outfit_description | TEXT | DEFAULT '' | 基础穿搭描述 |
| role_type | ENUM('protagonist','supporter','antagonist','extra') | NOT NULL, DEFAULT 'extra' | 角色类型 |
| status | ENUM('active','archived') | NOT NULL, DEFAULT 'active' | 状态 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |

**备注**：
- `key_features` 存储对AI生图至关重要的特征，例如"左眼下方有泪痣"、"总是戴着一副圆框眼镜"
- `personality` 格式：`["勇敢", "温柔", "固执"]`

**DDL 示例**：
```sql
CREATE TYPE role_type AS ENUM ('protagonist', 'supporter', 'antagonist', 'extra');
CREATE TYPE char_status AS ENUM ('active', 'archived');

CREATE TABLE character (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    age INTEGER,
    height FLOAT,
    weight FLOAT,
    hair_color VARCHAR(100) DEFAULT '',
    hair_style VARCHAR(200) DEFAULT '',
    eye_color VARCHAR(100) DEFAULT '',
    skin_tone VARCHAR(100) DEFAULT '',
    personality JSONB NOT NULL DEFAULT '[]',
    occupation VARCHAR(255) DEFAULT '',
    background_story TEXT DEFAULT '',
    key_features TEXT DEFAULT '',
    outfit_description TEXT DEFAULT '',
    role_type role_type NOT NULL DEFAULT 'extra',
    status char_status NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_character_project_id ON character(project_id);
CREATE INDEX idx_character_role_type ON character(role_type);
```

---

### 3.7 character_relation（人物关系）

定义角色之间的双向关系。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK | 主键 |
| project_id | UUID | FK → project.id, NOT NULL, ON DELETE CASCADE | 所属项目 |
| character_a_id | UUID | FK → character.id, NOT NULL, ON DELETE CASCADE | 角色A |
| character_b_id | UUID | FK → character.id, NOT NULL, ON DELETE CASCADE | 角色B |
| relation_type_a_to_b | VARCHAR(100) | NOT NULL | A对B的关系（如"暗恋"、"仇敌"、"师徒"） |
| relation_type_b_to_a | VARCHAR(100) | NOT NULL | B对A的关系（如"不知情"、"仇恨"、"尊敬"） |
| description | TEXT | DEFAULT '' | 关系描述 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |

**备注**：
- `character_a_id` 和 `character_b_id` 不可相同
- 有向关系设计，`relation_type_a_to_b` 与 `relation_type_b_to_a` 可以不同

**DDL 示例**：
```sql
CREATE TABLE character_relation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    character_a_id UUID NOT NULL REFERENCES character(id) ON DELETE CASCADE,
    character_b_id UUID NOT NULL REFERENCES character(id) ON DELETE CASCADE,
    relation_type_a_to_b VARCHAR(100) NOT NULL,
    relation_type_b_to_a VARCHAR(100) NOT NULL,
    description TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_different_characters CHECK (character_a_id <> character_b_id)
);

CREATE INDEX idx_character_relation_project_id ON character_relation(project_id);
CREATE INDEX idx_character_relation_a ON character_relation(character_a_id);
CREATE INDEX idx_character_relation_b ON character_relation(character_b_id);
```

---

### 3.8 character_outfit（人物服装）

角色的服装配置，不同场景可切换不同服装。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK | 主键 |
| character_id | UUID | FK → character.id, NOT NULL, ON DELETE CASCADE | 所属角色 |
| name | VARCHAR(255) | NOT NULL | 服装名称 |
| outfit_type | VARCHAR(100) | NOT NULL | 服装类型：校服/日常/战斗/礼服/睡衣/运动等 |
| description | TEXT | DEFAULT '' | 服装详细描述 |
| color_scheme | JSONB | NOT NULL DEFAULT '{}' | 配色方案 |
| scene_tags | JSONB | NOT NULL DEFAULT '[]' | 适用场景标签 |
| reference_image_url | VARCHAR(1024) | NULLABLE | 参考图URL |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |

**备注**：
- `color_scheme` 格式：`{"primary": "#FF0000", "secondary": "#0000FF", "accent": "#FFFF00"}`
- `scene_tags` 格式：`["战斗场景", "户外"]`

**DDL 示例**：
```sql
CREATE TABLE character_outfit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id UUID NOT NULL REFERENCES character(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    outfit_type VARCHAR(100) NOT NULL,
    description TEXT DEFAULT '',
    color_scheme JSONB NOT NULL DEFAULT '{}',
    scene_tags JSONB NOT NULL DEFAULT '[]',
    reference_image_url VARCHAR(1024),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_character_outfit_character_id ON character_outfit(character_id);
```

---

### 3.9 character_reference_image（人物参考图）

为角色提供多角度参考图，用于AI生图时保持角色一致性。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK | 主键 |
| character_id | UUID | FK → character.id, NOT NULL, ON DELETE CASCADE | 所属角色 |
| angle | ENUM('front','back','left','right','45deg','expression') | NOT NULL | 拍摄角度 |
| image_url | VARCHAR(1024) | NOT NULL | 图片存储路径/URL |
| tags | JSONB | NOT NULL DEFAULT '[]' | 标签数组 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |

**备注**：
- `angle = 'expression'` 表示表情特写参考图
- `tags` 格式：`["微笑", "正面", "半身"]`

**DDL 示例**：
```sql
CREATE TYPE ref_angle AS ENUM ('front', 'back', 'left', 'right', '45deg', 'expression');

CREATE TABLE character_reference_image (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id UUID NOT NULL REFERENCES character(id) ON DELETE CASCADE,
    angle ref_angle NOT NULL,
    image_url VARCHAR(1024) NOT NULL,
    tags JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_character_ref_img_character_id ON character_reference_image(character_id);
```

---

### 3.10 scene（剧情场景）

从小说文本中分析提取的剧情场景，是 Panel 的上一级聚合单元。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK | 主键 |
| chapter_id | UUID | FK → chapter.id, NOT NULL, ON DELETE CASCADE | 所属章节 |
| scene_number | INTEGER | NOT NULL | 场景编号（章节内自增） |
| description | TEXT | DEFAULT '' | 场景描述 |
| start_paragraph_id | INTEGER | NOT NULL | 起始段落ID |
| end_paragraph_id | INTEGER | NOT NULL | 结束段落ID |
| location | VARCHAR(500) | DEFAULT '' | 地点描述 |
| characters | JSONB | NOT NULL DEFAULT '[]' | 出场角色ID列表 |
| mood | VARCHAR(200) | DEFAULT '' | 场景氛围/情绪基调 |
| weather | VARCHAR(200) | DEFAULT '' | 天气描述 |
| time | VARCHAR(200) | DEFAULT '' | 时间描述 |
| summary | TEXT | DEFAULT '' | 场景摘要 |
| status | ENUM('pending','splitting','split','storyboarding','storyboarded','generating','generated','approved','failed') | NOT NULL, DEFAULT 'pending' | 处理状态 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |

**备注**：
- `characters` 格式：`["uuid1", "uuid2"]`
- `status` 流转：`pending` → `splitting` → `split` → `storyboarding` → `storyboarded` → `generating` → `generated` → `approved`，任一环节失败进入 `failed`

**DDL 示例**：
```sql
CREATE TYPE scene_status AS ENUM ('pending', 'splitting', 'split', 'storyboarding', 'storyboarded', 'generating', 'generated', 'approved', 'failed');

CREATE TABLE scene (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES chapter(id) ON DELETE CASCADE,
    scene_number INTEGER NOT NULL,
    description TEXT DEFAULT '',
    start_paragraph_id INTEGER NOT NULL,
    end_paragraph_id INTEGER NOT NULL,
    location VARCHAR(500) DEFAULT '',
    characters JSONB NOT NULL DEFAULT '[]',
    mood VARCHAR(200) DEFAULT '',
    weather VARCHAR(200) DEFAULT '',
    time VARCHAR(200) DEFAULT '',
    summary TEXT DEFAULT '',
    status scene_status NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(chapter_id, scene_number)
);

CREATE INDEX idx_scene_chapter_id ON scene(chapter_id);
CREATE INDEX idx_scene_status ON scene(status);
```

---

### 3.11 panel（画格）

**系统中最核心的表**。一个 Panel 对应漫画中的一个画格（画面单位），是整个生产管线的核心数据节点。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK | 主键 |
| scene_id | UUID | FK → scene.id, NOT NULL, ON DELETE CASCADE | 所属场景 |
| panel_number | INTEGER | NOT NULL | 画格编号（场景内自增） |
| source_text | TEXT | DEFAULT '' | 关联的原文片段 |
| start_paragraph_id | INTEGER | NOT NULL | 起始段落ID |
| end_paragraph_id | INTEGER | NOT NULL | 结束段落ID |
| characters | JSONB | NOT NULL DEFAULT '[]' | 本画格出场角色ID列表 |
| action | VARCHAR(1000) | DEFAULT '' | 动作描述 |
| emotion | VARCHAR(500) | DEFAULT '' | 情绪/表情描述 |
| camera_type | VARCHAR(100) | DEFAULT '' | 镜头类型：远景/中景/近景/特写/大远景/过肩等 |
| camera_movement | VARCHAR(100) | DEFAULT '' | 运镜方式：固定/推/拉/摇/移/跟/升降等 |
| composition | VARCHAR(500) | DEFAULT '' | 构图描述 |
| layout_type | VARCHAR(50) | DEFAULT '' | 版式建议：单格/双格/三格/四格/整页 |
| beat | VARCHAR(100) | DEFAULT '' | 节奏：快/中/慢 |
| status | ENUM('created','split','storyboarded','camera_set','layout_set','prompt_ready','generating','generated','reviewed','approved','exported','failed') | NOT NULL, DEFAULT 'created' | 处理状态 |
| selected_image_id | UUID | NULLABLE, FK → image.id, ON DELETE SET NULL | 选中的最终图片ID |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |

**备注**：
- `status` 流转：`created`（已创建） → `split`（已切分） → `storyboarded`（已分镜） → `camera_set`（镜头已规划） → `layout_set`（版式已分配） → `prompt_ready`（Prompt已就绪） → `generating`（生图中） → `generated`（候选图已生成） → `reviewed`（已审核） → `approved`（已通过） → `exported`（已导出）；任一环节失败则进入 `failed`
- `selected_image_id` 是冗余字段，用于快速获取 Panel 的最终图片，避免多表 JOIN
- `layout_type` 仅作建议，最终版式由 page 表的 `panel_layout` 决定

**DDL 示例**：
```sql
CREATE TYPE panel_status AS ENUM ('created', 'split', 'storyboarded', 'camera_set', 'layout_set', 'prompt_ready', 'generating', 'generated', 'reviewed', 'approved', 'exported', 'failed');

CREATE TABLE panel (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scene_id UUID NOT NULL REFERENCES scene(id) ON DELETE CASCADE,
    panel_number INTEGER NOT NULL,
    source_text TEXT DEFAULT '',
    start_paragraph_id INTEGER NOT NULL,
    end_paragraph_id INTEGER NOT NULL,
    characters JSONB NOT NULL DEFAULT '[]',
    action VARCHAR(1000) DEFAULT '',
    emotion VARCHAR(500) DEFAULT '',
    camera_type VARCHAR(100) DEFAULT '',
    camera_movement VARCHAR(100) DEFAULT '',
    composition VARCHAR(500) DEFAULT '',
    layout_type VARCHAR(50) DEFAULT '',
    beat VARCHAR(100) DEFAULT '',
    status panel_status NOT NULL DEFAULT 'created',
    selected_image_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(scene_id, panel_number)
);

CREATE INDEX idx_panel_scene_id ON panel(scene_id);
CREATE INDEX idx_panel_status ON panel(status);
CREATE INDEX idx_panel_selected_image_id ON panel(selected_image_id);
```

---

### 3.12 shot（镜头）

一个 Panel 中可以包含多个镜头规划（用于生图时的细节指导）。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK | 主键 |
| panel_id | UUID | FK → panel.id, NOT NULL, ON DELETE CASCADE | 所属画格 |
| shot_number | INTEGER | NOT NULL | 镜头编号（Panel内自增） |
| shot_type | VARCHAR(100) | NOT NULL | 景别/镜头类型 |
| movement | VARCHAR(100) | DEFAULT '' | 运镜方式 |
| description | TEXT | DEFAULT '' | 镜头描述 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |

**备注**：
- `shot_type` 可选值示例：extreme_long_shot / long_shot / full_shot / medium_shot / close_up / extreme_close_up / over_shoulder / two_shot / POV
- `movement` 可选值示例：static / pan / tilt / dolly / truck / pedestal / zoom / handheld

**DDL 示例**：
```sql
CREATE TABLE shot (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    panel_id UUID NOT NULL REFERENCES panel(id) ON DELETE CASCADE,
    shot_number INTEGER NOT NULL,
    shot_type VARCHAR(100) NOT NULL,
    movement VARCHAR(100) DEFAULT '',
    description TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(panel_id, shot_number)
);

CREATE INDEX idx_shot_panel_id ON shot(panel_id);
```

---

### 3.13 bubble（气泡）

画格中的对话气泡/旁白/内心独白。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK | 主键 |
| panel_id | UUID | FK → panel.id, NOT NULL, ON DELETE CASCADE | 所属画格 |
| bubble_type | ENUM('narration','dialogue','thinking') | NOT NULL | 气泡类型 |
| text | TEXT | NOT NULL | 文字内容 |
| speaker_id | UUID | NULLABLE, FK → character.id, ON DELETE SET NULL | 说话人（旁白时为NULL） |
| position_x | FLOAT | NOT NULL DEFAULT 0.5 | X坐标（画面百分比 0.0~1.0） |
| position_y | FLOAT | NOT NULL DEFAULT 0.5 | Y坐标（画面百分比 0.0~1.0） |
| width | FLOAT | NOT NULL DEFAULT 0.3 | 宽度（画面百分比 0.0~1.0） |
| height | FLOAT | NOT NULL DEFAULT 0.15 | 高度（画面百分比 0.0~1.0） |
| style | JSONB | NOT NULL DEFAULT '{}' | 气泡样式参数 |
| order | INTEGER | NOT NULL DEFAULT 0 | 显示顺序（从小到大） |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'pending' | 气泡处理状态 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |

**备注**：
- `status` 枚举值：`pending, identified, confirmed, edited, failed`
- 流转：`pending` → `identified` → `confirmed` → `edited`，识别失败进入 `failed`
- `bubble_type = 'narration'`：旁白，`speaker_id` 为 NULL
- `bubble_type = 'dialogue'`：对白，`speaker_id` 指向说话角色
- `bubble_type = 'thinking'`：内心独白，`speaker_id` 指向内心活动角色
- `style` 格式：`{"font_size": 16, "font_color": "#000000", "background_color": "#FFFFFF", "border_style": "oval", "border_color": "#000000", "opacity": 0.9, "tail_direction": "left"}`

**DDL 示例**：
```sql
CREATE TYPE bubble_type AS ENUM ('narration', 'dialogue', 'thinking');

CREATE TABLE bubble (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    panel_id UUID NOT NULL REFERENCES panel(id) ON DELETE CASCADE,
    bubble_type bubble_type NOT NULL,
    text TEXT NOT NULL,
    speaker_id UUID REFERENCES character(id) ON DELETE SET NULL,
    position_x FLOAT NOT NULL DEFAULT 0.5,
    position_y FLOAT NOT NULL DEFAULT 0.5,
    width FLOAT NOT NULL DEFAULT 0.3,
    height FLOAT NOT NULL DEFAULT 0.15,
    style JSONB NOT NULL DEFAULT '{}',
    "order" INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_bubble_panel_id ON bubble(panel_id);
CREATE INDEX idx_bubble_status ON bubble(status);
CREATE INDEX idx_bubble_speaker_id ON bubble(speaker_id);
```

---

### 3.14 prompt（提示词）

为 Panel 生成的 AI 提示词，采用10层结构化设计，支持版本管理。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK | 主键 |
| panel_id | UUID | FK → panel.id, NOT NULL, ON DELETE CASCADE | 所属画格 |
| version | INTEGER | NOT NULL | 版本号（Panel内自增） |
| layers | JSONB | NOT NULL | 10层Prompt结构（见下方说明） |
| full_prompt | TEXT | NOT NULL | 组装后的完整Prompt文本 |
| model_params | JSONB | NOT NULL DEFAULT '{}' | 生图模型参数 |
| score | FLOAT | NULLABLE | 人工/自动评分（0.0~5.0） |
| tags | JSONB | NOT NULL DEFAULT '[]' | 标签数组 |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'draft' | Prompt状态 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |

**备注**：
- `status` 枚举值：`draft, completed, used, superseded`
- 流转：`draft` → `completed` → `used` → `superseded`

**layers JSONB 结构**：

| 层名 | 类型 | 必填 | 说明 |
|------|------|------|------|
| character | TEXT | 是 | 角色描述（外貌、服装、姿态） |
| environment | TEXT | 是 | 环境/背景描述 |
| action | TEXT | 是 | 动作/姿势描述 |
| emotion | TEXT | 是 | 表情/情绪描述 |
| camera | TEXT | 是 | 镜头类型/角度 |
| lighting | TEXT | 是 | 光照描述 |
| composition | TEXT | 是 | 构图描述 |
| webtoon_style | TEXT | 是 | Webtoon画风描述 |
| bubble | TEXT | 否 | 气泡留白/文本布局 |
| negative | TEXT | 否 | 负面提示词 |

**DDL 示例**：
```sql
CREATE TABLE prompt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    panel_id UUID NOT NULL REFERENCES panel(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    layers JSONB NOT NULL,
    full_prompt TEXT NOT NULL,
    model_params JSONB NOT NULL DEFAULT '{}',
    score FLOAT,
    tags JSONB NOT NULL DEFAULT '[]',
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(panel_id, version)
);

CREATE INDEX idx_prompt_panel_id ON prompt(panel_id);
CREATE INDEX idx_prompt_status ON prompt(status);
```

---

### 3.15 image（图片）

AI 生成的图片记录，支持多版本、多候选。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK | 主键 |
| panel_id | UUID | FK → panel.id, NOT NULL, ON DELETE CASCADE | 所属画格 |
| prompt_id | UUID | FK → prompt.id, NOT NULL, ON DELETE RESTRICT | 使用的Prompt版本 |
| version | INTEGER | NOT NULL | 版本号（Panel内自增） |
| image_url | VARCHAR(1024) | NOT NULL | 原图存储路径/URL |
| thumbnail_url | VARCHAR(1024) | NOT NULL | 缩略图路径/URL |
| width | INTEGER | NOT NULL | 图片宽度（像素） |
| height | INTEGER | NOT NULL | 图片高度（像素） |
| file_size | INTEGER | NOT NULL DEFAULT 0 | 文件大小（字节） |
| format | VARCHAR(20) | NOT NULL DEFAULT 'png' | 文件格式 |
| model_name | VARCHAR(255) | DEFAULT '' | 生图模型名称 |
| model_params | JSONB | NOT NULL DEFAULT '{}' | 生图参数快照 |
| is_selected | BOOLEAN | NOT NULL DEFAULT FALSE | 是否被选为该Panel的最终图 |
| quality_score | FLOAT | NULLABLE | AI质量评分（0.0~1.0） |
| consistency_report | JSONB | NULLABLE | 一致性检测结果快照 |
| status | ENUM('pending','generating','generated','selected','rejected','superseded','pending_review') | NOT NULL, DEFAULT 'pending' | 生成状态 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |

**备注**：
- `status` 流转：`pending` → `generating` → `generated`；`generated` 后可被 `selected` / `rejected` / `superseded` / `pending_review`
- `is_selected = TRUE` 的图片会被 panel.selected_image_id 引用（冗余设计，避免 JOIN）
- `consistency_report` 格式：`{"character_score": 0.95, "scene_score": 0.88, "style_score": 0.92, "overall": 0.92}`
- `model_params` 为生成时的参数快照，与当前模型配置解耦

**DDL 示例**：
```sql
CREATE TYPE image_status AS ENUM ('pending', 'generating', 'generated', 'selected', 'rejected', 'superseded', 'pending_review');

CREATE TABLE image (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    panel_id UUID NOT NULL REFERENCES panel(id) ON DELETE CASCADE,
    prompt_id UUID NOT NULL REFERENCES prompt(id) ON DELETE RESTRICT,
    version INTEGER NOT NULL,
    image_url VARCHAR(1024) NOT NULL,
    thumbnail_url VARCHAR(1024) NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    file_size INTEGER NOT NULL DEFAULT 0,
    format VARCHAR(20) NOT NULL DEFAULT 'png',
    model_name VARCHAR(255) DEFAULT '',
    model_params JSONB NOT NULL DEFAULT '{}',
    is_selected BOOLEAN NOT NULL DEFAULT FALSE,
    quality_score FLOAT,
    consistency_report JSONB,
    status image_status NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_image_panel_id ON image(panel_id);
CREATE INDEX idx_image_prompt_id ON image(prompt_id);
CREATE INDEX idx_image_is_selected ON image(is_selected) WHERE is_selected = TRUE;
CREATE INDEX idx_image_status ON image(status);
```

---

### 3.16 consistency_check（一致性检测记录）

每次 AI 一致性检测的结果记录。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK | 主键 |
| image_id | UUID | FK → image.id, NOT NULL, ON DELETE CASCADE | 被检测图片 |
| check_type | ENUM('character','scene','prop','style','text') | NOT NULL | 检测类型 |
| result | ENUM('pass','fail','warning') | NOT NULL | 检测结论 |
| details | JSONB | NOT NULL DEFAULT '{}' | 检测详情 |
| score | FLOAT | NOT NULL | 检测得分（0.0~1.0） |
| checked_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 检测时间 |

**备注**：
- `details` 格式示例：
  - character类型：`{"character_id": "uuid", "feature": "hair_color", "expected": "black", "actual": "dark_brown", "similarity": 0.87}`
  - text类型（漏字检测）：`{"expected_text": "你好世界", "missing_chars": ["界"], "positions": [[100, 200, 150, 250]]}`

**DDL 示例**：
```sql
CREATE TYPE check_type AS ENUM ('character', 'scene', 'prop', 'style', 'text');
CREATE TYPE check_result AS ENUM ('pass', 'fail', 'warning');

CREATE TABLE consistency_check (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    image_id UUID NOT NULL REFERENCES image(id) ON DELETE CASCADE,
    check_type check_type NOT NULL,
    result check_result NOT NULL,
    details JSONB NOT NULL DEFAULT '{}',
    score FLOAT NOT NULL,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_consistency_check_image_id ON consistency_check(image_id);
CREATE INDEX idx_consistency_check_result ON consistency_check(result);
```

---

### 3.17 task（任务）

异步任务记录，用于追踪 AI 生成、批量处理等异步操作的执行状态。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK | 主键 |
| project_id | UUID | FK → project.id, NOT NULL, ON DELETE CASCADE | 所属项目 |
| type | VARCHAR(100) | NOT NULL | 任务类型 |
| status | ENUM('queued','running','completed','failed','cancelled','retrying') | NOT NULL, DEFAULT 'queued' | 任务状态 |
| priority | ENUM('low','normal','high','urgent') | NOT NULL, DEFAULT 'normal' | 优先级 |
| progress | INTEGER | NOT NULL DEFAULT 0 | 进度百分比（0~100） |
| input_data | JSONB | NOT NULL DEFAULT '{}' | 任务输入数据 |
| output_data | JSONB | NULLABLE | 任务输出数据 |
| error_message | TEXT | NULLABLE | 错误信息 |
| started_at | TIMESTAMPTZ | NULLABLE | 开始执行时间 |
| completed_at | TIMESTAMPTZ | NULLABLE | 完成时间 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |

**备注**：
- `type` 可选值示例：`novel_analysis` / `scene_split` / `prompt_generation` / `image_generation` / `consistency_check` / `batch_export`
- `status` 流转：`queued` → `running` → `completed`；失败时 `running` → `failed` → `retrying` → `running`；用户可取消 → `cancelled`
- `input_data` 格式取决于任务类型，例如 `{"panel_ids": ["uuid1", "uuid2"], "model": "sdxl"}`

**DDL 示例**：
```sql
CREATE TYPE task_status AS ENUM ('queued', 'running', 'completed', 'failed', 'cancelled', 'retrying');
CREATE TYPE task_priority AS ENUM ('low', 'normal', 'high', 'urgent');

CREATE TABLE task (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    type VARCHAR(100) NOT NULL,
    status task_status NOT NULL DEFAULT 'queued',
    priority task_priority NOT NULL DEFAULT 'normal',
    progress INTEGER NOT NULL DEFAULT 0,
    input_data JSONB NOT NULL DEFAULT '{}',
    output_data JSONB,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_task_project_id ON task(project_id);
CREATE INDEX idx_task_status ON task(status);
CREATE INDEX idx_task_type ON task(type);
CREATE INDEX idx_task_priority ON task(priority);
```

---

### 3.18 page（漫画页面）

管理漫画页面的版式布局，一个 Page 包含多个 Panel 的排版信息。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK | 主键 |
| chapter_id | UUID | FK → chapter.id, NOT NULL, ON DELETE CASCADE | 所属章节 |
| page_number | INTEGER | NOT NULL | 页码（章节内自增） |
| layout_template | VARCHAR(100) | DEFAULT '' | 使用的版式模板名称 |
| panel_layout | JSONB | NOT NULL DEFAULT '[]' | Panel在页面中的布局信息（位置、大小） |
| status | ENUM('empty','layouted','populated','edited','completed') | NOT NULL, DEFAULT 'empty' | 页面状态 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |

**备注**：
- `panel_layout` 格式：
```json
[
  {
    "panel_id": "uuid",
    "x": 0.05,
    "y": 0.02,
    "width": 0.9,
    "height": 0.45,
    "rotation": 0,
    "z_index": 1,
    "border_radius": 8,
    "border_width": 2
  },
  {
    "panel_id": "uuid",
    "x": 0.05,
    "y": 0.5,
    "width": 0.9,
    "height": 0.48,
    "rotation": 0,
    "z_index": 2,
    "border_radius": 8,
    "border_width": 2
  }
]
```
- `status` 流转：`empty` → `layouted` → `populated` → `edited` → `completed`

**DDL 示例**：
```sql
CREATE TYPE page_status AS ENUM ('empty', 'layouted', 'populated', 'edited', 'completed');

CREATE TABLE page (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES chapter(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    layout_template VARCHAR(100) DEFAULT '',
    panel_layout JSONB NOT NULL DEFAULT '[]',
    status page_status NOT NULL DEFAULT 'empty',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(chapter_id, page_number)
);

CREATE INDEX idx_page_chapter_id ON page(chapter_id);
CREATE INDEX idx_page_status ON page(status);
```

---

### 3.19 style_template（风格模板）

定义 Webtoon 的画风、配色、光影等艺术风格参数。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK | 主键 |
| project_id | UUID | FK → project.id, NOT NULL, ON DELETE CASCADE | 所属项目 |
| name | VARCHAR(255) | NOT NULL | 模板名称 |
| aspect_ratio | VARCHAR(20) | NOT NULL DEFAULT '1:1.34' | 画面比例 |
| width | INTEGER | NOT NULL DEFAULT 1080 | 生成宽度（像素） |
| art_style | TEXT | NOT NULL DEFAULT '' | 画风描述 |
| coloring_style | TEXT | DEFAULT '' | 上色风格描述 |
| lineart_style | TEXT | DEFAULT '' | 线稿风格描述 |
| lighting_style | TEXT | DEFAULT '' | 光影风格描述 |
| negative_prompt | TEXT | DEFAULT '' | 默认负面提示词 |
| is_default | BOOLEAN | NOT NULL DEFAULT FALSE | 是否为项目默认模板 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |

**DDL 示例**：
```sql
CREATE TABLE style_template (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    aspect_ratio VARCHAR(20) NOT NULL DEFAULT '1:1.34',
    width INTEGER NOT NULL DEFAULT 1080,
    art_style TEXT NOT NULL DEFAULT '',
    coloring_style TEXT DEFAULT '',
    lineart_style TEXT DEFAULT '',
    lighting_style TEXT DEFAULT '',
    negative_prompt TEXT DEFAULT '',
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_style_template_project_id ON style_template(project_id);
CREATE UNIQUE INDEX idx_style_template_default ON style_template(project_id) WHERE is_default = TRUE;
```

---

### 3.20 plugin（插件）

系统插件注册表，用于扩展系统功能。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK | 主键 |
| name | VARCHAR(255) | NOT NULL | 插件名称 |
| version | VARCHAR(50) | NOT NULL | 版本号 |
| description | TEXT | DEFAULT '' | 插件描述 |
| plugin_type | VARCHAR(100) | NOT NULL | 插件类型 |
| config_schema | JSONB | NOT NULL DEFAULT '{}' | 配置JSON Schema |
| enabled | BOOLEAN | NOT NULL DEFAULT TRUE | 是否启用 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |

**备注**：
- `plugin_type` 可选值：`image_generation` / `llm_provider` / `export_format` / `consistency_checker` / `style_transfer`
- `config_schema` 为 JSON Schema 格式，用于前端动态渲染配置表单

**DDL 示例**：
```sql
CREATE TABLE plugin (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,
    description TEXT DEFAULT '',
    plugin_type VARCHAR(100) NOT NULL,
    config_schema JSONB NOT NULL DEFAULT '{}',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(name, version)
);

CREATE INDEX idx_plugin_type ON plugin(plugin_type);
CREATE INDEX idx_plugin_enabled ON plugin(enabled);
```

---

### 3.21 system_log（系统日志）

全局操作审计日志。

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK | 主键 |
| level | ENUM('debug','info','warning','error') | NOT NULL, DEFAULT 'info' | 日志级别 |
| module | VARCHAR(100) | NOT NULL | 模块名称 |
| action | VARCHAR(200) | NOT NULL | 操作描述 |
| user_id | VARCHAR(255) | NULLABLE | 用户标识 |
| target_type | VARCHAR(100) | NULLABLE | 操作目标类型（如 panel/image/task） |
| target_id | UUID | NULLABLE | 操作目标ID |
| details | JSONB | NOT NULL DEFAULT '{}' | 详细数据 |
| ip_address | VARCHAR(50) | DEFAULT '' | 客户端IP |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 日志时间 |

**备注**：
- 此表为**追加写入**类型，不做 UPDATE 操作
- `created_at` 是聚集索引，按时间排序查询

**DDL 示例**：
```sql
CREATE TYPE log_level AS ENUM ('debug', 'info', 'warning', 'error');

CREATE TABLE system_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    level log_level NOT NULL DEFAULT 'info',
    module VARCHAR(100) NOT NULL,
    action VARCHAR(200) NOT NULL,
    user_id VARCHAR(255),
    target_type VARCHAR(100),
    target_id UUID,
    details JSONB NOT NULL DEFAULT '{}',
    ip_address VARCHAR(50) DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_system_log_level ON system_log(level);
CREATE INDEX idx_system_log_module ON system_log(module);
CREATE INDEX idx_system_log_created_at ON system_log(created_at DESC);
CREATE INDEX idx_system_log_target ON system_log(target_type, target_id);
```

---

## 4. 索引策略

### 4.1 主键索引

所有表均以 UUID 作为主键，PostgreSQL 自动创建主键索引（PRIMARY KEY）。

### 4.2 外键索引

| 表名 | 外键字段 | 索引类型 | 说明 |
|------|---------|---------|------|
| novel | project_id | BTREE | 按项目查询小说 |
| chapter | novel_id | BTREE | 按小说查询章节 |
| scene | chapter_id | BTREE | 按章节查询场景 |
| panel | scene_id | BTREE | 按场景查询画格 |
| shot | panel_id | BTREE | 按画格查询镜头 |
| bubble | panel_id | BTREE | 按画格查询气泡 |
| prompt | panel_id | BTREE | 按画格查询Prompt版本 |
| image | panel_id | BTREE | 按画格查询图片候选 |
| image | prompt_id | BTREE | 按Prompt查询图片 |
| consistency_check | image_id | BTREE | 按图片查询检测记录 |
| page | chapter_id | BTREE | 按章节查询页面 |
| character | project_id | BTREE | 按项目查询角色 |
| character_outfit | character_id | BTREE | 按角色查询服装 |
| character_reference_image | character_id | BTREE | 按角色查询参考图 |
| scene_asset | world_id | BTREE | 按世界观查询场景资产 |
| world_building | project_id | BTREE | 按项目查询世界观 |
| style_template | project_id | BTREE | 按项目查询模板 |
| task | project_id | BTREE | 按项目查询任务 |
| character_relation | project_id / character_a_id / character_b_id | BTREE | 关系查询 |

### 4.3 业务查询索引

| 表名 | 索引字段 | 索引类型 | 说明 |
|------|---------|---------|------|
| project | status | BTREE | 按状态筛选项目列表 |
| project | created_at DESC | BTREE | 按时间排序项目 |
| chapter | (novel_id, chapter_number) | UNIQUE BTREE | 章节号唯一性 |
| scene | (chapter_id, scene_number) | UNIQUE BTREE | 场景号唯一性 |
| panel | (scene_id, panel_number) | UNIQUE BTREE | 画格号唯一性 |
| panel | status | BTREE | 按状态筛选画格（生图/待处理） |
| panel | selected_image_id | BTREE | 按选中图片反查画格 |
| image | is_selected | PARTIAL BTREE | 仅索引已选中的图片（WHERE is_selected = TRUE） |
| image | status | BTREE | 按生成状态筛选 |
| bubble | speaker_id | BTREE | 按说话人查询气泡 |
| task | status | BTREE | 按状态查询任务队列 |
| task | type | BTREE | 按类型查询任务 |
| task | priority | BTREE | 按优先级排序 |
| consistency_check | result | BTREE | 按检测结果筛选 |
| page | (chapter_id, page_number) | UNIQUE BTREE | 页码唯一性 |
| style_template | (project_id) WHERE is_default | UNIQUE PARTIAL BTREE | 每个项目只有一个默认模板 |
| system_log | level | BTREE | 按日志级别筛选 |
| system_log | module | BTREE | 按模块筛选 |
| system_log | created_at DESC | BTREE | 按时间倒序查询 |
| system_log | (target_type, target_id) | BTREE | 按操作目标查询 |
| prompt | (panel_id, version) | UNIQUE BTREE | 版本号唯一性 |
| bubble | panel_id, "order" | BTREE | 按显示顺序查询 |

### 4.4 复合索引

| 表名 | 索引字段 | 说明 |
|------|---------|------|
| panel | (scene_id, status) | 按场景筛选特定状态的画格 |
| image | (panel_id, is_selected) | 快速查找某Panel的选中图片 |
| task | (status, priority, created_at) | 任务队列的排序和筛选 |
| system_log | (created_at DESC, level) | 按时间和级别查询日志 |

### 4.5 索引使用原则

1. **避免过度索引**：OLTP 场景下单个表索引不超过 8 个
2. **覆盖索引优先**：高频查询尽量使用索引覆盖
3. **部分索引**：对稀疏数据（如 `is_selected = TRUE`）使用部分索引
4. **复合索引顺序**：等值条件在前，范围条件在后

---

## 5. 数据流向

### 5.1 核心写入流程（生产管线）

```
                                    ┌─────────────┐
                                    │   Project   │
                                    └──────┬──────┘
                                           │
                                           ▼
                                    ┌─────────────┐
                                    │    Novel    │
                                    └──────┬──────┘
                                           │
                                           ▼
                                    ┌─────────────┐
                                    │   Chapter   │
                                    └──────┬──────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      ▼                      │
                    │               ┌─────────────┐              │
                    │               │    Scene    │              │
                    │               └──────┬──────┘              │
                    │                      │                     │
                    │                      ▼                     │
                    │               ┌─────────────┐              │
                    │               │    Panel    │              │
                    │               └──┬───┬───┬──┘              │
                    │                  │   │   │                 │
                    │   ┌──────────────┘   │   └──────────────┐  │
                    │   │                  ▼                  │  │
                    │   │           ┌────────────┐            │  │
                    │   │           │  Bubble    │            │  │
                    │   │           └────────────┘            │  │
                    │   ▼                                     │  │
                    │ ┌────────┐                              │  │
                    │ │  Shot  │                              │  │
                    │ └────────┘                              │  │
                    │                                         │  │
                    ▼                                         ▼  │
              ┌────────────┐                           ┌──────┴──┴──┐
              │   Prompt   │                           │    Page    │
              └──────┬─────┘                           └────────────┘
                     │
                     ▼
              ┌────────────┐
              │   Image    │
              └──────┬─────┘
                     │
                     ▼
              ┌──────────────────┐
              │ ConsistencyCheck │
              └──────────────────┘
```

**步骤说明**：

| 步骤 | 操作 | 产生数据 |
|------|------|---------|
| 1 | 导入小说 | novel.raw_text → novel.cleaned_text |
| 2 | 章节拆分 | chapter (多个) |
| 3 | 剧情分析 | scene (多个)，关联 character |
| 4 | 语义切句 | panel (多个)，关联 scene |
| 5 | 分镜规划 | shot (多个) |
| 6 | 气泡规划 | bubble (多个)，关联 character |
| 7 | 版式规划 | page (多个)，panel_layout 指向 panel |
| 8 | Prompt生成 | prompt (多个版本) |
| 9 | AI生图 | image (多个候选) |
| 10 | 一致性检测 | consistency_check (多条记录) |
| 11 | 人工选择 | panel.selected_image_id = image.id |

### 5.2 读取热点

| 热区 | 频率 | 说明 |
|------|------|------|
| Panel 查询 | ⭐⭐⭐⭐⭐ | 漫画编辑器、生图中心、分镜中心均频繁读取 |
| Panel 状态 | ⭐⭐⭐⭐⭐ | 任务队列状态轮询 |
| Image 候选 | ⭐⭐⭐⭐ | 生图中心的画廊视图 |
| Bubble 文本 | ⭐⭐⭐⭐ | 漫画文本中心、漫画编辑器 |
| Chapter → Scene → Panel | ⭐⭐⭐⭐ | 层级导航 |
| Character 基本信息 | ⭐⭐⭐ | 角色选择器、气泡编辑 |
| Prompt 版本 | ⭐⭐⭐ | Prompt 编辑、版本管理 |

### 5.3 归档策略

| 阶段 | 条件 | 操作 |
|------|------|------|
| 活跃期 | project.status = 'active' | 正常读写，保留所有版本 |
| 已完成 | project中的所有panel均为 approved | project.status → 'archived' |
| 归档后 | project.status = 'archived' | 保留数据，标记为只读 |
| 清理 | 归档超过180天 | 可选项：清理过期图片文件，保留DB记录 |

**归档影响**：
- 归档项目的数据仍可查询，但不可修改
- 图片文件可根据配置保留或清理
- 系统日志不受归档影响

---

## 6. 迁移策略

### 6.1 迁移工具

使用 **Alembic** 管理数据库迁移。

### 6.2 项目结构

```
project_root/
├── alembic/
│   ├── env.py              # 迁移环境配置
│   ├── script.py.mako      # 迁移脚本模板
│   └── versions/           # 迁移版本文件
│       ├── 0001_initial_schema.py
│       ├── 0002_add_character_outfit.py
│       └── ...
├── alembic.ini              # Alembic 配置文件
└── app/
    └── models/              # SQLAlchemy 模型定义
        ├── __init__.py
        ├── base.py          # 声明基类（DeclarativeBase）
        ├── project.py
        ├── novel.py
        ├── chapter.py
        ├── scene.py
        ├── panel.py
        ├── shot.py
        ├── bubble.py
        ├── prompt.py
        ├── image.py
        ├── consistency_check.py
        ├── character.py
        ├── character_relation.py
        ├── character_outfit.py
        ├── character_reference_image.py
        ├── world_building.py
        ├── scene_asset.py
        ├── task.py
        ├── page.py
        ├── style_template.py
        ├── plugin.py
        └── system_log.py
```

### 6.3 迁移原则

| 原则 | 说明 |
|------|------|
| **向下兼容** | 新增字段必须可 NULL 或有默认值，不允许破坏现有查询 |
| **增量变更** | 每次变更生成一个独立的迁移脚本，禁止修改已发布的迁移 |
| **先代码后DB** | 先更新 ORM 模型，再生成迁移脚本 |
| **Review 机制** | 生产环境的迁移脚本需经过 Code Review |
| **回滚预案** | 每个迁移必须提供 `downgrade()` 实现 |

### 6.4 迁移流程

```bash
# 1. 修改 SQLAlchemy 模型

# 2. 自动生成迁移脚本
alembic revision --autogenerate -m "描述变更内容"

# 3. 审查生成的迁移脚本（检查自动检测是否正确）

# 4. 执行迁移
alembic upgrade head

# 5. 回滚（如需）
alembic downgrade -1
```

### 6.5 迁移命名规范

```
格式：{序号}_{简短描述}.py
示例：
  0001_initial_schema.py          - 初始表结构
  0002_add_character_outfit.py    - 新增服装表
  0003_add_consistency_check.py   - 新增一致性检测表
  0004_add_selected_image_to_panel.py  - Panel新增selected_image_id字段
```

### 6.6 环境迁移策略

| 环境 | 策略 |
|------|------|
| 开发环境 | 每次启动自动检查并执行迁移 |
| 测试环境 | CI/CD 流程中执行迁移 |
| 生产环境 | 手动执行迁移，先备份数据库 |

### 6.7 SQLAlchemy 基类示例

```python
from sqlalchemy import Column, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime
import uuid

class Base(DeclarativeBase):
    """所有模型的基础类"""
    pass

class TimestampMixin:
    """时间戳混入类"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

class UUIDMixin:
    """UUID主键混入类"""
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
```

---

## 7. 附录：命名规范

### 7.1 表名命名

- 复数小写 snake_case（SQLAlchemy 默认表名生成规则）
- 示例：`projects`, `character_relations`, `consistency_checks`

### 7.2 字段名命名

- 小写 snake_case
- 主键统一为 `id`
- 外键统一为 `{目标表}_id`
- 时间戳统一为 `created_at` / `updated_at`
- 布尔字段使用 `is_` 前缀：`is_selected`, `is_default`, `is_archived`

### 7.3 ENUM 命名

- 类型名使用小写 snake_case，以 `_type` 或直接描述性名词结尾
- 示例：`panel_status`, `role_type`, `bubble_type`

### 7.4 索引命名

```
idx_{表名}_{字段名}
uniq_{表名}_{字段名}    -- 唯一索引
idx_{表名}_{字段1}_{字段2}  -- 复合索引
```

### 7.5 外键约束命名

```
fk_{源表}_{目标表}
```

示例：`fk_panel_scene`, `fk_image_prompt`

### 7.6 JSONB 字段规范

- JSONB 字段必须提供默认值 `'{}'` 或 `'[]'`
- 对象类型使用 `'{}'` 默认值
- 数组类型使用 `'[]'` 默认值
- 文档中需描述 JSONB 字段的内部结构

---

## 附录A：表关联关系速查表

| 序号 | 表名 | 父表 | 关联字段 | 级联删除 |
|------|------|------|---------|---------|
| 1 | novel | project | project_id | CASCADE |
| 2 | chapter | novel | novel_id | CASCADE |
| 3 | scene | chapter | chapter_id | CASCADE |
| 4 | panel | scene | scene_id | CASCADE |
| 5 | shot | panel | panel_id | CASCADE |
| 6 | bubble | panel | panel_id | CASCADE |
| 7 | prompt | panel | panel_id | CASCADE |
| 8 | image | panel | panel_id | CASCADE |
| 9 | image | prompt | prompt_id | RESTRICT |
| 10 | consistency_check | image | image_id | CASCADE |
| 11 | page | chapter | chapter_id | CASCADE |
| 12 | character | project | project_id | CASCADE |
| 13 | character_outfit | character | character_id | CASCADE |
| 14 | character_reference_image | character | character_id | CASCADE |
| 15 | character_relation | project | project_id | CASCADE |
| 16 | character_relation | character | character_a_id | CASCADE |
| 17 | character_relation | character | character_b_id | CASCADE |
| 18 | world_building | project | project_id | CASCADE |
| 19 | scene_asset | world_building | world_id | CASCADE |
| 20 | style_template | project | project_id | CASCADE |
| 21 | task | project | project_id | CASCADE |
| 22 | bubble | character | speaker_id | SET NULL |
| 23 | panel | image | selected_image_id | SET NULL |

## 附录B：状态机流转图

### panel.status 状态流转

```
                    ┌─────────┐
                    │ created │
                    └────┬────┘
                         │ 语义切句完成
                         ▼
                    ┌────────────┐
                    │   split    │
                    └─────┬──────┘
                          │ 分镜规划完成
                          ▼
                   ┌──────────────┐
                   │ storyboarded │
                   └──────┬───────┘
                          │ 镜头规划完成
                          ▼
                    ┌────────────┐
                    │ camera_set │
                    └─────┬──────┘
                          │ 版式分配完成
                          ▼
                    ┌────────────┐
                    │ layout_set │
                    └─────┬──────┘
                          │ Prompt组装完成
                          ▼
                  ┌──────────────┐
                  │ prompt_ready │
                  └──────┬───────┘
                         │ 提交生图
                         ▼
                   ┌───────────┐
                   │ generating│
                   └─────┬─────┘
                         │ 生图完成
                         ▼
                    ┌──────────┐
                    │ generated│
                    └────┬─────┘
                         │ 人工审核开始
                         ▼
                    ┌──────────┐
                    │ reviewed │
                    └──┬───┬───┘
               ┌───────┘   └──────────┐
               ▼                      ▼
          ┌──────────┐          ┌───────────┐
          │ approved │          │ generating│ (打回重生成)
          └─────┬────┘          └───────────┘
                │ 页面导出完成
                ▼
           ┌──────────┐
           │ exported │
           └──────────┘

  失败路径：任一环节可进入 failed
```

### task.status 状态流转

```
                    ┌─────────┐
                    │ queued  │
                    └────┬────┘
                         │ 开始执行
                         ▼
                   ┌───────────┐
                   │  running  │
                   └──┬─────┬──┘
              ┌───────┘     └──────────┐
              ▼                        ▼
        ┌───────────┐           ┌──────────┐
        │ completed │           │  failed  │
        └───────────┘           └────┬─────┘
              ▲                      │ 自动重试
              │ 取消           ┌──────▼──────┐
        ┌───────────┐          │  retrying   │
        │ cancelled │          └──────┬──────┘
        └───────────┘                 │ 重试开始
                                      ▼
                                 ┌───────────┐
                                 │  running  │
                                 └───────────┘
```

---

*文档结束*
