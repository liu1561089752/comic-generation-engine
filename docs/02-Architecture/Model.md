# AI Webtoon Factory — AI 模型设计文档（Model Design）

> **版本**：v1.0  
> **最后更新**：2026-06-27  
> **状态**：草案

---

## 目录

1. [模型抽象层架构](#1-模型抽象层架构)
2. [适配器接口定义](#2-适配器接口定义)
3. [各模型实现](#3-各模型实现)
4. [模型切换策略](#4-模型切换策略)
5. [模型调用管理](#5-模型调用管理)
6. [模型配置管理](#6-模型配置管理)
7. [Embedding 与视觉检测模型](#7-embedding-与视觉检测模型)

---

## 1. 模型抽象层架构

### 1.1 设计原则

系统遵循 **AI 无关性** 原则，不绑定任何特定 AI 模型或服务提供商。所有 AI 能力通过适配器模式抽象，确保：

- **可替换**：任意模型可在不修改业务代码的情况下替换
- **可扩展**：新增模型只需要实现对应的适配器接口
- **可降级**：主模型失败时可自动切换到备用模型
- **可监控**：所有模型调用经过统一的日志和监控层

### 1.2 模型分类

| 类别 | 用途 | 抽象接口 | 适配器数量（内置） |
|------|------|----------|-------------------|
| **LLM（大语言模型）** | 文本处理 Agent（剧情分析、语义切句、分镜规划等） | `LLMAdapter` | 4+ |
| **生图模型** | 图片生成（Panel 出图、角色表情/姿势生成） | `ImageGenAdapter` | 4+ |
| **Embedding 模型** | 语义搜索、相似度比对、人物特征向量化 | `EmbeddingAdapter` | 2+ |
| **视觉检测模型** | 角色一致性检测、OCR 漏字检测、画风比对 | `VisionAdapter` | 2+ |

### 1.3 适配器模式架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                               Agent 层                                  │
│  文本清洗   剧情分析   语义切句   分镜规划   镜头规划   版式规划          │
│  气泡规划   Prompt生成 一致性检查 质量评分                              │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ 调用
┌────────────────────────────────▼────────────────────────────────────────┐
│                         适配器接口层                                     │
│  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────────┐  │
│  │   LLMAdapter       │  │  ImageGenAdapter   │  │  EmbeddingAdapter│  │
│  │   ├─ chat()        │  │  ├─ generate()     │  │  ├─ embed()      │  │
│  │   ├─ embed()       │  │  ├─ get_models()   │  │  └─ health()     │  │
│  │   └─ health()      │  │  └─ health()       │  └──────────────────┘  │
│  └────────┬───────────┘  └────────┬───────────┘                        │
│  ┌────────────────────┐  ┌────────────────────┐                        │
│  │   VisionAdapter    │  │  (其他模型适配器)   │                        │
│  │   ├─ detect()      │  │  └─ ...            │                        │
│  │   ├─ compare()     │  └────────────────────┘                        │
│  │   └─ health()      │                                                │
│  └────────────────────┘                                                │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
┌────────────────────────────────┼────────────────────────────────────────┐
│                                │                                         │
│  ┌─────────────────────────────▼──────┐  ┌─────────────────────────────┐ │
│  │        LLM 实现                   │  │       生图模型实现           │ │
│  │  ┌────────────────────┐          │  │  ┌────────────────────┐     │ │
│  │  │ OpenAICompatible   │          │  │  │ SDAPIAdapter       │     │ │
│  │  │ （兼容OpenAI格式）  │          │  │  │ (SD WebUI API)     │     │ │
│  │  └────────────────────┘          │  │  └────────────────────┘     │ │
│  │  ┌────────────────────┐          │  │  ┌────────────────────┐     │ │
│  │  │ ClaudeAdapter      │          │  │  │ MidjourneyAdapter  │     │ │
│  │  │ （通过代理转换）    │          │  │  │ (MJ-Proxy)         │     │ │
│  │  └────────────────────┘          │  │  └────────────────────┘     │ │
│  │  ┌────────────────────┐          │  │  ┌────────────────────┐     │ │
│  │  │ CustomAdapter      │          │  │  │ ComfyUIAdapter     │     │ │
│  │  │ （用户自定义）      │          │  │  │ (工作流API)        │     │ │
│  │  └────────────────────┘          │  │  └────────────────────┘     │ │
│  └──────────────────────────────────┘  └─────────────────────────────┘ │
│                                                                         │
│  ┌──────────────────────────────────┐  ┌─────────────────────────────┐ │
│  │   Embedding 实现                 │  │  视觉检测实现                │ │
│  │  ┌────────────────────┐          │  │  ┌────────────────────┐     │ │
│  │  │ OpenAIEmbedAdapter │          │  │  │ YOLOv8Adapter      │     │ │
│  │  └────────────────────┘          │  │  │ (角色检测)          │     │ │
│  │  ┌────────────────────┐          │  │  └────────────────────┘     │ │
│  │  │ BGEEmbedAdapter    │          │  │  ┌────────────────────┐     │ │
│  │  │ （本地BGE模型）     │          │  │  │ GroundingDINOAdapter│     │ │
│  │  └────────────────────┘          │  │  │ (目标检测/OCR)      │     │ │
│  └──────────────────────────────────┘  └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 适配器接口定义

### 2.1 LLMAdapter — 大语言模型适配器

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ChatMessage:
    role: str                      # "system" | "user" | "assistant"
    content: str
    name: Optional[str] = None

@dataclass
class ChatResult:
    content: str                   # 模型回复内容
    finish_reason: str = "stop"    # "stop" | "length" | "error"
    usage: dict = field(default_factory=dict)
    # {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300}
    model_name: str = ""
    latency_ms: float = 0.0

class LLMAdapter(ABC):
    """所有 LLM 适配器必须实现的抽象基类"""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> ChatResult:
        """调用 LLM 进行对话

        Args:
            messages: 对话消息列表
            temperature: 生成温度 (0.0~2.0)
            max_tokens: 最大输出 token 数
            stream: 是否使用流式输出

        Returns:
            ChatResult: 包含回复内容和元数据
        """
        ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """调用 Embedding 模型获取文本向量

        Args:
            texts: 文本列表

        Returns:
            向量列表，每个文本对应一个向量
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """检查模型服务是否可用"""
        ...

    @abstractmethod
    async def get_models(self) -> list[dict]:
        """获取可用模型列表

        Returns:
            [{"id": "gpt-4o", "name": "GPT-4o", "capabilities": [...]}, ...]
        """
        ...
```

### 2.2 ImageGenAdapter — 生图模型适配器

```python
@dataclass
class ImageGenResult:
    images: list[bytes]            # 生成的图片二进制数据
    seeds: list[int]               # 每张图片使用的 seed
    infos: list[dict]              # 每张图片的详细信息
    # [{"seed": 12345, "steps": 30, "cfg_scale": 7.5, ...}, ...]
    model_name: str = ""
    latency_ms: float = 0.0

class ImageGenAdapter(ABC):
    """所有生图模型适配器必须实现的抽象基类"""

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
        """调用生图模型生成图片

        Args:
            prompt: 正向提示词
            negative_prompt: 负向提示词
            width: 图片宽度（像素）
            height: 图片高度（像素）
            steps: 采样步数
            cfg_scale: CFG 引导强度
            seed: 随机种子（-1 表示随机）
            batch_size: 单次生成数量
            **kwargs: 模型特定参数（如 ControlNet、LoRA 等）

        Returns:
            ImageGenResult: 包含生成图片和元数据
        """
        ...

    @abstractmethod
    async def get_available_models(self) -> list[str]:
        """获取该后端支持的模型列表"""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """检查模型服务是否可用"""
        ...
```

### 2.3 EmbeddingAdapter — Embedding 模型适配器

```python
@dataclass
class EmbeddingResult:
    embeddings: list[list[float]]   # 向量列表
    dimensions: int                 # 向量维度
    model_name: str = ""
    latency_ms: float = 0.0

class EmbeddingAdapter(ABC):
    @abstractmethod
    async def embed(
        self,
        texts: list[str],
        model: Optional[str] = None,
    ) -> EmbeddingResult:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...
```

### 2.4 VisionAdapter — 视觉检测模型适配器

```python
@dataclass
class DetectionResult:
    detections: list[dict]         # 检测结果列表
    # [{"bbox": [x1,y1,x2,y2], "label": "face", "confidence": 0.95}, ...]
    image_width: int
    image_height: int
    latency_ms: float = 0.0

class VisionAdapter(ABC):
    @abstractmethod
    async def detect(
        self,
        image: bytes,
        target_labels: Optional[list[str]] = None,
    ) -> DetectionResult:
        """检测图片中的目标对象

        Args:
            image: 图片二进制数据
            target_labels: 要检测的目标标签列表（None 表示检测所有）

        Returns:
            DetectionResult: 检测结果
        """
        ...

    @abstractmethod
    async def compare(
        self,
        image_a: bytes,
        image_b: bytes,
        comparison_type: str = "face",
        # "face" | "style" | "color" | "text"
    ) -> dict:
        """比对两张图片的指定维度

        Returns:
            {"score": 0.85, "details": {...}, "passed": True}
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...
```

---

## 3. 各模型实现

### 3.1 OpenAICompatibleAdapter（通用 LLM 适配器）

**设计目标**：兼容所有 OpenAI API 格式的 LLM 服务，覆盖市面上 90%+ 的 LLM 提供商。

**支持的提供商**：

| 提供商 | API Base URL | 模型示例 |
|--------|-------------|----------|
| OpenAI | `https://api.openai.com/v1` | GPT-4o, GPT-4-turbo, GPT-4o-mini |
| DeepSeek | `https://api.deepseek.com/v1` | deepseek-chat, deepseek-reasoner |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | qwen-max, qwen-turbo |
| Moonshot | `https://api.moonshot.cn/v1` | moonshot-v1-8k, moonshot-v1-32k |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | glm-4, glm-4-flash |
| 本地 ollama | `http://localhost:11434/v1` | llama3, qwen2, mistral |

**参数映射表**：

| OpenAI 参数 | 适配器统一参数 | 说明 |
|-------------|---------------|------|
| `model` | `model_name`（配置时指定） | 模型名称 |
| `messages` | `messages` | 消息列表（标准格式） |
| `temperature` | `temperature` | 0.0~2.0 |
| `max_tokens` | `max_tokens` | 最大输出 tokens |
| `stream` | `stream` | 流式输出 |
| `top_p` | `top_p` | 核采样 |
| `frequency_penalty` | `frequency_penalty` | 频率惩罚 |
| `presence_penalty` | `presence_penalty` | 存在惩罚 |
| `stop` | `stop` | 停止序列 |

**错误处理机制**：

| HTTP 状态码 | 错误类型 | 处理策略 |
|-------------|----------|----------|
| 400 | Bad Request | 记录日志，返回参数校验错误 |
| 401 | Authentication Error | 触发告警，通知用户更新 API Key |
| 429 | Rate Limit | 指数退避重试（最多 3 次），等待后重试 |
| 500 | Server Error | 切换备用模型（如配置），或返回友好错误 |
| 503 | Service Unavailable | 等待 30 秒后重试，超过重试次数则降级 |
| 超时 | Timeout | 默认超时 120 秒，超时后重试 1 次 |

**代码示例**：

```python
class OpenAICompatibleAdapter(LLMAdapter):
    def __init__(self, config: dict):
        self.api_base = config["api_base"]
        self.api_key = config["api_key"]
        self.model_name = config.get("model", "gpt-4o")
        self.client = OpenAI(
            base_url=self.api_base,
            api_key=self.api_key,
            timeout=120.0,
        )

    async def chat(self, messages, temperature=0.7, max_tokens=4096, stream=False):
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[m.__dict__ for m in messages],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
            )
            # 处理响应，封装为 ChatResult
            ...
        except RateLimitError:
            # 指数退避重试
            ...
        except Exception as e:
            # 通用错误处理
            ...
```

### 3.2 SDAPIAdapter（Stable Diffusion 生图适配器）

**设计目标**：兼容 Stable Diffusion WebUI API 格式，支持 SDXL、SD3、SD1.5 等多个版本。

**支持的端点**：

| 端点 | 用途 | 输入参数 |
|------|------|----------|
| `/sdapi/v1/txt2img` | 文生图 | prompt, negative_prompt, width, height, steps, cfg_scale, seed, batch_size |
| `/sdapi/v1/img2img` | 图生图 | + init_images, denoising_strength |
| `/sdapi/v1/extra-single-image` | 高清修复 | upscaling_resize, upscaler_1 |
| `/sdapi/v1/options` | 获取/设置全局配置 | sd_model_checkpoint, CLIP_stop_at_last_layers |
| `/sdapi/v1/sd-models` | 获取模型列表 | — |

**高级参数（通过 kwargs 透传）**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `controlnet_units` | list[dict] | ControlNet 配置，如 Reference-Only、Canny、OpenPose |
| `alwayson_scripts` | dict | 扩展脚本参数，如 ADetailer（面部修复） |
| `lora_weights` | list[dict] | LoRA 权重配置，用于角色一致性微调 |
| `override_settings` | dict | 覆盖 SD 全局设置（如 CLIP skip、VAE） |

**参数映射表**：

| 适配器统一参数 | SD API 参数 | 默认值 |
|---------------|-------------|--------|
| `prompt` | `prompt` | — |
| `negative_prompt` | `negative_prompt` | `""` |
| `width` | `width` | 1080 |
| `height` | `height` | 1440 |
| `steps` | `steps` | 30 |
| `cfg_scale` | `cfg_scale` | 7.5 |
| `seed` | `seed` | -1 |
| `batch_size` | `batch_size` | 4 |

### 3.3 MidjourneyAdapter（Midjourney 适配器）

**设计目标**：通过 MJ-Proxy 中间件接入 Midjourney，采用"提交→轮询"异步模式。

**接入架构**：

```
┌──────────┐     HTTP      ┌────────────┐    Discord    ┌──────────┐
│  Agent   │ ──────────▶   │ MJ-Proxy   │ ────────────▶ │   MJ     │
│  层       │ ◀──────────   │ (中间件)    │ ◀──────────── │  Bot     │
└──────────┘    轮询状态    └────────────┘               └──────────┘
```

**API 交互流程**：

```python
class MidjourneyAdapter(ImageGenAdapter):
    async def generate(self, prompt, **kwargs):
        # 1. 提交生图任务
        task_id = await self._submit_imagine(prompt, **kwargs)

        # 2. 轮询结果（最长等待 300 秒）
        result = await self._poll_result(task_id, max_wait=300)

        # 3. 对结果进行 upscale（如需要）
        if result.upscale_needed:
            result = await self._upscale(task_id)

        return result

    async def _submit_imagine(self, prompt, **kwargs) -> str:
        """提交 imagine 任务，返回 task_id"""
        ...

    async def _poll_result(self, task_id, max_wait) -> ImageGenResult:
        """每 5 秒轮询一次，直到完成或超时"""
        ...
```

**参数限制说明**：

| 参数 | Midjourney 限制 | 适配器处理 |
|------|----------------|-----------|
| `width/height` | 仅支持特定比例（1:1, 4:3, 3:4, 16:9, 9:16） | 自动映射到最接近的宽高比 |
| `steps` | MJ 不支持 | 忽略 |
| `cfg_scale` | MJ 使用 `--stylize` 和 `--chaos` | 映射为 MJ 参数 |
| `seed` | MJ 使用 `--seed` | 支持 |
| `batch_size` | MJ 默认一次生成 4 张 | 支持 |

### 3.4 ComfyUIAdapter（ComfyUI 适配器）

**设计目标**：通过 ComfyUI API 接入自定义工作流，支持高级用户自定义生图管线。

**工作流模板管理**：

```python
class ComfyUIAdapter(ImageGenAdapter):
    def __init__(self, config: dict):
        self.endpoint = config["endpoint"]           # http://localhost:8188
        self.workflow_dir = config["workflow_dir"]   # 工作流模板存储目录
        self.workflow_registry: dict[str, dict] = {} # 已加载的工作流模板

    async def load_workflow(self, name: str) -> dict:
        """从文件加载工作流模板 JSON"""
        path = os.path.join(self.workflow_dir, f"{name}.json")
        with open(path) as f:
            workflow = json.load(f)
        self.workflow_registry[name] = workflow
        return workflow

    async def generate(self, prompt, workflow_name="default", **kwargs):
        """基于指定工作流模板生图"""
        # 1. 加载工作流模板
        workflow = self.workflow_registry.get(workflow_name) or \
                   await self.load_workflow(workflow_name)

        # 2. 参数注入（替换工作流中的占位符节点）
        workflow = self._inject_params(workflow, prompt, kwargs)

        # 3. 提交任务
        result = await self._queue_prompt(workflow)

        # 4. 轮询结果
        images = await self._poll_images(result["prompt_id"])

        return ImageGenResult(images=images, ...)
```

**参数注入规则**：

| 工作流节点类型 | 注入参数 | 说明 |
|---------------|----------|------|
| CLIPTextEncode (positive) | `prompt` | 替换正向提示词 |
| CLIPTextEncode (negative) | `negative_prompt` | 替换负向提示词 |
| EmptyLatentImage | `width`, `height`, `batch_size` | 设置画布尺寸 |
| KSampler | `steps`, `cfg_scale`, `seed` | 设置采样参数 |
| CheckpointLoaderSimple | `model_name` | 替换模型 |
| ControlNetLoader | `controlnet_units` | ControlNet 配置 |

---

## 4. 模型切换策略

### 4.1 切换层级

模型配置支持三个层级的覆盖，优先级从高到低：

```
┌──────────────────────────────────────────┐
│  全局默认配置（系统设置）                   │
│  LLM: GPT-4o                             │
│  生图: SDXL                              │
└────────────────┬─────────────────────────┘
                 │ 被项目级配置覆盖
┌────────────────▼─────────────────────────┐
│  项目级配置                                │
│  LLM: DeepSeek-chat（项目A用了更便宜的模型）│
│  生图: Midjourney（项目A需要MJ画风）       │
└────────────────┬─────────────────────────┘
                 │ 被 Agent 级配置覆盖
┌────────────────▼─────────────────────────┐
│  Agent 级配置（任务级）                    │
│  剧情分析: GPT-4o（需要最强推理）          │
│  语义切句: GPT-4o-mini（轻量任务）         │
│  生图: SDXL（常规出图）                   │
└──────────────────────────────────────────┘
```

### 4.2 配置数据结构

```python
# 模型配置项
ModelConfig = {
    "adapter_type": str,          # "openai_compatible" | "sd_api" | "midjourney" | ...
    "model": str,                 # 模型名称，如 "gpt-4o", "sd_xl_base_1.0"
    "api_base": str,              # API 地址
    "api_key": str,               # API Key（加密存储）
    "parameters": dict,           # 默认参数
    "max_retries": int,           # 最大重试次数
    "timeout": float,             # 超时时间（秒）
    "fallback_adapter": str,      # 备用适配器 ID（降级用）
}

# 系统模型配置
SYSTEM_MODEL_CONFIG = {
    "llm": ModelConfig,
    "image_gen": ModelConfig,
    "embedding": ModelConfig,
    "vision": ModelConfig,
}

# Agent 模型映射
AGENT_MODEL_MAP = {
    "text_cleaner": {"llm": "gpt-4o-mini"},
    "story_analyzer": {"llm": "gpt-4o"},
    "semantic_splitter": {"llm": "gpt-4o"},
    "storyboard_planner": {"llm": "gpt-4o-mini"},
    "camera_planner": {"llm": "gpt-4o-mini"},
    "layout_planner": {"llm": "gpt-4o-mini"},
    "bubble_planner": {"llm": "gpt-4o-mini"},
    "prompt_generator": {},       # 纯代码实现，不依赖 LLM
    "consistency_checker": {"vision": "yolov8"},
    "quality_scorer": {"vision": "yolov8"},
}
```

### 4.3 切换 API

```python
# 在运行时切换 Agent 使用的模型
class ModelService:
    async def set_agent_model(
        self,
        agent_id: str,
        model_type: str,     # "llm" | "image_gen" | "vision"
        adapter_type: str,   # "openai_compatible" | "sd_api" | ...
        config: dict,
    ) -> None:
        """设置指定 Agent 使用的模型"""
        ...

    async def switch_llm(self, adapter_type: str, config: dict) -> bool:
        """全局切换 LLM 模型（立即生效）"""
        # 1. 创建新适配器实例
        adapter = self._create_adapter("llm", adapter_type, config)
        # 2. 运行健康检查
        if not await adapter.health_check():
            raise ModelNotAvailable("模型不可用")
        # 3. 更新全局配置
        self._update_config("llm", adapter_type, config)
        # 4. 替换运行中的适配器实例
        self._llm_adapter = adapter
        return True

    async def test_model(self, model_type: str, config: dict) -> TestResult:
        """测试模型连接可用性，不切换"""
        adapter = self._create_adapter(model_type, config)
        ok = await adapter.health_check()
        return TestResult(success=ok, latency_ms=...)
```

### 4.4 兼容性检测

```python
class ModelCompatibilityChecker:
    @staticmethod
    async def check_llm_compatibility(adapter: LLMAdapter) -> dict:
        """检测 LLM 适配器的兼容性"""
        result = {"compatible": True, "issues": []}

        # 1. 测试 chat 能力
        try:
            resp = await adapter.chat(
                [ChatMessage(role="user", content="Hello")],
                max_tokens=10,
            )
            if not resp.content:
                result["issues"].append("chat 返回空内容")
        except Exception as e:
            result["issues"].append(f"chat 调用失败: {str(e)}")

        # 2. 测试 JSON 输出能力（对 Agent 管线至关重要）
        try:
            resp = await adapter.chat(
                [ChatMessage(role="user",
                  content="Return JSON: {\"key\": \"value\"}")],
                max_tokens=100,
            )
            json.loads(resp.content)
        except:
            result["issues"].append("不支持 JSON 格式输出")

        # 3. 测试 embed 能力
        try:
            await adapter.embed(["test"])
        except NotImplementedError:
            result["issues"].append("不支持 embed")  # 非致命

        if result["issues"]:
            result["compatible"] = False
        return result
```

---

## 5. 模型调用管理

### 5.1 调用日志记录

每次模型调用记录以下信息，写入 `model_call_log` 表：

```json
{
    "id": "mcl-xxxxxxxx",
    "timestamp": "2026-06-27T14:00:00Z",
    "adapter_type": "openai_compatible",
    "model_name": "gpt-4o",
    "agent_id": "story_analyzer",
    "task_id": "task-002",
    "call_type": "chat",
    "input_tokens": 3500,
    "output_tokens": 800,
    "total_tokens": 4300,
    "latency_ms": 2850,
    "status": "success",
    "error_message": null,
    "cost_usd": 0.0325
}
```

### 5.2 Token 消耗统计

| 维度 | 统计粒度 | 用途 |
|------|----------|------|
| 按 Agent | 每次调用 | Agent 级别的成本分析和优化 |
| 按项目 | 累计 | 项目成本核算 |
| 按时间 | 日/周/月 | 预算控制与趋势分析 |
| 按模型 | 累计 | 模型性价比评估 |

```python
class TokenUsageTracker:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def record_call(self, log: ModelCallLog):
        """记录一次模型调用"""
        # 1. 写入数据库持久化
        await self.db.save(log)

        # 2. 更新 Redis 实时计数
        today = date.today().isoformat()
        await self.redis.hincrby(
            f"token_usage:{today}",
            log.model_name,
            log.total_tokens,
        )

    async def get_daily_cost(self, date: str = None) -> dict:
        """获取指定日期的成本统计"""
        ...

    async def check_budget_alert(self) -> bool:
        """检查是否触发预算预警

        如果当日成本超过日均预算的 150%，触发告警
        """
        ...
```

### 5.3 调用频率控制

| 模型类型 | 频率限制策略 | 配置 |
|----------|-------------|------|
| LLM API | 令牌桶（Redis 实现） | 60 请求/分钟/模型 |
| 生图 API | 信号量 + 队列 | 最大并发 2-4 |
| Embedding API | 令牌桶 | 120 请求/分钟 |

```python
class RateLimiter:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def acquire(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """获取调用许可（基于滑动窗口）"""
        now = time.time()
        window_start = now - window_seconds

        # 移除窗口外的记录
        await self.redis.zremrangebyscore(key, 0, window_start)
        count = await self.redis.zcard(key)

        if count >= max_requests:
            return False  # 限流

        await self.redis.zadd(key, {now: now})
        await self.redis.expire(key, window_seconds)
        return True
```

### 5.4 自动降级策略

```python
class ModelFallbackManager:
    """模型降级管理器"""

    FALLBACK_CHAINS = {
        "gpt-4o": ["gpt-4-turbo", "deepseek-chat", "gpt-4o-mini"],
        "sd_xl": ["sd_3", "sd_1.5"],
        "midjourney": ["sd_xl", "sd_3"],
    }

    async def call_with_fallback(
        self,
        adapter: BaseAdapter,
        method: str,
        *args,
        **kwargs,
    ) -> Any:
        """调用模型，失败时自动降级"""
        errors = []

        for model_name in self._get_fallback_chain(adapter):
            try:
                # 切换模型
                if model_name != adapter.model_name:
                    await adapter.switch_model(model_name)

                # 调用
                result = await getattr(adapter, method)(*args, **kwargs)
                return result

            except Exception as e:
                errors.append({model_name: str(e)})
                continue

        raise AllModelsFailed(f"所有模型均失败: {errors}")
```

---

## 6. 模型配置管理

### 6.1 配置 CRUD

| 操作 | API 端点 | 说明 |
|------|----------|------|
| 列表 | `GET /api/v1/settings/llm-models` | 查看所有 LLM 模型配置 |
| 列表 | `GET /api/v1/settings/image-models` | 查看所有生图模型配置 |
| 新增 | `POST /api/v1/settings/llm-models` | 添加新的 LLM 模型 |
| 更新 | `PUT /api/v1/settings/llm-models/{id}` | 更新模型配置 |
| 删除 | `DELETE /api/v1/settings/llm-models/{id}` | 删除模型配置 |
| 测试 | `POST /api/v1/settings/llm-models/test` | 测试模型连接 |
| 切换 | `PUT /api/v1/settings/llm-models/active` | 设置当前活跃模型 |

### 6.2 参数预设管理

为常用生图场景提供参数预设：

```python
PARAMETER_PRESETS = {
    "webtoon_standard": {
        "description": "Webtoon 标准出图",
        "params": {
            "steps": 30,
            "cfg_scale": 7.5,
            "scheduler": "dpm++_2m_karras",
            "width": 1080,
            "height": 1440,
            "batch_size": 4,
        },
    },
    "webtoon_preview": {
        "description": "快速预览（低质量、速度快）",
        "params": {
            "steps": 15,
            "cfg_scale": 6.0,
            "scheduler": "euler_a",
            "width": 540,
            "height": 720,
            "batch_size": 4,
        },
    },
    "character_ref": {
        "description": "角色参考图生成（六视图）",
        "params": {
            "steps": 40,
            "cfg_scale": 8.0,
            "width": 1080,
            "height": 1440,
            "batch_size": 6,
        },
    },
}
```

### 6.3 模型配置存储

模型配置在数据库中加密存储：

```sql
CREATE TABLE model_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    adapter_type VARCHAR(50) NOT NULL,        -- "openai_compatible" | "sd_api" | ...
    model_name VARCHAR(255) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    api_base VARCHAR(1024) NOT NULL,
    api_key_encrypted TEXT NOT NULL,           -- AES-256-GCM 加密
    parameters JSONB NOT NULL DEFAULT '{}',
    capabilities JSONB NOT NULL DEFAULT '[]',  -- ["chat", "embed", ...]
    max_retries INT NOT NULL DEFAULT 3,
    timeout_seconds INT NOT NULL DEFAULT 120,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    priority INT NOT NULL DEFAULT 0,           -- 降级优先级
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_model_config_active ON model_config(is_active);
CREATE INDEX idx_model_config_type ON model_config(adapter_type);
```

### 6.4 模型测试验证

```python
class ModelTester:
    """模型连接测试工具"""

    @staticmethod
    async def test_llm_connection(config: dict) -> TestResult:
        """测试 LLM 连接"""
        try:
            adapter = OpenAICompatibleAdapter(config)
            start = time.time()
            ok = await adapter.health_check()
            latency = (time.time() - start) * 1000

            if ok:
                return TestResult(
                    success=True,
                    latency_ms=latency,
                    message="连接成功",
                )
            else:
                return TestResult(
                    success=False,
                    message="健康检查返回 False",
                )
        except Exception as e:
            return TestResult(
                success=False,
                message=f"连接失败: {str(e)}",
            )

    @staticmethod
    async def test_image_gen_connection(config: dict) -> TestResult:
        """测试生图模型连接"""
        try:
            adapter = SDAPIAdapter(config)
            start = time.time()
            models = await adapter.get_available_models()
            latency = (time.time() - start) * 1000

            return TestResult(
                success=True,
                latency_ms=latency,
                message=f"可用模型: {', '.join(models[:5])}" + \
                        ("..." if len(models) > 5 else ""),
                data={"models": models},
            )
        except Exception as e:
            return TestResult(
                success=False,
                message=f"连接失败: {str(e)}",
            )
```

---

## 7. Embedding 与视觉检测模型

### 7.1 Embedding 模型

| 适配器 | 模型 | 向量维度 | 用途 | 部署方式 |
|--------|------|----------|------|----------|
| OpenAIEmbedAdapter | `text-embedding-3-small` | 1536 | 通用语义搜索 | 云端 API |
| OpenAIEmbedAdapter | `text-embedding-3-large` | 3072 | 高精度语义匹配 | 云端 API |
| BGEEmbedAdapter | `BAAI/bge-large-zh-v1.5` | 1024 | 中文语义搜索 | 本地部署 |
| BGEEmbedAdapter | `BAAI/bge-m3` | 1024 | 多语言语义搜索 | 本地部署 |

**Embedding 在系统中的用途**：

1. **角色相似度搜索**：将角色特征描述向量化，按语义搜索匹配角色
2. **Prompt 模板推荐**：根据 Panel 内容语义，推荐最匹配的 Prompt 模板
3. **场景资产匹配**：Scene 描述与场景资产的语义匹配
4. **图片特征搜索**：已生成图片的语义检索（按内容搜图）

### 7.2 视觉检测模型

| 适配器 | 模型 | 用途 | 精度要求 |
|--------|------|------|----------|
| YOLOv8Adapter | YOLOv8x | 角色检测（面部、全身） | 高 |
| GroundingDINOAdapter | Grounding-DINO-L | 开放词汇目标检测（道具、场景元素） | 中 |
| PaddleOCROCRAdapter | PP-OCRv4 | 图片中文字识别（漏字检测） | 高 |
| ImageStyleAdapter | 基于 CLIP 的 style encoder | 画风一致性比对 | 中 |

**视觉检测管线**：

```
图片生成完成
    │
    ├──▶ YOLOv8 检测角色面部/身体
    │        │
    │        ▼
    │   面部特征提取（发色、瞳色、发型）
    │        │
    │        ▼
    │   与 IP 设定比对 → 一致性评分
    │
    ├──▶ PP-OCR 识别图片中的文字
    │        │
    │        ▼
    │   与原文比对 → 漏字检测报告
    │
    └──▶ CLIP 风格编码
             │
             ▼
         与画风模板比对 → 画风一致性评分
```

---

## 附录：适配器注册与工厂

```python
# 适配器注册表
ADAPTER_REGISTRY = {
    "llm": {
        "openai_compatible": OpenAICompatibleAdapter,
        "claude": ClaudeAdapter,
        "custom": CustomLLMAdapter,
    },
    "image_gen": {
        "sd_api": SDAPIAdapter,
        "midjourney": MidjourneyAdapter,
        "comfyui": ComfyUIAdapter,
        "dalle": DALLEAdapter,
        "custom": CustomImageGenAdapter,
    },
    "embedding": {
        "openai": OpenAIEmbedAdapter,
        "bge": BGEEmbedAdapter,
    },
    "vision": {
        "yolov8": YOLOv8Adapter,
        "grounding_dino": GroundingDINOAdapter,
        "paddle_ocr": PaddleOCROCRAdapter,
    },
}

class AdapterFactory:
    """适配器工厂，根据配置创建适配器实例"""

    @staticmethod
    def create(
        model_type: str,      # "llm" | "image_gen" | "embedding" | "vision"
        adapter_type: str,    # "openai_compatible" | "sd_api" | ...
        config: dict,
    ) -> BaseAdapter:
        """创建适配器实例"""
        adapter_class = ADAPTER_REGISTRY[model_type].get(adapter_type)
        if not adapter_class:
            raise AdapterNotFound(
                f"不支持的适配器类型: {model_type}/{adapter_type}"
            )
        return adapter_class(config)

    @staticmethod
    def get_supported_adapters(model_type: str) -> list[str]:
        """获取指定模型类型的所有支持的适配器"""
        return list(ADAPTER_REGISTRY.get(model_type, {}).keys())
```

---

*文档结束*
