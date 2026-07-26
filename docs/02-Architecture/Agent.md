# AI Webtoon Factory — AI Agent 设计文档

> 版本：v1.0  
> 最后更新：2026-06-27  
> 状态：正式

---

## 1. Agent 架构总览

### 1.1 Agent 管线图

```
小说文本（原始 TXT / DOCX / MD）
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│                      文本预处理管线                                │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐  │
│  │ ① TextCleaner  │───▶│ ② StoryAnalyzer│───▶│③ Semantic     │  │
│  │   文本清洗      │    │   剧情分析      │    │   Splitter    │  │
│  │               │    │               │    │   语义切句     │  │
│  └────────────────┘    └────────────────┘    └───────┬────────┘  │
│                                                       │           │
│                                                       ▼           │
│                        ┌────────────────────────────────┐         │
│                        │           Scene → Panel[]       │         │
│                        └────────────────────────────────┘         │
│                                                                    │
│                      视觉分镜管线                                   │
│  ┌────────────────┐    ┌────────────────┐                        │
│  │ ④ Storyboard  │───▶│ ⑤ Camera       │                        │
│  │   Planner     │    │   Planner      │                        │
│  │   分镜规划      │    │   镜头规划      │                        │
│  └────────────────┘    └────────┬───────┘                        │
│                                 │                                │
│  ┌────────────────┐            │                                │
│  │ ⑥ Layout      │◀───────────┘                                │
│  │   Planner     │                                              │
│  │   版式规划      │                                              │
│  └────────┬───────┘                                              │
│           │                                                      │
│  ┌────────▼───────┐                                              │
│  │ ⑦ Bubble      │                                              │
│  │   Planner     │                                              │
│  │   气泡规划      │                                              │
│  └────────┬───────┘                                              │
└───────────┼──────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Prompt + 生图管线                            │
│  ┌────────────────┐    ┌────────────────┐                        │
│  │ ⑧ Prompt      │───▶│  Image Gen     │                        │
│  │   Generator   │    │  (外部SD API)   │                        │
│  │   Prompt生成   │    │   AI生图       │                        │
│  └────────────────┘    └────────┬───────┘                        │
│                                 │                                │
│                  ┌──────────────┴──────────────┐                 │
│                  ▼                              ▼                │
│  ┌────────────────────────┐  ┌────────────────────────┐         │
│  │ ⑨ ConsistencyChecker  │  │ ⑩ QualityScorer       │         │
│  │   一致性检查            │  │   质量评分              │         │
│  └────────────────────────┘  └────────────────────────┘         │
│                  │                              │                │
│                  └──────────────┬──────────────┘                │
│                                 ▼                               │
│                        人工审核 → 漫画编辑器 → 导出              │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 Agent 设计原则

| 原则 | 说明 |
|------|------|
| **单一职责原则** | 每个 Agent 只做一件事。TextCleaner 只管清洗，不分析剧情；StoryAnalyzer 只管提取 Scene，不管拆 Panel |
| **结构化 IO** | 所有 Agent 的输入和输出均为结构化 JSON，不使用自然语言文本传递中间结果。确保数据可解析、可校验、可追溯 |
| **独立可替换** | 任意 Agent 可单独升级、替换或禁用。例如可替换 StoryAnalyzer 的 LLM 调用策略，不影响其他 Agent |
| **可追溯** | 每个 Agent 的执行记录存入任务日志（Task 表），包含输入快照、输出摘要、耗时、Token 消耗、重试次数 |

### 1.3 Agent 基类定义

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

@dataclass
class AgentContext:
    """Agent 执行上下文"""
    task_id: str                    # 关联的 Task ID
    chapter_id: str                 # 当前处理的章节 ID
    user_id: str                    # 触发执行的用户 ID
    params: dict                    # 执行参数（如 LLM 配置覆盖）
    trace_id: str                   # 链路追踪 ID
    retry_count: int = 0            # 当前重试次数
    max_retries: int = 3            # 最大重试次数
    timeout: int = 60               # 超时秒数

@dataclass
class AgentResult:
    """Agent 执行结果"""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    metrics: Optional[dict] = None   # 耗时、Token 消耗等
    fallback_used: bool = False      # 是否使用了降级策略

class BaseAgent(ABC):
    """所有 Agent 的抽象基类"""

    agent_id: str                   # Agent 唯一标识
    agent_version: str = "1.0.0"    # Agent 版本号

    @abstractmethod
    async def process(self, context: AgentContext) -> AgentResult:
        """核心处理方法，包含 LLM 调用、结果解析、后处理"""
        pass

    @abstractmethod
    async def validate_input(self, data: dict) -> bool:
        """校验输入数据是否符合 JSON Schema"""
        pass

    @abstractmethod
    async def validate_output(self, data: dict) -> bool:
        """校验输出数据是否符合 JSON Schema"""
        pass

    async def fallback(self, context: AgentContext, error: Exception) -> AgentResult:
        """降级处理：规则引擎 / 简化 LLM / 标记失败"""
        return AgentResult(
            success=False,
            error=f"All retries exhausted: {str(error)}",
            fallback_used=True
        )

    async def handle_failure(self, context: AgentContext, error: Exception) -> AgentResult:
        """统一失败处理：重试 → 降级 → 标记失败"""
        while context.retry_count < context.max_retries:
            context.retry_count += 1
            try:
                return await self.process(context)
            except Exception as e:
                if context.retry_count >= context.max_retries:
                    return await self.fallback(context, e)
        return await self.fallback(context, error)
```

---

## 2. Agent 详细定义

### Agent ① TextCleanerAgent (文本清洗)

| 项目 | 内容 |
|------|------|
| **ID** | `text_cleaner` |
| **版本** | `1.0.0` |
| **职责** | 清洗导入的原始小说文本，统一格式，输出结构清晰的纯文本段落列表 |
| **LLM 策略** | 每章调用 1 次。短文本（<500 字）使用规则引擎替代 LLM |
| **超时** | 60 秒 |

#### System Prompt

```
你是一个专业的文本清洗助手，专门处理中文小说文本。你的任务是：
1. 移除多余空行和空白字符，保留段落间距
2. 统一全角/半角符号为全角（中文语境标准）
3. 修正常见编码错误（如乱码字符、不正确的引号配对）
4. 识别并保留章节标题格式
5. 统一对话引号格式（使用「」或“”）
6. 检测并标记特殊格式（如粗体、斜体、注释等）

输出必须为结构化 JSON，不要包含任何额外说明。
```

#### User Prompt

```
请清洗以下小说文本，输出结构化 JSON。

原始文本：
{{raw_text}}

请按以下 JSON Schema 格式输出：
{
  "chapter_title": "第X章 章名（自动识别）",
  "clean_text": "清洗后的连续纯文本",
  "paragraphs": ["段落1", "段落2", ...],
  "meta": {
    "word_count": 整数,
    "paragraph_count": 整数,
    "has_dialogue": true/false,
    "format_issues_found": ["问题1", ...]
  }
}
```

#### 输入 JSON Schema

```json
{
  "type": "object",
  "required": ["raw_text", "chapter_id", "source_format"],
  "properties": {
    "raw_text": {
      "type": "string",
      "description": "原始文本内容"
    },
    "chapter_id": {
      "type": "string",
      "format": "uuid",
      "description": "章节 ID"
    },
    "source_format": {
      "type": "string",
      "enum": ["txt", "docx", "markdown"],
      "description": "原始格式"
    },
    "options": {
      "type": "object",
      "properties": {
        "preserve_line_breaks": {
          "type": "boolean",
          "default": true
        },
        "unify_quotes": {
          "type": "boolean",
          "default": true
        }
      }
    }
  }
}
```

#### 输出 JSON Schema

```json
{
  "type": "object",
  "required": ["chapter_title", "clean_text", "paragraphs", "meta"],
  "properties": {
    "chapter_title": {
      "type": "string",
      "description": "章节标题"
    },
    "clean_text": {
      "type": "string",
      "description": "清洗后的完整文本"
    },
    "paragraphs": {
      "type": "array",
      "items": { "type": "string" },
      "description": "段落列表"
    },
    "meta": {
      "type": "object",
      "required": ["word_count", "paragraph_count", "has_dialogue"],
      "properties": {
        "word_count": { "type": "integer" },
        "paragraph_count": { "type": "integer" },
        "has_dialogue": { "type": "boolean" },
        "format_issues_found": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    }
  }
}
```

#### 失败处理

```
步骤1: 正常 LLM 调用（1 次）
  ├─ 成功 → 解析输出并校验 Schema
  ├─ JSON 解析失败 → 重试（最多 3 次）
  ├─ Schema 校验失败 → 重试（最多 3 次）
  └─ LLM 调用异常（超时/网络） → 重试（最多 3 次）

步骤2: 所有重试耗尽
  └─ 降级为规则引擎：
      1. 正则替换多余空行 (\n{3,} → \n\n)
      2. 全角/半角统一（半角标点 → 全角）
      3. 按段落拆分（\n\n 分割）
      4. 统计元数据
      └─ 标记 fallback_used = true

步骤3: 规则引擎也失败
  └─ 标记任务失败，error 记录原因
```

---

### Agent ② StoryAnalyzerAgent (剧情分析)

| 项目 | 内容 |
|------|------|
| **ID** | `story_analyzer` |
| **版本** | `1.0.0` |
| **职责** | 从章节文本中提取 Scene（场景）结构，识别场景边界、人物、地点、时间、情绪，提取情节节点 |
| **LLM 策略** | 每章调用 1 次，单次 Prompt 包含全章。充分利用 LLM 的上下文理解能力 |
| **超时** | 120 秒（长章节需更多时间） |
| **上下文窗口** | 考虑 LLM 的上下文限制，长章节（>8000 tokens）分段处理，每段独立分析后合并 |

#### System Prompt

```
你是一个专业的漫画剧情分析助手。你的任务是对小说章节进行深度语义理解，
提取剧情结构要素，识别场景（Scene）边界，并输出结构化的 Scene 列表。

核心概念：
- Scene（场景）：发生在同一时间、同一地点的一段连续剧情
- 场景切换标志：时间变化、地点变化、人物进出场、情绪转变
- 情节节点：故事开端、冲突引入、转折点、高潮、结局

分析要求：
1. 按时间/地点切换识别场景边界
2. 提取每个 Scene 的核心要素（人物、地点、时间、情绪）
3. 识别情节节点在 Scene 级别的分布
4. 每个 Scene 关联对应的原文段落范围（精确到段落编号）
5. 输出严格的 JSON 格式，不要包含额外说明文字
```

#### User Prompt

```
请分析以下章节文本，提取场景（Scene）结构。

章节标题：{{chapter_title}}

文本（已分段落）：
{{paragraphs_with_numbers}}

可选参考信息：
- 已知世界观设定：{{world_building_info}}
- 已知人物列表：{{character_list}}

请输出以下 JSON 结构：
{
  "chapter_id": "{{chapter_id}}",
  "analysis_version": "1.0",
  "scenes": [
    {
      "scene_number": 1,
      "summary": "场景摘要",
      "start_paragraph": 起始段落编号,
      "end_paragraph": 结束段落编号,
      "location": "地点描述",
      "time": "时间描述",
      "characters": ["人物1", "人物2"],
      "emotion": "场景情绪标签",
      "plot_points": ["情节节点标签"],
      "scene_type": "dialogue/action/transition/emotional"
    }
  ],
  "plot_structure": {
    "beginning": "开头摘要（哪些 Scene）",
    "development": "发展部分摘要",
    "climax": "高潮部分摘要",
    "ending": "结局部分摘要"
  },
  "meta": {
    "total_scenes": 整数,
    "total_characters": ["所有出现的人物"],
    "locations": ["所有出现的地点"]
  }
}
```

#### 输入 JSON Schema

```json
{
  "type": "object",
  "required": ["chapter_id", "paragraphs", "clean_text"],
  "properties": {
    "chapter_id": { "type": "string", "format": "uuid" },
    "clean_text": { "type": "string" },
    "paragraphs": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["index", "text"],
        "properties": {
          "index": { "type": "integer" },
          "text": { "type": "string" }
        }
      }
    },
    "world_building_info": { "type": "string" },
    "character_list": {
      "type": "array",
      "items": { "type": "string" }
    }
  }
}
```

#### 输出 JSON Schema

```json
{
  "type": "object",
  "required": ["chapter_id", "scenes", "plot_structure", "meta"],
  "properties": {
    "chapter_id": { "type": "string" },
    "analysis_version": { "type": "string" },
    "scenes": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["scene_number", "summary", "start_paragraph", "end_paragraph", "location", "time", "characters", "emotion", "scene_type"],
        "properties": {
          "scene_number": { "type": "integer" },
          "summary": { "type": "string", "maxLength": 200 },
          "start_paragraph": { "type": "integer" },
          "end_paragraph": { "type": "integer" },
          "location": { "type": "string" },
          "time": { "type": "string" },
          "characters": { "type": "array", "items": { "type": "string" } },
          "emotion": { "type": "string" },
          "plot_points": { "type": "array", "items": { "type": "string" } },
          "scene_type": { "type": "string", "enum": ["dialogue", "action", "transition", "emotional"] }
        }
      }
    },
    "plot_structure": {
      "type": "object",
      "properties": {
        "beginning": { "type": "string" },
        "development": { "type": "string" },
        "climax": { "type": "string" },
        "ending": { "type": "string" }
      }
    },
    "meta": {
      "type": "object",
      "properties": {
        "total_scenes": { "type": "integer" },
        "total_characters": { "type": "array", "items": { "type": "string" } },
        "locations": { "type": "array", "items": { "type": "string" } }
      }
    }
  }
}
```

#### 长章节分段处理策略

```
Chapter 文本总长度 > 8000 tokens：
  │
  ├─ 按段落均匀分割为 N 段（每段约 4000 tokens，保留段落完整性）
  │
  ├─ 每段独立调用 LLM，使用相同 System Prompt
  │   └─ User Prompt 中增加上下文提示：
  │       "这是章节的第 {k}/{n} 段，前一段结尾是：{prev_tail}"
  │
  ├─ 合并策略：
  │   1. 按 scene_number 顺序拼接
  │   2. 校验相邻 Scene 的连续性（时间/地点跳跃是否合理）
  │   3. 如发现同一 Scene 被分割到两段，自动合并
  │
  └─ 重新编号 scene_number 使序列连续
```

#### 失败处理

```
3 次重试 → 降低分段阈值（每段 2000 tokens 重新尝试） → 标记失败
```

---

### Agent ③ SemanticSplitterAgent (语义切句)

| 项目 | 内容 |
|------|------|
| **ID** | `semantic_splitter` |
| **版本** | `1.0.0` |
| **职责** | 按语义粒度将 Scene 文本拆分为 Panel（画格）级别的文本片段。核心理念是"一个动作 = 一个 Panel" |
| **LLM 策略** | 每个 Scene 调用 1 次。长 Scene（>2000 字）分段处理 |
| **超时** | 60 秒 |

#### System Prompt

```
你是一个漫画语义拆解专家。你的任务是将一段场景文本按语义粒度拆分为
独立的 Panel（画格）片段。每个 Panel 对应漫画中的一格画面。

核心拆分规则：

规则1【对话独立成格】：每句对话独立为一个 Panel。
  - 正确："张三说："你好"" → Panel[对话]
  - "李四回答："好久不见"" → Panel[对话]

规则2【动作拆解】：连续动作拆分为多个 Panel。
  - "他推开门走进房间坐在沙发上" → 
    Panel1[他推开门] → Panel2[他走进房间] → Panel3[他坐在沙发上]

规则3【描述合并】：同一场景的环境描述与首个动作合并为一个 Panel。
  - "夕阳西下，红色的霞光照满了天空。他站在窗前。" →
    Panel[夕阳西下，红色的霞光照满了天空。他站在窗前。]

规则4【情绪转折点】：情绪变化处必须切换 Panel。
  - 同一段文本中，从"平静"到"愤怒"的情绪转变 → 拆分为两个 Panel

规则5【信息量控制】：每个 Panel 文本建议 10-50 字，单幅画面的合理信息量。
  - 过于简短的 Panel（<5 字）尝试与相邻 Panel 合并
  - 过于冗长的 Panel（>100 字）进一步拆分

输出的每个 Panel 需标注：文本内容、关联段落编号、涉及人物、情绪标签、Panel 类型。
```

#### User Prompt

```
请将以下 Scene 文本按语义拆分为 Panel 列表。

Scene 信息：
- Scene 编号：{{scene_number}}
- 场景摘要：{{scene_summary}}
- 地点：{{location}}
- 时间：{{time}}
- 情绪基调：{{emotion}}
- 出现人物：{{characters}}

Scene 文本（段落已编号）：
{{paragraphs_with_numbers}}

请输出以下 JSON 结构：
{
  "scene_id": "{{scene_id}}",
  "panels": [
    {
      "panel_number": 1,
      "text": "Panel 对应的文本片段",
      "paragraph_ref": 关联段落编号,
      "characters": ["人物"],
      "emotion": "情绪标签",
      "panel_type": "dialogue/action/description/transition/thinking"
    }
  ],
  "meta": {
    "total_panels": 整数,
    "split_strategy_used": ["使用的拆分规则列表"]
  }
}
```

#### 输入 JSON Schema

```json
{
  "type": "object",
  "required": ["scene_id", "scene_text", "paragraphs", "characters"],
  "properties": {
    "scene_id": { "type": "string" },
    "scene_text": { "type": "string" },
    "scene_summary": { "type": "string" },
    "location": { "type": "string" },
    "time": { "type": "string" },
    "emotion": { "type": "string" },
    "paragraphs": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "index": { "type": "integer" },
          "text": { "type": "string" }
        }
      }
    },
    "characters": {
      "type": "array",
      "items": { "type": "string" }
    }
  }
}
```

#### 输出 JSON Schema

```json
{
  "type": "object",
  "required": ["scene_id", "panels"],
  "properties": {
    "scene_id": { "type": "string" },
    "panels": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["panel_number", "text", "paragraph_ref", "panel_type"],
        "properties": {
          "panel_number": { "type": "integer" },
          "text": { "type": "string", "minLength": 1 },
          "paragraph_ref": { "type": "integer" },
          "characters": { "type": "array", "items": { "type": "string" } },
          "emotion": { "type": "string" },
          "panel_type": {
            "type": "string",
            "enum": ["dialogue", "action", "description", "transition", "thinking"]
          }
        }
      },
      "minItems": 1
    },
    "meta": {
      "type": "object",
      "properties": {
        "total_panels": { "type": "integer" },
        "split_strategy_used": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    }
  }
}
```

#### 失败处理

```
3 次重试 → 降级为标点拆分规则（按句号/问号/感叹号/对话引号拆分） → 标记失败
```

---

### Agent ④ StoryboardPlannerAgent (分镜规划)

| 项目 | 内容 |
|------|------|
| **ID** | `storyboard_planner` |
| **版本** | `1.0.0` |
| **职责** | 为每个 Panel 生成视觉分镜方案，确定核心视觉元素、构图思路和画面描述 |
| **LLM 策略** | 每 5-10 个 Panel 批量处理一次，保持上下文连续性 |
| **超时** | 120 秒 |

#### System Prompt

```
你是一个资深漫画分镜师。你的任务是根据 Panel 的文本内容，生成详细的
视觉分镜方案。你需要考虑：

1. 画面构成：主体位置、背景、关键元素
2. 视觉焦点：读者第一眼应该看到什么
3. 色彩氛围：场景的整体色调和色彩倾向
4. 连续 Panel 的视觉连续性：相邻 Panel 之间的画面过渡
5. 叙事重点：哪些细节需要强调，哪些可以省略

注意：
- 输出的是视觉描述（供后续镜头规划使用），不是最终生图 Prompt
- 高潮/关键剧情 Panel 提供详细描述，过渡 Panel 从简
- 关注"什么元素在画面中"，而不是"用什么镜头拍"
```

#### User Prompt

```
请为以下 Panel 序列生成视觉分镜方案。

场景上下文：
- 场景摘要：{{scene_summary}}
- 场景情绪：{{scene_emotion}}
- 场景地点：{{scene_location}}

Panel 序列（共 {{panel_count}} 个）：
{{panels_json}}

请为每个 Panel 输出以下 JSON 结构：
{
  "panels": [
    {
      "panel_id": "uuid",
      "panel_number": 1,
      "shot_description": "完整的画面描述，包含主体、背景、关键元素、氛围",
      "composition": "构图方式描述（如中心构图、三分法等）",
      "focus": "视觉焦点说明",
      "background": "背景描述",
      "key_elements": ["关键元素列表"],
      "color_palette": ["主色调1", "主色调2"],
      "mood": "画面情绪",
      "continuity_notes": "与前后 Panel 的连续性说明"
    }
  ]
}
```

#### 连续 Panel 处理策略

```
批量处理时，LLM 同时看到 5-10 个连续 Panel 的文本，确保：

1. 主体位置过渡自然（不在相邻 Panel 中左右跳跃）
2. 背景一致性（同一 Scene 内的背景描述不矛盾）
3. 动作流畅性（连续动作 Panel 描述同一动作的连贯阶段）
4. 情绪递进（情绪变化的 Panel 之间有合理的视觉过渡）
```

#### 输入/输出 JSON Schema

输入为 Panel 列表（含文本、人物、动作、情绪），输出为每个 Panel 的视觉描述对象列表。Schema 结构与上述 User Prompt 中的 JSON 对应。

#### 失败处理

```
3 次重试 → 逐 Panel 单独分析（降低批量大小到 3） → 标记失败
```

---

### Agent ⑤ CameraPlannerAgent (镜头规划)

| 项目 | 内容 |
|------|------|
| **ID** | `camera_planner` |
| **版本** | `1.0.0` |
| **职责** | 为每个 Panel 确定镜头类型、景别、运镜方式、构图规则和视角 |
| **LLM 策略** | 每 5-10 个 Panel 批量处理一次 |
| **超时** | 120 秒 |

#### 镜头规则

```
对话场景：
  1. 正反打（shot-reverse-shot）：对话双方交替出现
  2. 以中景（Medium Shot）为主，适当插入近景强调表情
  3. 平视角度为主，保持对话平等感
  4. 镜头切换频率：每 2-3 句对话切换一次

动作场景：
  1. 多角度切换，避免单调
  2. 远景（Long Shot）展示动作全貌 + 特写（Close-up）强调细节
  3. 仰拍增强角色气势，俯拍展示全局
  4. 使用动态镜头（推/拉/跟）增强动感

情绪场景：
  1. 特写 + 俯拍/仰拍强化情绪
  2. 缓慢的镜头运动（推近/拉远）营造氛围
  3. 景别逐渐变化（远景→中景→特写）增强代入感
  4. 使用过肩镜头（OTS）增强亲密感或对抗感

通用规则：
  1. 避免连续 3 个同类型镜头
  2. 景别变化要符合节奏：舒缓段落变化慢，紧张段落变化快
  3. 建立镜头（Establishing Shot）用于新场景开头
```

#### System Prompt

```
你是一个专业的漫画镜头规划师。你的任务是根据 Panel 的文本内容和
分镜描述（Agent ④ 的输出），为每个 Panel 确定具体的镜头方案。

你需要输出：
- 镜头类型（远景/中景/近景/特写/POV/过肩等）
- 镜头角度（平视/俯拍/仰拍/侧面等）
- 镜头运动（固定/推/拉/摇/移/跟）
- 景别（extreme_long/long/medium/close/extreme_close）
- 构图规则（三分法/中心/对角线/引导线/框架等）
- 与前一 Panel 的过渡方式（cut/fade/dissolve/match_cut）

批量处理时，请确保相邻 Panel 的镜头变化自然合理。
```

#### User Prompt

```
请为以下 Panel 序列规划镜头方案。

场景情绪基调：{{scene_emotion}}

Panel 序列：
{{panels_with_storyboard}}

请输出：
{
  "panels": [
    {
      "panel_id": "uuid",
      "panel_number": 1,
      "camera_type": "medium_shot",
      "camera_angle": "eye_level",
      "camera_movement": "fixed",
      "shot_size": "medium",
      "composition_rule": "rule_of_thirds",
      "transition_from_prev": "cut",
      "rationale": "镜头选择理由"
    }
  ]
}
```

#### 输入/输出 JSON Schema

输入包含 Agent ④ 输出的分镜描述，输出为镜头规划对象列表。

#### 失败处理

```
3 次重试 → 使用默认镜头规则（对话/动作/情绪场景的预设方案） → 标记失败
```

---

### Agent ⑥ LayoutPlannerAgent (版式规划)

| 项目 | 内容 |
|------|------|
| **ID** | `layout_planner` |
| **版本** | `1.0.0` |
| **职责** | 将 Panel 序列编排为 Webtoon 页面布局，确定每页的 Panel 数量、排列方式和相对比例 |
| **LLM 策略** | 每话（30-50 Panel）集中处理 1 次 |
| **超时** | 180 秒 |

#### 版式规则

```
1. 高潮场景：使用大格（1/2 页）、跨格或整页布局，增强视觉冲击力
2. 对话场景：使用 3-4 格均分布局，阅读节奏均匀
3. 过渡场景：使用 5-6 格紧凑布局，加快阅读节奏
4. 每页建议 3-6 个 Panel，避免过多或过少
5. 页面首格：通常是引导格，承担承上启下功能
6. 页面末格：通常是悬念格或停顿格，留给读者回味空间
7. 重要情节 Panel 分配更大面积，次要 Panel 压缩
8. 同一 Scene 尽量安排在同一页或连续页

页面模板参考：
  - 1_panel  : 整页单格（高潮/建立镜头）
  - 2_split  : 上下二等分
  - 3_split  : 上 大格 + 下 两小格
  - 4_split  : 四等分网格
  - 5_split  : 2+3 或 3+2 组合
  - 6_split  : 3x2 或 2x3 网格
  - custom   : 自定义比例
```

#### System Prompt

```
你是一个专业的 Webtoon 版式设计师。你的任务是将 Panel 序列
编排为 Webtoon 竖屏页面布局。

Webtoon 竖屏阅读特点：
  1. 从上到下滚动阅读，不需要翻页
  2. 页面宽度固定（1080px），高度可变
  3. 阅读节奏由 Panel 大小和排列决定

输出要求：
  - 每页的布局模板选择（参考预设模板库）
  - 每个 Panel 在页面中的位置和尺寸（相对比例）
  - 页面意图说明（对话推进/动作高潮/情绪沉淀等）
  - 整话的节奏分析
```

#### User Prompt

```
请为以下 Panel 序列进行版式规划。

Panel 总数：{{panel_count}}
情节节奏标记：{{pacing_markers}}

Panel 序列（含镜头信息和情绪标签）：
{{panels_with_camera}}

请输出：
{
  "pages": [
    {
      "page_number": 1,
      "layout_template": "3_split",
      "panels": [
        {
          "panel_id": "uuid",
          "position": { "x": 0, "y": 0, "w": 1, "h": 0.4 }
        },
        {
          "panel_id": "uuid",
          "position": { "x": 0, "y": 0.4, "w": 1, "h": 0.3 }
        },
        {
          "panel_id": "uuid",
          "position": { "x": 0, "y": 0.7, "w": 1, "h": 0.3 }
        }
      ],
      "page_intent": "对话推进"
    }
  ],
  "pacing_analysis": {
    "total_pages": 整数,
    "climax_page": 高潮所在页码,
    "panel_density": "high/moderate/low",
    "recommendations": ["建议1"]
  }
}
```

#### 输入/输出 JSON Schema

输入为含镜头信息的完整 Panel 列表，输出为页面布局列表。

#### 失败处理

```
3 次重试 → 使用默认版式（4_split 均分布局） → 标记失败
```

---

### Agent ⑦ BubblePlannerAgent (气泡规划)

| 项目 | 内容 |
|------|------|
| **ID** | `bubble_planner` |
| **版本** | `1.0.0` |
| **职责** | 识别文本类型（对话/旁白/内心独白），生成气泡列表并建议放置位置 |
| **LLM 策略** | 每 10-20 个 Panel 批量处理一次 |
| **超时** | 120 秒 |

#### 文本类型识别规则

```
类型1 - Dialogue（对白）：
  - 引号（" "、「」）包裹的内容
  - 包含"说""道""问""答""喊""叫"等动词
  - 例句："你终于来了。"神秘人说。

类型2 - Thinking（内心独白）：
  - 包含"心想""想道""觉得""感到""暗自"等词
  - 无引号的第一人称心理活动
  - 例句：他心里想，这下麻烦了。

类型3 - Narration（旁白）：
  - 其他描述性文本
  - 环境描述、动作描述、过渡说明
  - 例句：雨越下越大，街上的行人纷纷躲避。

气泡放置规则：
  - 旁白框：默认左上角或右上角
  - 对白框：默认居右（从左到右阅读习惯），尾部指向说话者
  - 内心独白：默认左中位置，使用云状气泡样式
  - 阅读顺序：从上到下、从左到右
```

#### System Prompt

```
你是一个漫画气泡规划专家。你的任务是从 Panel 文本中识别不同类型的
文本内容，生成对应的气泡，并建议放置位置。

你需识别三种文本类型：
1. Dialogue（对白）- 引号内的对话内容
2. Thinking（内心独白）- 心理活动
3. Narration（旁白）- 描述性文本

请严格按照识别规则分类，并建议气泡在画面中的位置。
输出的气泡列表按阅读顺序排列。
```

#### User Prompt

```
请为以下 Panel 规划气泡。

Panel 信息：
- Panel 编号：{{panel_number}}
- Panel 文本：{{panel_text}}
- 分镜描述：{{shot_description}}
- 人物信息：{{characters_in_panel}}

请输出：
{
  "panel_id": "{{panel_id}}",
  "bubbles": [
    {
      "bubble_id": "自动生成 UUID",
      "type": "dialogue/narration/thinking",
      "text": "气泡文本内容",
      "speaker": "说话者（旁白为 null）",
      "position_suggestion": "left/right/top/center",
      "style_ref": "气泡样式引用",
      "order": 阅读顺序编号,
      "source_text_id": "关联原文 ID"
    }
  ]
}
```

#### 输入/输出 JSON Schema

输入为 Panel 文本和分镜信息，输出为气泡列表。

#### 失败处理

```
3 次重试 → 降级为规则引擎识别（基于引号和关键词匹配） → 标记失败
```

---

### Agent ⑧ PromptGeneratorAgent (Prompt 生成)

| 项目 | 内容 |
|------|------|
| **ID** | `prompt_generator` |
| **版本** | `1.0.0` |
| **职责** | 聚合所有上游数据，组装为 10 层结构化 Prompt，供生图模型使用 |
| **LLM 策略** | 不需要 LLM。此 Agent 为纯代码实现（模板引擎 + 数据聚合器） |
| **超时** | 10 秒（纯本地计算） |

#### 组装规则

```
步骤1: 从模板库加载 10 层 Prompt 模板
  └─ SELECT * FROM prompt_templates WHERE template_id = :template_id

步骤2: 逐层映射数据源
  Layer 1 (Character)    ← 人物 IP 中心
  Layer 2 (Environment)  ← 世界观资产库
  Layer 3 (Action)       ← 分镜数据（Agent ④）
  Layer 4 (Emotion)      ← 剧情分析数据（Agent ②）
  Layer 5 (Camera)       ← 镜头规划数据（Agent ⑤）
  Layer 6 (Lighting)     ← 场景设定 + 镜头规划
  Layer 7 (Composition)  ← 分镜规划数据（Agent ④）
  Layer 8 (WebtoonStyle) ← 风格模板库
  Layer 9 (Bubble)       ← 气泡规划数据（Agent ⑦）
  Layer 10 (Negative)    ← 系统预设 + 用户自定义

步骤3: 模板变量替换
  逐层执行：template.replace('{{variable}}', actual_value)
  变量缺失时：使用该变量的默认值（在 prompt_variables 表中配置）
  空层处理：如果某层所有变量都缺失，跳过该层不输出

步骤4: 合并 Prompt
  10 层按顺序拼接，层间用 ", " 分隔
  总长度控制在 CLIP token 限制内（<150 tokens 建议值）
  负向 Prompt 单独输出

步骤5: 附加生成参数
  width/height/cfg_scale/steps/seed 从模型配置中读取
```

#### 输入数据源映射

| 层 | 数据来源表 | 关键字段映射 |
|----|-----------|-------------|
| L1 Character | `character` | name, appearance, hair_color, hair_style, eye_color, skin_tone, clothing, key_features |
| L2 Environment | `scene_asset` | location, weather, time_of_day, season, atmosphere |
| L3 Action | `panel.storyboard_data` | action, characters_action, action_intensity |
| L4 Emotion | `scene.emotion` | mood, expression, intensity |
| L5 Camera | `panel.camera_data` | camera_type, camera_angle, camera_movement, shot_size, composition_rule |
| L6 Lighting | `scene_asset` + `panel` | lighting_style, lighting_direction, lighting_color, emphasis |
| L7 Composition | `panel.storyboard_data` | composition, focus, background, key_elements |
| L8 WebtoonStyle | `style_template` | art_style, coloring_style, lineart_style, detail_level, artist_ref |
| L9 Bubble | `bubble` | type, position, text_content, style_ref |
| L10 Negative | `style_template` + `user_settings` | negative_prompt, custom_negative |

#### 输出 JSON Schema

```json
{
  "type": "object",
  "required": ["panel_id", "prompt_version", "layers", "merged_prompt", "negative_prompt", "params"],
  "properties": {
    "panel_id": { "type": "string" },
    "prompt_version": { "type": "string" },
    "layers": {
      "type": "object",
      "properties": {
        "1_character": { "type": "string" },
        "2_environment": { "type": "string" },
        "3_action": { "type": "string" },
        "4_emotion": { "type": "string" },
        "5_camera": { "type": "string" },
        "6_lighting": { "type": "string" },
        "7_composition": { "type": "string" },
        "8_webtoon_style": { "type": "string" },
        "9_bubble": { "type": "string" },
        "10_negative": { "type": "string" }
      }
    },
    "merged_prompt": { "type": "string" },
    "negative_prompt": { "type": "string" },
    "params": {
      "type": "object",
      "properties": {
        "width": { "type": "integer" },
        "height": { "type": "integer" },
        "cfg_scale": { "type": "number" },
        "steps": { "type": "integer" },
        "seed": { "type": "integer" }
      }
    },
    "variable_resolution_log": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "variable": { "type": "string" },
          "resolved": { "type": "boolean" },
          "source": { "type": "string" },
          "value_snippet": { "type": "string" }
        }
      }
    }
  }
}
```

#### 失败处理

```
模板加载失败 → 使用内置默认模板
变量解析失败 → 使用默认值 / 跳过该变量
某层数据缺失 → 跳过该层（不注入空白内容）
```

---

### Agent ⑨ ConsistencyCheckerAgent (一致性检查)

| 项目 | 内容 |
|------|------|
| **ID** | `consistency_checker` |
| **版本** | `1.0.0` |
| **职责** | 检测生成图片中角色外观特征与人物 IP 设定的一致性 |
| **技术方案** | YOLOv8 + 特征提取 + 语义比对 |
| **执行时机** | 图片生成完成后自动触发，异步执行 |
| **超时** | 30 秒/图 |

#### 检测维度

| 维度 | 检测方法 | 比对策略 |
|------|----------|----------|
| 发色 (hair_color) | YOLOv8 分割头发区域 → 提取主色调 | 语义标签比对（"黑色" vs "黑色"） |
| 发型 (hair_style) | 图像分类模型 | 类别标签比对（"短发" vs "短发"） |
| 瞳色 (eye_color) | YOLOv8 检测眼部 → 提取虹膜颜色 | 语义标签比对 |
| 肤色 (skin_tone) | 分割皮肤区域 → 提取色值 | 色值距离计算（CIE Lab ΔE） |
| 服装 (clothing) | YOLOv8 检测服装区域 → 颜色+款式分类 | 多标签匹配度计算 |

#### 评分逻辑

```
为每个角色计算各维度的匹配度（0.0 ~ 1.0）：

  match_score = match_count / total_dimensions

  其中 match_count 为匹配成功的维度数
  每个维度的判定标准：
    - 发色/瞳色/肤色：语义标签完全匹配 → 1.0；色值距离在阈值内 → 0.5；不匹配 → 0.0
    - 发型：类别完全匹配 → 1.0；相似类别 → 0.5；不匹配 → 0.0
    - 服装：主要颜色 + 款式同时匹配 → 1.0；仅颜色匹配 → 0.5；不匹配 → 0.0

  最终判定：match_score >= 0.8 为通过；否则为不通过
```

#### 输出 JSON Schema

```json
{
  "type": "object",
  "required": ["panel_id", "checks", "passed"],
  "properties": {
    "panel_id": { "type": "string" },
    "checks": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["character_id", "character_name", "dimensions", "overall_match"],
        "properties": {
          "character_id": { "type": "string" },
          "character_name": { "type": "string" },
          "detected": {
            "type": "object",
            "description": "检测到的角色位置"
          },
          "dimensions": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "dimension": { "type": "string" },
                "expected": { "type": "string" },
                "detected": { "type": "string" },
                "match": { "type": "boolean" },
                "confidence": { "type": "number", "minimum": 0, "maximum": 100 },
                "note": { "type": "string" }
              }
            }
          },
          "overall_match": { "type": "boolean" },
          "match_score": { "type": "number", "minimum": 0, "maximum": 1 }
        }
      }
    },
    "passed": { "type": "boolean" }
  }
}
```

#### 失败处理

```
YOLOv8 检测失败（未检测到人脸） → 跳过该角色的检查，标记为"无法检测"
特征提取异常 → 单维度跳过，输出部分结果
图片格式不支持 → 标记失败
3 次重试 → 标记为"检查失败"
```

---

### Agent ⑩ QualityScorerAgent (质量评分)

| 项目 | 内容 |
|------|------|
| **ID** | `quality_scorer` |
| **版本** | `1.0.0` |
| **职责** | 多维度评估生成图片的视觉质量，输出量化评分报告 |
| **技术方案** | 基于 CLIP + 图像质量评估模型的混合方案 |
| **执行时机** | 图片生成完成后自动触发，与 Agent ⑨ 并行执行 |
| **超时** | 20 秒/图 |

#### 评分维度

| 维度 | 权重 | 评估方法 | 评分标准（0-100） |
|------|------|----------|-------------------|
| 构图 (composition) | 0.25 | CLIP 编码 + 构图规则分类器 | 构图是否合理、主体是否突出、是否符合三分法等规则 |
| 角色完整性 (character_integrity) | 0.25 | 人体关键点检测 + 异常检测 | 手指/面部/肢体有无变形、残缺、扭曲 |
| 光影 (lighting) | 0.20 | 光照一致性分析 + 直方图分析 | 光照方向是否一致、明暗对比是否合理、是否有曝光问题 |
| 细节 (detail) | 0.15 | 高频分量分析 + 纹理复杂度 | 背景细节丰富度、纹理清晰度、是否有"糊"的情况 |
| 画风一致性 (style_consistency) | 0.15 | CLIP 画风特征向量对比 | 与目标画风模板的特征向量余弦相似度 |

#### 评分逻辑

```
overall_score = Σ(score_i × weight_i)

各维度评分范围：0-100
最终推荐：
  - overall_score >= 90 → "best"（最优）
  - overall_score >= 75 → "recommended"（推荐）
  - overall_score >= 60 → "acceptable"（可用）
  - overall_score < 60  → "rejected"（需重生成）

缺陷列表（辅助决策）：
  - 检测到手部变形 → {"type": "hand_deformity", "severity": "major/minor", "location": "坐标"}
  - 检测到面部扭曲 → {"type": "face_distortion", "severity": "...", "location": "..."}
  - 检测到曝光异常 → {"type": "exposure_issue", "severity": "...", "location": "..."}
```

#### 输出 JSON Schema

```json
{
  "type": "object",
  "required": ["panel_id", "scores", "overall_score", "recommendation"],
  "properties": {
    "panel_id": { "type": "string" },
    "scores": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "dimension": {
            "type": "string",
            "enum": ["composition", "character_integrity", "lighting", "detail", "style_consistency"]
          },
          "score": { "type": "number", "minimum": 0, "maximum": 100 },
          "comment": { "type": "string" }
        }
      }
    },
    "overall_score": { "type": "number" },
    "defects": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "type": { "type": "string" },
          "severity": { "type": "string", "enum": ["minor", "major", "critical"] },
          "location": { "type": "string" }
        }
      }
    },
    "recommendation": {
      "type": "string",
      "enum": ["rejected", "acceptable", "recommended", "best"]
    }
  }
}
```

#### 失败处理

```
某个维度评分失败 → 跳过该维度，使用剩余维度重新计算权重
所有维度都失败 → 标记为"评分失败"，recommendation = "acceptable"（保守处理）
3 次重试 → 输出默认评分（所有维度 50 分）
```

---

## 3. Agent 编排与管理

### 3.1 Agent 执行顺序

```
主管线（串行）：
  TextCleaner → StoryAnalyzer → SemanticSplitter
    → StoryboardPlanner → CameraPlanner → LayoutPlanner
    → BubblePlanner → PromptGenerator

并行组（图片生成后触发）：
  ConsistencyChecker ──┐
                       ├── 并行执行
  QualityScorer     ───┘
```

### 3.2 并行执行策略

| 场景 | 策略 | 说明 |
|------|------|------|
| 多 Scene 处理 | 并发 | 同一章节的不同 Scene 可同时执行 SemanticSplitter（资源允许时） |
| 多 Panel 镜头规划 | 批量 | 5-10 个 Panel 打包为一个 LLM 请求，非并发 |
| 一致性检查 + 质量评分 | 并行 | 图片生成后，两个检测 Agent 同时执行 |
| 批量出图 | 队列+限流 | 通过 Celery 队列控制并发数（2-4） |

### 3.3 条件执行

```yaml
# Agent 开关配置
agent_execution_rules:
  text_cleaner:
    enabled: true
    skip_if: "chapter.clean_text is not null"  # 已清洗则跳过

  story_analyzer:
    enabled: true
    skip_if: "chapter has valid scenes"        # 已有有效 Scene 则跳过

  consistency_checker:
    enabled: true
    skip_if: "image.consistency_report is not null"  # 已检查则跳过

  quality_scorer:
    enabled: true
    skip_if: "image.quality_report is not null"      # 已评分则跳过
```

### 3.4 重试策略统一配置

```yaml
retry_config:
  max_retries: 3
  retry_delay:
    base: 2           # 首次重试延迟 2 秒
    multiplier: 2     # 指数退避：2, 4, 8 秒
  retry_on:
    - LLMTimeoutError
    - LLMRateLimitError
    - LLMConnectionError
    - JSONParseError
  no_retry_on:
    - SchemaValidationError     # Schema 校验失败不重试（提示改进 Prompt）
    - InvalidInputError         # 输入不合法不重试
    - TaskCancelledError        # 用户取消不重试
```

### 3.5 Agent 版本管理

```yaml
agent_versioning:
  storage: "agent_versions 表"
  
  fields:
    agent_id: string          # 如 "story_analyzer"
    version: string           # 如 "1.0.0"
    prompt_template_hash: string  # Prompt 模板的哈希值
    code_hash: string         # Agent 代码的 Git commit hash
    created_at: datetime
    created_by: string
  
  # 每次 Agent 代码或 Prompt 模板变更时，自动递增版本号
  # 执行记录中记录使用的 Agent 版本，支持追溯
```

---

## 4. Agent 通信协议

### 4.1 数据传递机制

```
所有 Agent 之间不直接函数调用，而是通过数据库传递数据：

  Agent A 产生输出
    │
    ├─ 写入数据库表（如 panels / scenes / prompts）
    ├─ 更新 Task 状态（tasks 表）
    │
    ▼
  Agent B 从数据库读取
    │
    ├─ 轮询 / 监听 Task 状态变化
    ├─ 读取 Agent A 的输出数据
    │
    ▼
  Agent B 处理并写入自己的输出
```

### 4.2 Task 对象状态追踪

```python
# Task 对象定义
@dataclass
class Task:
    task_id: str                    # UUID
    task_type: str                  # "text_clean" / "story_analysis" / ...
    agent_id: str                   # 执行此任务的 Agent ID
    agent_version: str              # Agent 版本
    chapter_id: str                 # 关联章节
    scene_ids: list[str]            # 关联场景列表
    panel_ids: list[str]            # 关联 Panel 列表
    
    status: str                     # queued / running / completed / failed / cancelled
    progress: float                 # 0.0 ~ 1.0
    error_message: Optional[str]
    
    input_snapshot: dict            # 输入数据快照
    output_summary: dict            # 输出数据摘要
    
    retry_count: int                # 当前重试次数
    max_retries: int                # 最大重试次数
    
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    
    token_usage: Optional[dict]     # LLM token 消耗统计
    cost_estimate: Optional[float]  # 成本估算
    
    created_by: str                 # 用户 ID
    created_at: datetime
    updated_at: datetime
```

### 4.3 消息队列通知

```
Agent 完成处理后，通过 Redis Pub/Sub 发送通知：

  通道（Channel）：task:{task_id}
  
  消息格式：
  {
    "type": "task_completed",
    "task_id": "uuid",
    "agent_id": "story_analyzer",
    "status": "completed",        # completed / failed
    "chapter_id": "uuid",
    "output_summary": { ... },
    "timestamp": "2026-06-27T10:30:00Z"
  }

  前端 WebSocket 服务订阅对应通道，实时推送进度给用户
  Celery Worker 也在同通道监听，触发下游 Agent
```

---

## 附录 A：Agent 调用时序示例

```
以"章节 A 的完整处理"为例：

时间线：
  T0  用户点击"AI 处理章节 A"
       │
  T1  TaskService 创建 Task #1 (type=text_clean)
       │  └─ Redis Pub: "task:uuid" → status=queued
       │
  T2  Celery Worker 消费 Task #1
       │  └─ TextCleanerAgent.process()
       │     └─ 更新 Task #1: status=running, progress=0.3
       │     └─ LLM 调用...
       │     └─ 更新 Task #1: status=completed, progress=1.0
       │     └─ Redis Pub: "task:uuid" → type=task_completed
       │
  T3  TaskService 检测到 Task #1 完成
       │  └─ 创建 Task #2 (type=story_analysis, depends_on=Task#1)
       │
  T4  Celery Worker 消费 Task #2
       │  └─ StoryAnalyzerAgent.process()
       │     └─ ...
       │
  ...（依次执行 Agent ②→③→④→⑤→⑥→⑦→⑧）
       │
  TN  所有 Agent 处理完成
       └─ 通知前端：章节 A 处理完成
```

---

*本文档完*
