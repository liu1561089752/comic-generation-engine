# AI Webtoon Factory — 工作流设计文档（Workflow Design）

> 版本：v1.0  
> 最后更新：2026-06-27  
> 状态：草案

---

## 1. 总体工作流

AI Webtoon Factory 的漫画生产管线由 **15 个步骤**组成，覆盖从原始小说文本到可发布 Webtoon 页面的全流程。

```
Novel (小说导入)
  │  输入: TXT/DOCX/MD 文件
  │  输出: Novel 对象 + Chapter 列表
  ▼
Preprocessing (文本预处理)
  │  输入: 原始文本
  │  输出: 清洗后结构化文本 + 段落编号
  ▼
World Building (世界观设定)
  │  输入: 小说文本 + 用户设定
  │  输出: World 对象 + Scene Assets
  ▼
Character IP (人物IP创建)
  │  输入: 文本分析结果 + 用户设定
  │  输出: Character 对象集 + 六视图/关系/尺寸
  ▼
Story Analysis (剧情分析)
  │  输入: 清洗文本 + 世界观
  │  输出: Scene 列表 + 情节结构
  ▼
Semantic Split (语义切句)
  │  输入: Scene 文本
  │  输出: Panel 列表
  ▼
Storyboard (分镜规划)
  │  输入: Panel 列表
  │  输出: 分镜方案 (视觉描述/构图/关键元素)
  ▼
Camera/Layout (镜头+版式)
  │  输入: Panel + 情绪
  │  输出: 镜头类型 + 页面布局
  ▼
Bubble Planning (气泡规划)
  │  输入: Panel 原文
  │  输出: Bubble 列表 (对白/旁白/内心)
  ▼
Prompt Generation (Prompt组装)
  │  输入: 所有上游数据
  │  输出: 10层结构化Prompt
  ▼
Image Generation (AI生图)
  │  输入: Prompt + 模型参数
  │  输出: 候选图 4-8 张/Panel
  ▼
Quality Check (质量检测)
  │  输入: 生成图片 + 角色设定
  │  输出: 一致性报告 + 质量评分
  ▼
Human Review (人工审核)
  │  输入: 候选图 + 检测报告
  │  输出: 选中图片 / 打回重新生成
  ▼
Comic Editor (漫画编辑)
  │  输入: 选中图片 + 气泡 + 版式
  │  输出: 最终页面
  ▼
Export (导出)
  │  输入: 最终页面
  │  输出: PNG/JPG/PSD/ZIP/长图
```

---

## 2. 步骤详细定义

### 2.1 小说导入

| 项目 | 内容 |
|------|------|
| **ID** | novel_import |
| **触发条件** | 用户上传文件或拖拽文件至导入区域 |
| **输入格式** | TXT / DOCX / Markdown（文件大小 ≤ 50MB）|
| **前置依赖** | 无（管线入口步骤）|
| **同步/异步** | 同步 |

**处理流程：**

1. **文件格式校验**：检查文件扩展名（`.txt` / `.docx` / `.md`）和 MIME 类型（使用 `python-magic` 库验证 Magic Bytes）
2. **编码检测**：使用 `chardet` 库检测文件编码（支持 UTF-8 / GBK / Shift-JIS / Big5 / EUC-KR）
3. **文本提取**：
   - TXT：直接读取
   - DOCX：使用 `python-docx` 解析
   - Markdown：去除 Markdown 标记符号，保留纯文本结构
4. **元数据提取**：尝试从文件名或文件头提取标题、作者信息
5. **章节识别**：扫描文本，识别章节标题（根据 `第X章` / `Chapter X` / `第X話` 等模式）
6. **创建数据对象**：创建 Novel 记录 + Chapter 记录列表

**输出：**
```
Novel {
  id: UUID,
  title: string,
  author: string (optional),
  file_type: "txt" | "docx" | "md",
  file_size: number (bytes),
  raw_text: text,
  chapters: Chapter[]
}
Chapter {
  id: UUID,
  novel_id: UUID,
  chapter_number: number,
  title: string,
  raw_text: text
}
```

**错误处理：**
| 错误类型 | 处理方式 |
|----------|----------|
| 不支持的文件格式 | 返回 400 错误，提示支持的格式列表：TXT / DOCX / Markdown |
| 文件损坏无法解析 | 返回 400 错误，提示用户重新上传 |
| 编码无法识别 | 返回 400 错误，提示用户手动选择编码（列出检测到的候选编码） |
| 文件超过 50MB | 返回 413 错误，提示文件过大 |
| 空文件 | 返回 400 错误，提示文件内容为空 |

**重试策略：** 不自动重试，由用户重新操作

**人工介入：** 无（全自动完成）

---

### 2.2 文本预处理（Agent ①）

| 项目 | 内容 |
|------|------|
| **ID** | text_cleaner |
| **触发条件** | 小说导入完成且 Novel.status = "uploaded"，或用户手动触发 |
| **输入** | Novel.raw_text + Chapter[].raw_text |
| **前置依赖** | 小说导入完成 |
| **同步/异步** | 异步 |

**处理流程：**

1. **空行压缩**：将连续 2 个以上的空行压缩为 1 个空行
2. **标点符号统一**：半角标点符号统一为全角（`,`→ `，`、`.` → `。`、`?` → `？`、`!` → `！`、`"` → `"`）
3. **编码错误修复**：使用 LLM + 规则引擎修复常见编码转换错误（如 `æˆ'` → `我`、`ä½ ` → `你`）
4. **章节边界识别**：根据正则模式匹配章节标题
   - 中文模式：`第[一二三四五六七八九十百千零\d]+[章节回話話]`
   - 英文模式：`Chapter\s+\d+` / `Ch\.\s*\d+`
   - 日文模式：`第[一二三四五六七八九十\d]+[章話]`
5. **段落编号**：按段落顺序编号（0001, 0002, 0003...），段落以换行符分隔
6. **对话引号统一**：识别并统一对话引号格式（中文 `""` / 英文 `""` / 日文 `「」`）

**输出：**
```
Novel {
  cleaned_text: text,       // 新增字段
  paragraph_count: number,
}
Chapter[] {
  content: text,            // 对应清洗后的内容
  clean_status: "cleaned",
  paragraph_start: number,
  paragraph_end: number,
}
```

**错误处理：**
| 错误类型 | 处理方式 |
|----------|----------|
| 文本过短（< 100 字） | 警告用户，提示文本内容异常 |
| 章节识别失败 | 创建单个默认章节，包裹全部内容，记录警告日志 |
| LLM 调用超时 | 回退到纯规则引擎（正则 + 字符替换），记录降级日志 |
| LLM 调用失败 | 同上，规则引擎降级方案 |
| 段落数量为 0 | 返回错误，提示文本格式异常 |

**重试策略：**
- LLM 调用：自动重试 2 次，间隔 3 秒
- 规则引擎处理：无需重试
- 总超时：120 秒

**人工介入：**
- 用户可在 UI 预览清洗结果，对比原始文本和清洗后文本
- 支持手动调整章节拆分边界（合并/拆分章节）
- 支持手动修正编码错误

---

### 2.3 世界观设定（World Building）

| 项目 | 内容 |
|------|------|
| **ID** | world_building |
| **触发条件** | 文本预处理完成，或用户手动触发 |
| **输入** | Novel.cleaned_text + 用户设定的世界观描述（可选） |
| **前置依赖** | 文本预处理完成 |
| **同步/异步** | 异步 |

**处理流程：**

1. **LLM 分析**：基于小说文本提取世界观要素
   - 时代背景（古代/现代/未来/奇幻/科幻）
   - 地理环境（都市/乡村/异世界/太空）
   - 社会结构（封建/民主/部落/赛博朋克）
   - 魔法/科技体系（存在/不存在、规则描述）
2. **场景资产提取**：识别小说中出现的所有场景/地点
   - 场景名称、描述、出现频率
   - 场景关联的情绪/氛围标签
3. **道具提取**：识别关键道具/物品
   - 道具名称、描述、重要性
   - 与角色/场景的关联
4. **建筑/服装风格提取**：根据时代和地域推断建筑和服装风格
5. **画风建议**：根据世界观类型推荐合适的 Webtoon 画风模板

**输出：**
```
World {
  id: UUID,
  novel_id: UUID,
  era: string,
  genre: string[],
  description: text,
  geography: { name, description, significance }[],
  social_structure: text,
  magic_tech_system: text,
}
SceneAsset {
  id: UUID,
  world_id: UUID,
  name: string,
  type: "location" | "prop" | "architecture" | "costume",
  description: text,
  mood_tags: string[],
  appearance_count: number,
}[]
StyleTemplate {
  world_id: UUID,
  recommended_styles: string[],
  art_direction_notes: text,
}
```

**错误处理：**
| 错误类型 | 处理方式 |
|----------|----------|
| LLM 分析结果不完整 | 部分字段留空，标记为 "需用户补充" |
| 文本中信息不足以分析 | 返回最小世界观对象，提示用户手动补充 |
| LLM 调用失败 | 跳过自动分析，提示用户手动填写世界观信息 |

**重试策略：** LLM 调用自动重试 2 次，间隔 3 秒；总超时 180 秒

**人工介入：**
- 用户可编辑/补充所有世界观字段
- 支持从预置模板选择世界观类型
- 可手动添加/编辑/删除场景资产
- 可上传场景参考图

---

### 2.4 人物 IP 创建（Character IP）

| 项目 | 内容 |
|------|------|
| **ID** | character_ip_creator |
| **触发条件** | 文本预处理完成 + 世界观设定完成，或用户手动触发 |
| **输入** | Novel.cleaned_text + World 对象 + 用户设定（可选） |
| **前置依赖** | 文本预处理完成（世界观设定为可选前置，可并行） |
| **同步/异步** | 异步 |

**处理流程：**

1. **角色识别**：LLM 从文本中识别所有有名字的角色
   - 角色名称、别称、首次出现位置
   - 角色分类（主角/配角/反派/龙套）
2. **外貌特征提取**：提取角色外貌描述
   - 发色/发型、瞳色、肤色、身高、体型
   - 服装风格、标志性配饰
   - 特殊特征（伤疤/纹身/机械义肢等）
3. **性格特征提取**：提取角色性格标签
   - 性格维度（外向/内向、理性/感性等）
   - 语气/说话风格
   - 常用口头禅
4. **角色关系分析**：
   - 关系类型（朋友/敌人/恋人/家人/师徒）
   - 关系强度/亲密程度
5. **角色尺寸图生成**：根据文本描述生成角色间的相对尺寸比例
6. **六视图规划**：标记需要生成的角色参考图种类（正面/侧面/背面/3/4 侧面/表情集/姿势集）

**输出：**
```
Character {
  id: UUID,
  novel_id: UUID,
  name: string,
  aliases: string[],
  role: "protagonist" | "supporting" | "antagonist" | "minor",
  appearance: {
    hair_color: string,
    hair_style: string,
    eye_color: string,
    skin_tone: string,
    height: string,
    build: string,
    distinguishing_features: string[],
    typical_clothing: string,
  },
  personality: {
    traits: string[],
    speech_style: string,
    catchphrases: string[],
  },
  relationship: {
    character_id: UUID,
    relationship_type: string,
    description: string,
  }[],
  scale: { ref_character_id: UUID, height_ratio: number },
  reference_views: string[],
  status: "analyzed",
}
```

**错误处理：**
| 错误类型 | 处理方式 |
|----------|----------|
| 角色识别遗漏 | 允许用户手动添加角色 |
| 外貌特征提取不完整 | 部分特征留空，提示用户补充 |
| 角色过多（> 50） | 自动筛选主配角，次要角色生成简略信息 |
| LLM 调用失败 | 跳过自动分析，提示用户手动创建角色 |

**重试策略：** LLM 调用自动重试 2 次，间隔 3 秒；总超时 240 秒

**人工介入：**
- 用户可编辑所有角色信息（必选步骤）
- 必须至少确认主要角色的外貌特征，否则后续生图不可用
- 支持手动绘制角色关系图
- 支持上传角色参考图作为生图依据
- 支持设置角色生图权重（越高则一致性保持越严格）

---

### 2.5 剧情分析（Agent ②）

| 项目 | 内容 |
|------|------|
| **ID** | story_analyzer |
| **触发条件** | 文本预处理完成，或用户手动触发 |
| **输入** | 清洗后的章节文本 + 段落列表 |
| **前置依赖** | 文本预处理完成 |
| **同步/异步** | 异步 |

**处理流程：**

1. **场景边界识别**：基于时间/地点/人物切换识别场景边界
   - 时间判断：时间词（"第二天"、"三小时后"、"与此同时"）
   - 地点判断：地点词（"回到家中"、"来到咖啡馆"）
   - 人物判断：新人物入场/主要人物离场
2. **Scene 要素提取**：为每个 Scene 提取
   - 摘要（1-2 句话概括）
   - 发生地点（关联世界观场景资产）
   - 发生时间（具体时间 + 氛围如"黄昏/深夜"）
   - 出场人物（关联人物 IP）
   - 情绪基调（紧张/轻松/悲伤/欢乐/悬疑）
   - 关联段落范围（start_paragraph / end_paragraph）
3. **情节结构分析**：识别本节的叙事结构
   - 开端 / 发展 / 高潮 / 结局
   - 标记高潮 Scene

**输出：**
```
Scene[] {
  id: UUID,
  chapter_id: UUID,
  scene_number: number,
  summary: string,
  location: { name: string, asset_id?: UUID },
  time: { description: string, mood: string },
  characters: { character_id: UUID, role: string }[],
  emotion: string,
  plot_position: "beginning" | "development" | "climax" | "ending",
  start_paragraph: number,
  end_paragraph: number,
  text: text,
  status: "analyzed",
}
PlotStructure {
  chapter_id: UUID,
  beginning_summary: text,
  development_summary: text,
  climax_summary: text,
  ending_summary: text,
}
```

**错误处理：**
| 错误类型 | 处理方式 |
|----------|----------|
| 场景边界识别不准确 | 默认按段落平均分割，标注置信度较低的场景 |
| LLM 返回格式异常 | 重试，使用更严格的输出格式约束 |
| 单章场景过多（> 30） | 拆分为 Act（幕）中间层级 |
| LLM 调用失败 | 回退到基于时间词/地点词的规则引擎分割 |

**重试策略：** LLM 调用自动重试 2 次，间隔 5 秒；总超时 300 秒

**人工介入：**
- 用户可调整场景边界（合并/拆分 Scene）
- 用户可编辑每个 Scene 的情绪和摘要
- 用户可调整高潮标记

---

### 2.6 语义切句（Agent ③）

| 项目 | 内容 |
|------|------|
| **ID** | semantic_splitter |
| **触发条件** | 剧情分析完成 |
| **输入** | Scene 对象（含文本、人物、地点、情绪） |
| **前置依赖** | 剧情分析完成 |
| **同步/异步** | 异步 |

**处理流程：**

1. **逐 Scene 处理**：对每个 Scene 独立执行语义切句
2. **对话切分**：每句对话（含引号）独立为一个 Panel
   - 对话内容 + 说话者 + 动作/表情描写合并至同一 Panel
3. **动作拆解**：连续动作为独立 Panel
   - 如 "推门→走进→坐下" 拆为 3 个 Panel
4. **描述合并**：环境/氛围描述与紧随的首个动作/对话合并
5. **情绪转折检测**：文本中出现情绪转折词时切换 Panel
6. **信息量控制**：每个 Panel 文本建议 10-50 字，最大不超过 80 字
7. **Panel 类型标记**：
   - `action`：动作描写
   - `dialogue`：对话（包含说话者和说话内容）
   - `narration`：旁白描述
   - `thinking`：内心独白
   - `establishing`：定场/环境镜头
   - `transition`：过渡/转场

**输出：**
```
Panel[] {
  id: UUID,
  scene_id: UUID,
  panel_number: number,
  text: string,
  original_paragraph_ref: number,
  characters: { character_id: UUID, name: string, action: string }[],
  emotion: string,
  panel_type: "action" | "dialogue" | "narration" | "thinking" | "establishing" | "transition",
  status: "split",
}
```

**切句策略矩阵：**
| 原文特征 | 切句策略 | 示例 |
|----------|----------|------|
| 含引号的对话 | 独立成格 | `"你来了。"他说。` → Panel: "你来了。"他说 |
| 连续动作（动词链） | 按动词拆分 | `推门走进咖啡馆坐下` → [推门, 走进, 坐下] |
| 环境描述段落 | 与后续动作合并 | `夜色已深。他独自走在街上。` → 合并为一个 Panel |
| 转折词（但/然而/突然） | 在转折处切分 | `他很开心。然而...` → 拆为两个 Panel |
| 内心独白 | 独立成格 | `他想：这样不行。` → Panel: 内心独白 |

**错误处理：**
| 错误类型 | 处理方式 |
|----------|----------|
| Panel 文本过长（> 80 字） | 强制在句号处拆分，标记提示 |
| 空 Scene 文本 | 跳过，记录警告 |
| LLM 调用失败 | 回退到按句号/逗号/分号的规则切分方案 |
| 单 Scene 切出 Panel > 20 | 检查 Scene 边界是否合理，若合理则不限制 |

**重试策略：** LLM 调用自动重试 2 次，间隔 3 秒；每 Scene 超时 60 秒

**人工介入：**
- 用户可调整 Panel 的文本归属（将文本片段从一个 Panel 移动到另一个）
- 用户可手动拆分/合并 Panel
- 用户可修改 Panel 类型标记

---

### 2.7 分镜规划（Agent ④）

| 项目 | 内容 |
|------|------|
| **ID** | storyboard_planner |
| **触发条件** | 语义切句完成 |
| **输入** | Panel[]（文本、人物、动作、情绪、类型）+ Scene 氛围描述 |
| **前置依赖** | 语义切句完成 |
| **同步/异步** | 异步 |

**处理流程：**

1. **视觉描述生成**：将 Panel 文本转化为画面描述
   - 画面中需要出现的视觉元素
   - 人物姿态/位置/表情
   - 背景/环境描述
2. **构图思路**：推荐的构图方式
   - 主体位置、视角中心
   - 画面深度（前景/中景/背景）
3. **关键元素标注**：标注画面中必须出现的元素
   - 角色外观描述（与人物 IP 设定一致）
   - 场景/道具描述
4. **色彩方案建议**：基于 Scene 情绪推荐配色方案
5. **视觉连续性检查**：确保相邻 Panel 的视觉元素不矛盾
   - 角色位置一致性（同一场景中角色位置不能无故变化）
   - 服装一致性（同一场景内服装连续）

**输出：**
```
PanelStoryboard {
  panel_id: UUID,
  visual_description: string,       // 画面视觉描述
  composition_notes: string,        // 构图要点
  focus: string,                    // 画面焦点
  background_description: string,   // 背景描述
  foreground_elements: string[],    // 前景元素
  character_positions: {
    character_id: UUID,
    position: "left" | "center" | "right" | "background",
    pose: string,
    expression: string,
  }[],
  key_elements: string[],           // 关键元素列表
  color_palette: string[],          // 配色方案
  mood: string,                     // 画面氛围
}
```

**分镜优先级规则：**
- 高潮/关键剧情 Panel → 详细分镜描述（50-100 字视觉描述）
- 对话 Panel → 重点描述人物表情和姿态，背景从简
- 过渡 Panel → 简洁描述（10-20 字），复用前格背景
- 定场 Panel → 详细背景描述，人物从简

**错误处理：**
| 错误类型 | 处理方式 |
|----------|----------|
| LLM 描述与角色设定矛盾 | 后处理校验，检测到矛盾时修正描述 |
| Panel 类型与分镜不匹配 | 标记不一致，提示检查 |
| LLM 调用失败 | 回退到模板化描述（基于 Panel 类型生成通用分镜）|

**重试策略：** LLM 调用自动重试 2 次，间隔 3 秒；每批 10 Panel 超时 120 秒

**人工介入：**
- 用户可编辑/替换每个 Panel 的分镜描述
- 用户可锁定已编辑内容，后续重跑管线不覆盖

---

### 2.8 镜头 + 版式规划（Agent ⑤ + Agent ⑥）

#### 2.8.1 镜头规划（Agent ⑤）

| 项目 | 内容 |
|------|------|
| **ID** | camera_planner |
| **触发条件** | 分镜规划完成 |
| **输入** | PanelStoryboard[] + Scene 情绪 + 相邻 Panel 信息 |
| **前置依赖** | 分镜规划完成 |
| **同步/异步** | 异步 |

**处理流程：**

1. **镜头类型确定**：根据 Panel 类型和情绪选择
2. **景别选择**：远景/中景/近景/特写/极特写
3. **视角选择**：平视/俯拍/仰拍/侧面/过肩/POV
4. **运镜方式**：固定/平移/推进/拉远/跟拍
5. **转场方式**：cut / fade / dissolve / match_cut / wipe
6. **镜头多样性检查**：避免连续 3 个同类型镜头

**镜头规则库：**
| Panel 类型 | 推荐镜头 | 推荐景别 | 推荐视角 |
|------------|----------|----------|----------|
| dialogue（对话） | shot-reverse-shot | 中景/中近景 | 平视/过肩 |
| action（动作） | multi-angle | 远景/中景 | 多角度切换 |
| thinking（内心） | fixed | 特写 | 平视/微俯 |
| narration（旁白） | fixed / slow pan | 中景 | 平视 |
| establishing（定场） | fixed / pan | 远景/大远景 | 平视/俯拍 |
| transition（过渡） | dissolve / fade | 不定 | 平视 |

**输出：**
```
PanelCamera {
  panel_id: UUID,
  camera_type: "long_shot" | "medium_shot" | "close_up" | "extreme_close_up" | "establishing",
  camera_angle: "eye_level" | "high_angle" | "low_angle" | "dutch" | "over_shoulder" | "pov",
  camera_movement: "fixed" | "pan" | "tilt" | "dolly" | "zoom" | "track",
  shot_size: "extreme_long" | "long" | "medium" | "close" | "extreme_close",
  transition_from_prev: "cut" | "fade" | "dissolve" | "match_cut" | "wipe",
  rationale: string,           // 选择理由
  composition_rule: "rule_of_thirds" | "center" | "leading_lines" | "symmetry" | "frame_within_frame",
}
```

#### 2.8.2 版式规划（Agent ⑥）

| 项目 | 内容 |
|------|------|
| **ID** | layout_planner |
| **触发条件** | 镜头规划完成 |
| **输入** | PanelCamera[] + 节奏标记 + 可用模板列表 |
| **前置依赖** | 镜头规划完成 |
| **同步/异步** | 异步 |

**处理流程：**

1. **节奏分析**：根据 Scene 情绪分布标记节奏变化点
2. **页面分组**：将 Panel 序列分组为页面（Page）
   - 每页 3-6 个 Panel
   - 高潮 Scene 用大格/整页
   - 对话 Scene 用 3-4 格均分布局
   - 过渡 Scene 用 5-6 格紧凑布局
3. **模板匹配**：从模板库匹配适合的页面布局模板
4. **位置分配**：为每个 Panel 分配在页面中的位置（x, y, w, h 比例）
5. **阅读顺序优化**：确保 Z 字形阅读顺序自然流畅

**页面布局规则：**
| 场景类型 | 每页 Panel 数 | 布局特征 |
|----------|--------------|----------|
| 高潮/战斗 | 1-2 | 大格/通栏/整页出血 |
| 关键剧情 | 2-3 | 一大一小/上大下小 |
| 对话 | 3-4 | 均分横格/上下等分 |
| 过渡/日常 | 5-6 | 紧凑排列/小格为主 |
| 混合节奏 | 3-5 | 大小穿插/制造节奏 |

**输出：**
```
Page[] {
  id: UUID,
  chapter_id: UUID,
  page_number: number,
  layout_template: string,
  panels: {
    panel_id: UUID,
    position: { x: number, y: number, w: number, h: number },  // 0-1 相对坐标
    row: number,
    column: number,
  }[],
  page_intent: string,       // 该页的叙事目的
  pacing: "fast" | "moderate" | "slow",
}
PacingReport {
  chapter_id: UUID,
  total_pages: number,
  climax_page: number,
  panel_density: "high" | "moderate" | "low",
  reading_time_estimate: number,  // 预计阅读时间（秒）
}
```

**错误处理：**
| 错误类型 | 处理方式 |
|----------|----------|
| Panel 数 < 3 | 无法分页，整章作为一页 |
| 布局模板不匹配 | 使用通用模板（3-4 格均分）|
| 连续同类型镜头 > 3 | LLM 重新规划，调整至少一个 |
| LLM 调用失败 | 使用布局规则引擎按模板分配 |

**重试策略：** LLM 调用自动重试 2 次，间隔 3 秒；总超时 180 秒

**人工介入：**
- 用户可拖拽调整 Panel 在页面中的位置
- 用户可切换页面布局模板
- 用户可添加/删除分页符强制页面分割

---

### 2.9 气泡规划（Agent ⑦）

| 项目 | 内容 |
|------|------|
| **ID** | bubble_planner |
| **触发条件** | 语义切句完成（不依赖镜头/版式，可并行） |
| **输入** | Panel[].text + Panel[].characters |
| **前置依赖** | 语义切句完成 |
| **同步/异步** | 异步 |

**处理流程：**

1. **文本类型识别**：分析 Panel 原文，识别文本类型
2. **气泡生成**：为每段文本创建对应的 Bubble 对象
   - 对白（dialogue）：对话气泡
   - 旁白（narration）：旁白框
   - 内心独白（thinking）：云朵/虚线气泡
   - 拟声词（sfx）：特效文字（暂不生成气泡）
3. **说话者分配**：对白气泡关联说话者角色
4. **位置建议**：基于角色位置建议气泡放置区域
5. **阅读顺序**：为多气泡 Panel 标记阅读顺序

**文本类型识别规则：**
| 文本特征 | 气泡类型 | 气泡样式 |
|----------|----------|----------|
| 包含 `"` 或 `「」` 引号 | dialogue | 椭圆气泡，带尾尖 |
| 包含 `心想` / `想道` / `思考` / `觉得` | thinking | 云朵状/虚线气泡 |
| 包含 `（旁白）` / `（叙述）` 标签 | narration | 方形旁白框，右上角 |
| 其余文本 | narration | 方形旁白框 |
| 拟声词（`砰！` / `轰隆` / `叮`） | sfx | 特效文字（无气泡） |

**输出：**
```
Bubble[] {
  id: UUID,
  panel_id: UUID,
  type: "dialogue" | "narration" | "thinking" | "sfx",
  text: string,
  speaker_character_id: UUID,   // narration/thinking 类型可为空
  position_suggestion: "left" | "right" | "top" | "center" | "bottom",
  style_ref: string,            // 气泡样式模板引用
  order: number,                // 同一 Panel 内的阅读顺序
  font_style: {
    font_family: string,
    font_size: number,
    bold: boolean,
    italic: boolean,
    color: string,
  },
  status: "identified",
}
```

**气泡排布规则：**
- 旁白框：默认左上角（Z 字头）
- 对白气泡：默认居中偏右（Z 字中部）
- 内心独白：默认左侧偏中（Z 字中部偏左）
- 阅读顺序：从左到右，从上到下
- 同 Panel 最多 4 个气泡，超过时拆分 Panel

**错误处理：**
| 错误类型 | 处理方式 |
|----------|----------|
| Panel 无文本（纯动作格） | 跳过，不生成气泡 |
| 引号识别失败 | 标记为 narration 类型，留待人工修正 |
| 说话者无法确定 | 气泡关联 `unknown_speaker`，标记人工确认 |
| LLM 调用失败 | 使用规则引擎（引号检测 + 关键词匹配）降级 |

**重试策略：** LLM 调用自动重试 2 次，间隔 3 秒；每批 20 Panel 超时 120 秒

**人工介入：**
- 用户可编辑气泡文本内容
- 用户可更改气泡类型
- 用户可调整气泡位置预设
- 用户可调节字体样式

---

### 2.10 Prompt 组装（Agent ⑧）

| 项目 | 内容 |
|------|------|
| **ID** | prompt_generator |
| **触发条件** | 所有上游数据就绪（分镜 + 镜头 + 版式 + 气泡） |
| **输入** | 角色数据 + 场景数据 + 分镜描述 + 镜头数据 + 版式数据 + 气泡数据 + 画风模板 + Prompt 模板 |
| **前置依赖** | 分镜规划 + 镜头规划 + 版式规划 + 气泡规划（全部完成） |
| **同步/异步** | 异步 |

**处理流程：**

1. **模板加载**：从 Prompt 模板库加载 10 层结构化模板
2. **变量替换**：逐层用实际数据替换模板中的 `{{变量}}`
   - Layer 1（角色）：从人物 IP 中心获取角色外观描述
   - Layer 2（环境）：从世界观场景资产获取场景描述
   - Layer 3（动作）：从分镜描述获取角色动作和姿态
   - Layer 4（情绪）：从 Scene/Panel 情绪数据获取
   - Layer 5（镜头）：从镜头规划数据获取
   - Layer 6（光照）：基于时间/氛围推导
   - Layer 7（构图）：从分镜构图规则获取
   - Layer 8（画风）：从风格模板库获取
   - Layer 9（气泡）：从气泡数据获取（绘图时预占位）
   - Layer 10（负向）：系统预设 + 用户自定义
3. **合并 Prompt**：10 层内容拼接为完整 Prompt 字符串
4. **Token 检查**：确保合并后 Prompt 在模型 token 限制内（CLIP < 150 tokens）
5. **参数绑定**：关联生图参数（宽高比、CFG Scale、Steps、Seed）

**10 层 Prompt 结构：**
```
Layer 1 (character): {{角色描述}}
  → "A young man with black hair and brown eyes, wearing a black leather jacket"
Layer 2 (environment): {{环境描述}}
  → "In a cozy coffee shop at evening, warm ambient lighting, rain outside the window"
Layer 3 (action): {{动作描述}}
  → "Sitting at a table, holding a coffee cup, looking cautiously to the right"
Layer 4 (emotion): {{情绪描述}}
  → "Nervous yet expectant, slight frown, tense shoulders"
Layer 5 (camera): {{镜头参数}}
  → "Medium shot, eye-level angle, fixed camera, shallow depth of field"
Layer 6 (lighting): {{光照参数}}
  → "Warm ambient lighting from overhead lamps, cool blue fill from window, soft shadows"
Layer 7 (composition): {{构图规则}}
  → "Rule of thirds, subject on left third, depth with blurred background"
Layer 8 (webtoon_style): {{画风模板}}
  → "Webtoon style, semi-realistic, clean lines, cell shading, high contrast, bold outlines"
Layer 9 (bubble): {{气泡占位}}
  → "Empty speech bubble on the right side, with tail pointing left"
Layer 10 (negative): {{负向提示}}
  → "nsfw, low quality, blurry, distorted hands, extra fingers, bad anatomy, mutated"
```

**输出：**
```
Prompt {
  id: UUID,
  panel_id: UUID,
  version: string,
  layers: {
    character: string,
    environment: string,
    action: string,
    emotion: string,
    camera: string,
    lighting: string,
    composition: string,
    webtoon_style: string,
    bubble: string,
    negative: string,
  },
  merged_prompt: string,        // 10 层合并后的完整 Prompt
  negative_prompt: string,       // Layer 10 内容
  params: {
    width: 1080,
    height: 1440,
    cfg_scale: 7.5,
    steps: 30,
    seed: -1,
    batch_size: 4,
  },
  status: "completed",
}
```

**错误处理：**
| 错误类型 | 处理方式 |
|----------|----------|
| 模板变量未匹配 | 跳过未匹配变量，记录警告 |
| 合并 Prompt 超长 | 自动裁剪 Layer 8 和 Layer 9 的内容 |
| 上游数据缺失 | 对应的 Layer 留空，不注入空白内容 |
| 模板加载失败 | 使用硬编码默认模板 |

**重试策略：** 纯代码逻辑，无需重试

**人工介入：**
- 用户可编辑任意 Prompt Layer
- 用户可保存自定义 Prompt 模板
- 用户可调整生图参数（宽高比、Steps、CFG Scale）

---

### 2.11 AI 生图（Image Generation）

| 项目 | 内容 |
|------|------|
| **ID** | image_generation |
| **触发条件** | Prompt 组装完成 |
| **输入** | Prompt（10 层结构化）+ 生图模型参数 |
| **前置依赖** | Prompt 组装完成 |
| **同步/异步** | 异步 |

**处理流程：**

1. **任务入队**：将生图任务提交到 Celery `ai_generation` 队列
2. **优先级分配**：按 Panel 在页面中的重要性分配优先级
   - 高潮 Panel → 高优先级
   - 封面图 → 最高优先级
   - 过渡 Panel → 普通优先级
3. **批量生成**：调用生图模型 API，每 Panel 生成 4-8 张候选图
4. **速率控制**：限制并发生图任务数 2-4 个（基于 GPU/API 配额）
5. **结果接收**：接收生成图片 + 关联 Seed 和元数据
6. **缩略图生成**：为每张生成图生成缩略图和预览图

**帧率/比例：**
- 标准尺寸：1080 × 1440（1:1.34 竖屏比例）
- 特殊尺寸：1080 × 2160（通栏大格）、1080 × 720（半格）
- 封面尺寸：1080 × 1920（适合社交媒体分享）

**输出：**
```
Image[] {
  id: UUID,
  panel_id: UUID,
  prompt_id: UUID,
  image_type: "original" | "thumbnail" | "preview",
  file_path: string,             // 存储路径
  width: number,
  height: number,
  seed: number,                  // 生成 seed（用于复现）
  model: string,                 // 使用的模型
  params_snapshot: {             // 生成参数快照
    cfg_scale: number,
    steps: number,
    model_hash: string,
  },
  batch_index: number,           // 批次内序号 (0-3)
  generated_at: datetime,
  status: "generated",
}
```

**错误处理：**
| 错误类型 | 处理方式 |
|----------|----------|
| 模型 API 超时 | 重试 3 次，间隔递增（5s / 15s / 30s）|
| 模型返回空结果 | 检查 API 响应格式，重试 |
| 模型 API 返回 429 | 限流，指数退避等待（初始 10s，最大 60s） |
| 图片内容违规（NSFW） | 标记为 rejected，自动用备用 seed 重新生成 |
| 图片尺寸异常 | 自动裁剪/缩放至标准尺寸，记录警告 |
| 所有重试均失败 | 标记 Panel 为生成失败，人工介入 |

**重试策略：**
- 最大重试次数：3 次
- 重试间隔：指数退避（5s → 15s → 30s）
- 总超时：每 Panel 300 秒
- 跨 Panel 无重试依赖

**人工介入：**
- 用户可在生图队列页面查看任务进度
- 生图失败后可手动触发单 Panel 重新生成

---

### 2.12 质量检测（Agent ⑨ + Agent ⑩）

质量检测由两个并行的 Agent 组成：一致性检查 + 质量评分。

#### 2.12.1 一致性检查（Agent ⑨）

| 项目 | 内容 |
|------|------|
| **ID** | consistency_checker |
| **触发条件** | 图片生成完成 |
| **输入** | 生成图片 + Panel 的角色 ID 列表 + 人物 IP 设定 |
| **前置依赖** | AI 生图完成 |
| **同步/异步** | 异步 |

**处理流程：**

1. **人脸检测**：使用 YOLOv8 检测图片中的人脸
2. **角色识别**：将检测到的人脸与角色设定进行匹配
3. **特征比对**：逐维度比对检测特征与设定特征
   - 发色、发型、瞳色、肤色
   - 服装颜色、服装类型
   - 特殊特征（伤疤/配饰等）
4. **综合评估**：计算一致性得分

**检测维度：**
| 维度 | 检测方法 | 权重 |
|------|----------|------|
| 发色 | 图像色值提取 + 语义比对 | 20% |
| 发型 | 图像特征分析 | 15% |
| 瞳色 | 眼睛区域色值提取 | 15% |
| 肤色 | 皮肤区域色值提取 | 10% |
| 服装颜色 | 躯干区域色值提取 | 15% |
| 服装款式 | 图像特征分析 | 15% |
| 特殊特征 | 目标检测 | 10% |

**输出：**
```
ConsistencyReport {
  id: UUID,
  image_id: UUID,
  panel_id: UUID,
  overall_score: number,          // 0-100
  passed: boolean,                // threshold ≥ 70
  checks: {
    character_id: UUID,
    character_name: string,
    detected: boolean,            // 是否检测到该角色
    dimensions: {
      dimension: string,
      expected: string,
      detected: string,
      match: boolean,
      confidence: number,
    }[],
    match_score: number,           // 该角色的综合匹配度
  }[],
  threshold: 70,
}
```

#### 2.12.2 质量评分（Agent ⑩）

| 项目 | 内容 |
|------|------|
| **ID** | quality_scorer |
| **触发条件** | 图片生成完成 |
| **输入** | 生成图片 |
| **前置依赖** | AI 生图完成 |
| **同步/异步** | 异步 |

**处理流程：**

1. **构图评分**：分析构图合理性、主体位置
2. **角色完整性评分**：检测手部/面部变形、异常肢体
3. **光影质量评分**：光照一致性、阴影质量
4. **细节丰富度评分**：背景细节、纹理质量
5. **画风一致性评分**：与目标画风的匹配程度

**评分维度：**
| 维度 | 说明 | 权重 |
|------|------|------|
| composition | 构图质量，主体突出，布局平衡 | 25% |
| character_integrity | 角色完整性（手指/面部无畸形） | 25% |
| lighting | 光影质量，层次丰富 | 15% |
| detail | 细节丰富度 | 15% |
| style_consistency | 画风一致性 | 20% |

**输出：**
```
QualityReport {
  id: UUID,
  image_id: UUID,
  panel_id: UUID,
  overall_score: number,
  scores: {
    dimension: string,
    score: number,
    comment: string,
  }[],
  defects: {
    type: string,               // "hand_deformity" | "face_distortion" | "background_artifact"
    severity: "critical" | "major" | "minor",
    location: string,
  }[],
  recommendation: "rejected" | "acceptable" | "recommended" | "best",
}
```

**错误处理：**
| 错误类型 | 处理方式 |
|----------|----------|
| 图片中无人脸 | 一致性检查跳过（空结果），标记为 N/A |
| 检测模型加载失败 | 跳过自动检测，直接进入人工审核 |
| 检测结果置信度过低 | 标记为低置信度，提示人工重点核查 |

**重试策略：** 不自动重试（检测失败直接进入人工审核）

**人工介入：**
- 用户可查看检测报告详情（哪些维度匹配/不匹配）
- 用户可调整检测阈值（严格/标准/宽松）

---

### 2.13 人工审核（Human Review）

| 项目 | 内容 |
|------|------|
| **ID** | human_review |
| **触发条件** | 质量检测完成（所有候选图） |
| **输入** | 候选图 4-8 张 + 一致性报告 + 质量评分报告 |
| **前置依赖** | 质量检测完成 |
| **同步/异步** | 同步（需要用户操作） |

**处理流程：**

1. **候选图展示**：在审核界面展示 4-8 张候选图
2. **检测报告叠加**：在图片上叠加显示检测结果标记
   - 绿色边框：该项检测通过
   - 红色边框 + 高亮：检测不一致项
3. **用户选择**：
   - ✅ **选中**：选择一张作为最终图
   - 🔄 **重新生成**：打回重生成（可选指定 seed）
   - ✏️ **编辑**：用图片编辑器手动修正
4. **批量操作**：支持批量审核多个 Panel

**审核界面布局：**
```
┌────────────────────────────────────────┐
│  Panel: 3/12  Scene: 2  选区 1/4      │
├────────────────────────────────────────┤
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐│
│  │图① 85分│  │图② 79分│  │图③ 72分│  │图④ 68分││
│  │ ✅一致 │  │⚠️瞳色⚠️│  │ ⚠️手部⚠️│  │❌多指❌││
│  └──────┘  └──────┘  └──────┘  └──────┘│
│                                          │
│  [选中] [重新生成] [编辑]  [跳过]       │
├────────────────────────────────────────┤
│  Panel 原文: "你终于来了。"神秘人说。    │
│  角色: 神秘人(图中)                      │
│  一致性: 85%  质量: 82分                │
└────────────────────────────────────────┘
```

**输出：**
```
ReviewResult {
  panel_id: UUID,
  selected_image_id: UUID | null,    // null = 全部打回
  rejected_image_ids: UUID[],        // 被拒绝的图片
  review_action: "approved" | "regenerate" | "skip",
  reviewer_notes: string,
  reviewed_at: datetime,
}
```

**错误处理：**
| 错误类型 | 处理方式 |
|----------|----------|
| 用户未操作超时 | 标记为待审核，不自动通过 |
| 无候选图（全部生成失败）| 显示错误提示，直接打回重新生成 |

**人工介入：**
- **必需步骤**：人工审核是强制性的，不可跳过
- **批量审核**：支持一键全选/通过
- **对比模式**：支持两张图片对比查看

---

### 2.14 漫画编辑（Comic Editor）

| 项目 | 内容 |
|------|------|
| **ID** | comic_editor |
| **触发条件** | 人工审核完成（Panel 有选中图片） |
| **输入** | 选中图片 + 气泡列表 + 页面版式 + Prompt 数据 |
| **前置依赖** | 人工审核完成 |
| **同步/异步** | 同步（交互式编辑） |

**处理流程：**

1. **页面初始化**：根据版式数据加载所有已审核 Panel 的选中图片
2. **图片编辑**：
   - 调整图片在 Panel 内的裁剪/缩放
   - 支持替换图片（从候选图中重新选择）
   - 支持局部重绘（Inpainting）
3. **气泡编辑**：
   - 气泡位置拖拽
   - 气泡大小调整
   - 气泡样式切换
   - 气泡文本编辑
4. **文本编辑**：
   - 文字内容修改
   - 字体/字号/颜色/样式调整
5. **图层管理**：
   - 背景层 / 图片层 / 气泡层 / 特效层
   - 图层顺序调整
   - 图层透明度/混合模式
6. **页面管理**：
   - 添加/删除页面
   - 调整页面顺序
   - 切换布局模板

**技术实现：**
- 使用 Konva.js (react-konva) 实现 Canvas 编辑
- 图层化管理，每层独立渲染
- 支持撤销/重做（UndoStack）

**输出：**
```
Page[] {
  id: UUID,
  chapter_id: UUID,
  page_number: number,
  width: number,
  height: number,
  layers: {
    type: "image" | "bubble" | "text" | "effect",
    z_index: number,
    visible: boolean,
    opacity: number,
    data: LayerData,
  }[],
  revision: number,
  status: "edited",
}
```

**人工介入：**
- 全步骤手动操作（编辑器提供所有所需工具）
- 编辑完成后手动标记完成

---

### 2.15 导出（Export）

| 项目 | 内容 |
|------|------|
| **ID** | export |
| **触发条件** | 漫画编辑完成，用户发起导出请求 |
| **输入** | 最终页面数据（图片 + 气泡 + 版式） |
| **前置依赖** | 漫画编辑完成 |
| **同步/异步** | 异步 |

**处理流程：**

1. **格式选择**：用户选择导出格式
2. **页面组包**：
   - PNG：每页导出为独立 PNG 文件，导出为 ZIP 包
   - JPG：每页导出为独立 JPG 文件，导出为 ZIP 包
   - PSD：每页导出为 PSD 文件（含图层），导出为 ZIP 包
   - 长图：所有页面垂直拼接为一张长图
   - 项目包：包含所有工程文件的可恢复项目包
3. **图片渲染**：使用 Pillow / ImageMagick 将 Canvas 渲染为位图
4. **元数据嵌入**：为每张导出图片嵌入元数据（版权信息、Pipeline 追溯信息）
5. **压缩打包**：ZIP 格式打包
6. **下载/存储**：提供下载链接或存储至用户指定路径

**导出格式规格：**
| 格式 | 分辨率 | 色彩空间 | 最大文件大小 | 说明 |
|------|--------|----------|-------------|------|
| PNG | 1080 × 1440+ | sRGB | 单页 ≤ 20MB | 无损，推荐使用 |
| JPG | 1080 × 1440+ | sRGB | 单页 ≤ 5MB | 有损，质量 90% |
| PSD | 1080 × 1440+ | sRGB | 单页 ≤ 100MB | 含图层，专业用户 |
| 长图 | 1080 × 可变 | sRGB | ≤ 200MB | 适合移动端阅读 |
| 项目包 | - | - | ≤ 500MB | 完整的可恢复项目文件 |

**输出：**
```
ExportJob {
  id: UUID,
  project_id: UUID,
  format: "png" | "jpg" | "psd" | "long_image" | "project_package",
  options: {
    quality: number,
    include_metadata: boolean,
    dpi: number,
  },
  output_paths: string[],          // 输出文件路径列表
  file_size: number,               // 总文件大小
  status: "completed" | "failed",
  completed_at: datetime,
}
```

**错误处理：**
| 错误类型 | 处理方式 |
|----------|----------|
| 磁盘空间不足 | 返回错误，提示释放空间 |
| 渲染失败 | 逐页重试，跳过失败页，记录日志 |
| 压缩失败 | 使用未压缩打包作为降级方案 |
| 导出过程中断 | 支持断点续传（部分文件已生成的不重复生成）|

**重试策略：** 自动重试 2 次，间隔 5 秒；逐页重试不影响其他页面

**人工介入：**
- 用户选择导出格式和参数
- 导出完成后下载或分享

---

## 3. 分支与并行流

### 3.1 并行执行步骤

以下步骤可以并行执行（无数据依赖冲突）：

| 并行组 | 步骤 | 说明 |
|--------|------|------|
| 并行组 A | 2.3 世界观设定 + 2.4 人物 IP 创建 | 两者都依赖 2.2 文本预处理，但彼此不依赖 |
| 并行组 B | 2.7 分镜规划 + 2.9 气泡规划 | 两者都依赖 2.6 语义切句，但彼此不依赖 |
| 并行组 C | 2.8.1 镜头规划 + 2.8.2 版式规划 | 镜头规划依赖 2.7 分镜规划；版式规划依赖 2.8.1 即镜头规划（串行）|
| 并行组 D | 2.12.1 一致性检查 + 2.12.2 质量评分 | 两者都依赖 2.11 AI 生图，但彼此不依赖 |

### 3.2 严格串行步骤

以下步骤存在严格的数据依赖关系，必须串行执行：

| 驱动步骤 | 下游步骤 | 依赖数据 |
|----------|----------|----------|
| 2.1 小说导入 | 2.2 文本预处理 | Novel.raw_text |
| 2.2 文本预处理 | 2.3 世界观设定 / 2.4 人物 IP / 2.5 剧情分析 | Novel.cleaned_text |
| 2.5 剧情分析 | 2.6 语义切句 | Scene 列表 |
| 2.6 语义切句 | 2.7 分镜规划 | Panel 列表 |
| 2.7 分镜规划 | 2.8.1 镜头规划 | PanelStoryboard |
| 2.8.1 镜头规划 | 2.8.2 版式规划 | PanelCamera |
| 2.7+2.8+2.9 | 2.10 Prompt 组装 | 全部上游数据 |
| 2.10 Prompt 组装 | 2.11 AI 生图 | Prompt |
| 2.11 AI 生图 | 2.12 质量检测 | Image |
| 2.12 质量检测 | 2.13 人工审核 | 检测报告 |
| 2.13 人工审核 | 2.14 漫画编辑 | 选中图片 |
| 2.14 漫画编辑 | 2.15 导出 | 最终页面 |

### 3.3 条件分支

```
[质量检测]
    │
    ├── 全部通过 ──→ [人工审核]
    │
    ├── 部分候选图通过 ──→ [人工审核]（仅展示通过的候选图）
    │
    ├── 全部不通过 ──→ [打回重新生成] ← 可指定固定 seed
    │                         │
    │                         └── [保留原 Prompt，重新生图]
    │
    └── 检测失败 ──→ [人工审核]（标记为"未检测"，由人工判断）
```

```
[人工审核]
    │
    ├── 选中某张图 ──→ [漫画编辑]
    │
    ├── 全部打回 ──→ [AI 生图重新执行]
    │
    └── 标记编辑 ──→ [漫画编辑]（进入手动修正模式）
```

---

## 4. 错误处理总纲

### 4.1 失败类型分类

| 类别 | 说明 | 示例 |
|------|------|------|
| **A 类：输入验证错误** | 用户输入不合法 | 不支持的文件格式、文件过大 |
| **B 类：LLM 调用错误** | AI 模型调用失败 | 超时、限流、返回格式异常 |
| **C 类：系统内部错误** | 后端逻辑错误 | 数据库连接失败、磁盘空间满 |
| **D 类：外部服务错误** | 依赖的第三方服务不可用 | SD API 宕机、网络中断 |
| **E 类：数据质量错误** | 数据处理结果不符合预期 | 文本过短、角色识别遗漏 |

### 4.2 重试策略总表

| 步骤 | 重试条件 | 最大重试次数 | 重试间隔 | 总超时 |
|------|----------|-------------|----------|--------|
| 2.1 小说导入 | 文件解析失败 | 0（不自动重试） | - | 30s |
| 2.2 文本预处理（LLM） | LLM 超时/返回异常 | 2 | 3s | 120s |
| 2.2 文本预处理（规则） | - | 0 | - | 10s |
| 2.3 世界观设定（LLM） | LLM 超时/返回异常 | 2 | 3s | 180s |
| 2.4 人物 IP 创建（LLM） | LLM 超时/返回异常 | 2 | 3s | 240s |
| 2.5 剧情分析（LLM） | LLM 超时/返回异常 | 2 | 5s | 300s |
| 2.6 语义切句（LLM） | LLM 超时/返回异常 | 2 | 3s | 60s/Scene |
| 2.7 分镜规划（LLM） | LLM 超时/返回异常 | 2 | 3s | 120s/批 |
| 2.8 镜头+版式（LLM） | LLM 超时/返回异常 | 2 | 3s | 180s |
| 2.9 气泡规划（LLM） | LLM 超时/返回异常 | 2 | 3s | 120s/批 |
| 2.10 Prompt 组装 | - | 0（纯代码） | - | 5s |
| 2.11 AI 生图 | API 超时/429/NSFW | 3 | 5s→15s→30s | 300s/Panel |
| 2.12 质量检测 | 检测模型加载失败 | 0（跳过→人工） | - | 60s |
| 2.13 人工审核 | 用户未操作 | 0（等待操作） | - | 无超时 |
| 2.14 漫画编辑 | - | 0（交互操作） | - | 无超时 |
| 2.15 导出 | 渲染/打包失败 | 2 | 5s | 600s |

### 4.3 降级策略

| 组件 | 主方案 | 降级方案 |
|------|--------|----------|
| **文本清洗 LLM** | LLM 修复编码错误 | 规则引擎（chardet + 正则替换） |
| **章节识别 LLM** | LLM 识别章节边界 | 正则匹配（`第X章` / `Chapter X`） |
| **语义切句 LLM** | LLM 语义切句 | 规则切分（按句号/对话/逗号） |
| **分镜规划 LLM** | LLM 生成视觉描述 | 模板化描述（基于 Panel 类型的预制模板）|
| **镜头规划 LLM** | LLM 镜头推荐 | 规则引擎（Panel 类型→镜头类型映射表）|
| **质量检测** | AI 视觉模型检测 | 跳过自动检测，全部标记为"需人工检查" |

### 4.4 人工介入阈值

| 条件 | 动作 |
|------|------|
| 某 Panel 一致性得分 < 50 | 在审核界面标记为"建议打回" |
| 某 Panel 质量得分 < 60 | 在审核界面标记为"建议打回" |
| 同一 Panel 连续 3 次生成失败 | 自动暂停该 Panel 的生成任务，通知人工介入 |
| 同一项目连续 5 个 Panel 生成失败 | 暂停该项目管线，通知人工检查模型配置和 Prompt 质量 |
| LLM 连续 5 次调用失败 | 切换 备用 LLM 模型 |
| 生图 API 连续 3 次返回 429 | 降低并发数（2→1），通知用户限流 |
| 手动编辑超过 30 分钟未保存 | 自动保存当前编辑状态（草稿）|

### 4.5 超时设置

| 场景 | 超时时间 | 超时后行为 |
|------|----------|-----------|
| API 请求（LLM）| 60s | 触发重试 |
| API 请求（生图）| 120s | 触发重试 |
| 文件上传 | 300s | 断开连接，提示网络问题 |
| 用户审核（无操作）| 无超时 | 标记为待审核状态 |
| 导出任务 | 600s | 标记失败，提示重试 |
| 全局管线处理 | 12h（单话）| 标记项目暂停，通知用户 |

---

## 5. 异步任务设计

### 5.1 同步 vs 异步划分

| 步骤 | 同步/异步 | 说明 |
|------|-----------|------|
| 2.1 小说导入 | 同步 | 文件上传和解析直接返回结果，CUD 操作 |
| 2.2 文本预处理 | 异步 | AI 分析任务 |
| 2.3 世界观设定 | 异步 | AI 分析任务 |
| 2.4 人物 IP 创建 | 异步 | AI 分析任务 |
| 2.5 剧情分析 | 异步 | AI 分析任务 |
| 2.6 语义切句 | 异步 | AI 分析任务 |
| 2.7 分镜规划 | 异步 | AI 分析任务 |
| 2.8 镜头+版式 | 异步 | AI 分析任务 |
| 2.9 气泡规划 | 异步 | AI 分析任务 |
| 2.10 Prompt 组装 | 同步 | 纯模板引擎，无需异步 |
| 2.11 AI 生图 | 异步 | 重计算任务，需要排队 |
| 2.12 质量检测 | 异步 | AI 视觉检测任务 |
| 2.13 人工审核 | 同步 | 需要用户交互 |
| 2.14 漫画编辑 | 同步 | 需要用户交互 |
| 2.15 导出 | 异步 | 文件渲染和打包任务 |

### 5.2 任务状态流转

```
                    ┌─────────┐
                    │ Queued  │  (排队中)
                    └────┬────┘
                         │ 调度
                    ┌────▼────┐
                    │ Running │  (运行中)
                    └────┬────┘
               ┌─────────┼─────────┐
               ▼         ▼         ▼
          ┌────────┐ ┌────────┐ ┌────────┐
          │Completed│ │ Failed │ │Cancelled│
          └────────┘ └────────┘ └────────┘
               │           │
               │      ┌────▼────┐
               │      │ Retrying│  (重试中)
               │      └────┬────┘
               │           │
               │      ┌────▼────┐
               │      │ Running │
               │      └─────────┘
               │
          [触发下游任务]
```

### 5.3 任务队列设计

| 队列名 | 用途 | 优先级 | 最大并发 |
|--------|------|--------|----------|
| `ai_generation` | AI 生图任务 | 最高 | 2-4 |
| `ai_analysis` | AI 分析任务（LLM 调用）| 高 | 8-16 |
| `export` | 导出任务 | 中 | 1-2 |
| `default` | 其他后台任务 | 低 | 4 |

**队列优先级规则：**
```
ai_generation > ai_analysis > export > default
```

### 5.4 任务回调机制

**WebSocket 实时推送：**

```
客户端                             服务端
  │                                   │
  │  ├─ connect /ws/task/{task_id}
  │                                   │
  │  │  [任务状态变更]
  │                                   │
  │  ◄─ { type: "task_status",
  │       task_id: "uuid",
  │       status: "running",
  │       progress: 30,
  │       message: "正在生成第 3/12 Panel (25%)"
  │     }
  │                                   │
  │  [任务完成]
  │                                   │
  │  ◄─ { type: "task_completed",
  │       task_id: "uuid",
  │       result: { panel_id, images_count, ... }
  │     }
  │                                   │
  │  [任务失败]
  │                                   │
  │  ◄─ { type: "task_failed",
  │       task_id: "uuid",
  │       error: { code, message, retry_count }
  │     }
```

**HTTP 轮询（备选方案）：**
```
GET /api/v1/tasks/{task_id}/status
→ { status, progress, result/error }
轮询间隔: 3s（运行中）/ 30s（排队中）
```

### 5.5 管线编排流程

```
pipeline_service.py
  │
  ├── start_pipeline(chapter_id):
  │    ├── 创建 PipelineRun 记录
  │    ├── 串行：submit_task(text_cleaner, chapter_id)
  │    │         → 等待完成
  │    ├── 串行：submit_task(story_analyzer, chapter_id)
  │    │         → 等待完成
  │    ├── 并行：submit_task(semantic_splitter, chapter_id)
  │    │         → 等待完成
  │    ├── 并行：submit_task(storyboard_planner, batch_panels)
  │    │    +   submit_task(bubble_planner, batch_panels)
  │    │         → 等待全部完成
  │    ├── 串行：submit_task(camera_planner, batch_panels)
  │    │         → 等待完成
  │    ├── 串行：submit_task(layout_planner, all_panels)
  │    │         → 等待完成
  │    ├── 同步：execute_prompt_generation(all_panels)
  │    ├── 异步：submit_task(image_generation, batch_panels)
  │    │         → 等待全部完成（最长等待）
  │    ├── 并行：submit_task(consistency_check, images)
  │    │    +   submit_task(quality_score, images)
  │    │         → 等待全部完成
  │    └── 标记：pipeline.status = "awaiting_review"
  │
  └── 用户完成 review 后：
       └── pipeline.status = "editing"
```

### 5.6 任务生命周期管理

| 阶段 | 数据库记录 | Redis 缓存 | 前端展示 |
|------|-----------|-----------|----------|
| 排队中 | Task.status = "queued" | List 队列中 | 排队图标 + 位置 |
| 运行中 | Task.status = "running", started_at | - | 进度条 + 消息 |
| 完成 | Task.status = "completed", result, completed_at | 结果缓存 24h | 成功提示 |
| 失败 | Task.status = "failed", error, retry_count | - | 失败提示 + 原因 |
| 取消 | Task.status = "cancelled" | 从队列移除 | 取消提示 |
| 重试中 | Task.status = "retrying", retry_count++ | - | 重试提示 |

---

## 6. 管线配置与扩展

### 6.1 工作流配置示例

```yaml
# workflow_standard.yaml（标准模式）
workflow:
  name: "标准制作流程"
  
  agents:
    - id: text_cleaner
      enabled: true
      provider: llm+rule   # 使用 LLM + 规则引擎双重方案
    
    - id: story_analyzer
      enabled: true
      provider: llm
      model: gpt-4o        # 使用更强的模型处理分析任务
    
    - id: semantic_splitter
      enabled: true
      provider: llm
    
    - id: storyboard_planner
      enabled: true
      provider: llm
    
    - id: camera_planner
      enabled: true
      provider: llm
    
    - id: layout_planner
      enabled: true
      provider: llm
    
    - id: bubble_planner
      enabled: true
      provider: llm
    
    - id: prompt_generator
      enabled: true
      provider: template   # 模板引擎
    
    - id: image_generation
      enabled: true
      provider: sd_api
      batch_size: 4
    
    - id: consistency_checker
      enabled: true
      provider: ai_vision
    
    - id: quality_scorer
      enabled: true
      provider: ai_vision
  
  parallel_groups:
    - [world_building, character_ip_creator]    # 并行组
    - [storyboard_planner, bubble_planner]
    - [consistency_checker, quality_scorer]
```

```yaml
# workflow_quick.yaml（快捷模式）
workflow:
  name: "快速预览模式"
  
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
    - id: image_generation
      enabled: true
      batch_size: 2         # 减少候选图数量
    - id: consistency_checker
      enabled: false        # 跳过质量检测
    - id: quality_scorer
      enabled: false
    - id: human_review
      enabled: false        # 自动选第一张
      auto_select: first
    
    auto_pilot: true        # 全自动模式
```

### 6.2 管线事件与钩子

| 事件 | 触发时机 | 数据载荷 |
|------|----------|----------|
| `pipeline.started` | 管线启动 | chapter_id, pipeline_run_id |
| `pipeline.completed` | 管线完成 | chapter_id, stats |
| `pipeline.failed` | 管线失败 | chapter_id, error |
| `agent.started` | Agent 开始执行 | agent_id, input_summary |
| `agent.completed` | Agent 执行完成 | agent_id, output_summary |
| `agent.failed` | Agent 执行失败 | agent_id, error, retry_count |
| `panel.generated` | Panel 生图完成 | panel_id, images_count |
| `panel.reviewed` | Panel 审核完成 | panel_id, action |
| `export.completed` | 导出完成 | export_job_id, format |

---

## 附录 A：术语表

| 术语 | 说明 |
|------|------|
| **Novel** | 导入的原始小说 |
| **Chapter** | 章节，Novel 的子集 |
| **Scene** | 场景，按时间/地点/人物切换划分的段落，Chapter 的子集 |
| **Panel** | 画格，漫画中的单幅画面，Scene 的子集 |
| **Shot** | 镜头描述，Panel 的视觉化子集 |
| **Bubble** | 气泡，包含对白/旁白/内心独白 |
| **Prompt** | 生图提示词，10 层结构化 |
| **Page** | 漫画页面，包含多个 Panel |
| **Agent** | AI 处理单元，管线中的功能模块 |
| **Pipeline** | 管线，从输入到输出的完整处理流程 |
