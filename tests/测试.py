"""
模拟 AI API 服务 (Mock Server)
================================
支持多种故障注入场景，尽可能接近真实 LLM / 生图 API 的行为。
内置完备的请求统计：追踪各 API 的请求次数、成功/失败、重复请求。

支持的环境变量：
  MOCK_FAIL_RATE=0.1        # 全局请求失败概率 0.0 ~ 1.0，默认 0.1
  MOCK_TIMEOUT_MIN=3.5      # 最小响应延迟（秒），默认 3.5
  MOCK_TIMEOUT_MAX=300.0    # 最大响应延迟（秒），默认 300.0
  MOCK_API_KEY=sk-test      # 期望的 API Key（留空则不校验）
  MOCK_PORT=5000            # 监听端口

  MOCK_THINKING_ENABLED=1   # 是否模拟 AI 思考阶段（reasoning_content），默认 1
  MOCK_THINKING_MIN=1.0     # 思考阶段最短延迟（秒），默认 1.0
  MOCK_THINKING_MAX=5.0     # 思考阶段最长延迟（秒），默认 5.0
  MOCK_RATE_LIMIT=60        # 每分钟请求数限制（0 = 不限），默认 60
  MOCK_DEFAULT_MODEL=gpt-4o # 默认模型名，默认 gpt-4o
"""

import json
import re
import time
import uuid
import os
import random
import hashlib
import base64
import threading
from collections import defaultdict
from flask import Flask, request, Response, jsonify, send_from_directory

app = Flask(__name__)

# ============ 配置 ============
FAIL_RATE = float(os.environ.get("MOCK_FAIL_RATE", "0.1"))
TIMEOUT_MIN = float(os.environ.get("MOCK_TIMEOUT_MIN", "10.0"))
TIMEOUT_MAX = float(os.environ.get("MOCK_TIMEOUT_MAX", "15.0"))
EXPECTED_API_KEY = os.environ.get("MOCK_API_KEY", None)

# 思考/推理模拟
THINKING_ENABLED = os.environ.get("MOCK_THINKING_ENABLED", "1") == "1"
THINKING_MIN = float(os.environ.get("MOCK_THINKING_MIN", "30.0"))
THINKING_MAX = float(os.environ.get("MOCK_THINKING_MAX", "83.0"))

# 速率限制
RATE_LIMIT = int(os.environ.get("MOCK_RATE_LIMIT", "40"))

# 默认模型
DEFAULT_MODEL = os.environ.get("MOCK_DEFAULT_MODEL", "gpt-4o")

# 支持的模型列表
SUPPORTED_MODELS = [
    {"id": "gpt-4o", "object": "model", "created": 1700000000, "owned_by": "openai"},
    {"id": "gpt-4o-mini", "object": "model", "created": 1700000000, "owned_by": "openai"},
    {"id": "gpt-3.5-turbo", "object": "model", "created": 1700000000, "owned_by": "openai"},
    {"id": "deepseek-chat", "object": "model", "created": 1700000000, "owned_by": "deepseek"},
    {"id": "deepseek-reasoner", "object": "model", "created": 1700000000, "owned_by": "deepseek"},
]

# 判断模型是否为推理模型（会产生 thinking 内容）
def _is_reasoning_model(model: str) -> bool:
    """推理模型：deepseek-reasoner, o1*, o3* 等"""
    m = (model or "").lower()
    return ("deepseek-reasoner" in m or "o1" in m or "o3" in m or "r1" in m)

# ============ 加载映射数据 ============
def _load_json(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠ 未找到 {filename}")
        return {}

SHOT_PAGE_MAP = _load_json('shot_page_map.json')

# ============ 请求统计模块 ============
class RequestStats:
    """线程安全的请求统计器"""

    API_LABELS = {
        'chat': 'LLM 聊天补全',
        'image': '生图',
        'extract_roles': '① 角色提取',
        'split_script': '② 脚本拆分',
        'storyboard': '③ 分镜描述',
        'layout': '④ 页面排版',
        'image_prompt': '⑤ 生图提示词',
    }

    def __init__(self):
        self._lock = threading.Lock()
        # total / success / fail 按 API 类型分组
        self.total = defaultdict(int)
        self.success = defaultdict(int)
        self.fail = defaultdict(int)
        # 失败原因统计
        self.fail_reason = defaultdict(lambda: defaultdict(int))
        # 请求内容去重追踪：key = content_hash → (first_seen_success, count)
        self.content_first = {}  # hash → (api_type, first_success_time)
        self.content_count = defaultdict(int)  # hash → total request count
        self.extra_requests = 0  # 多请求计数（内容已成功过，但又被请求）

    def _content_hash(self, body: dict) -> str:
        """对请求体生成散列值用于去重"""
        raw = json.dumps(body, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(raw.encode('utf-8')).hexdigest()

    def _classify_chat(self, system_content: str) -> str:
        """根据 system prompt 判断 LLM 请求类型"""
        if "角色提取" in system_content:
            return 'extract_roles'
        if "单镜头文案" in system_content:
            return 'split_script'
        if "分镜描述" in system_content:
            return 'storyboard'
        if "Page Layout Planner" in system_content:
            return 'layout'
        if "分页分镜如" in system_content:
            return 'image_prompt'
        return 'chat'

    def record_request(self, body: dict, endpoint: str) -> str:
        """
        记录一次请求。
        endpoint: 'chat' 或 'image'
        返回分类后的 api_type。
        """
        api_type = endpoint
        if endpoint == 'chat':
            # 从 messages 中提取 system 内容判断类型
            msgs = body.get('messages', [])
            sys_content = ''
            for m in msgs:
                if m.get('role') == 'system':
                    sys_content = m.get('content', '')
                    break
            api_type = self._classify_chat(sys_content)

        content_hash = self._content_hash(body)

        with self._lock:
            self.total[api_type] += 1
            self.content_count[content_hash] += 1

            # 判断是否是重复请求
            if content_hash in self.content_first:
                # 这个请求内容已经见过（之前可能成功或失败过）
                first_success_time = self.content_first[content_hash][1]
                if first_success_time is not None:
                    # 之前已经成功过，这次是多余的
                    self.extra_requests += 1

        return api_type

    def record_success(self, api_type: str, body: dict):
        """记录一次成功响应"""
        content_hash = self._content_hash(body)
        with self._lock:
            self.success[api_type] += 1
            if content_hash not in self.content_first:
                self.content_first[content_hash] = (api_type, time.time())

    def record_fail(self, api_type: str, reason: str, body: dict):
        """记录一次失败响应"""
        content_hash = self._content_hash(body)
        with self._lock:
            self.fail[api_type] += 1
            self.fail_reason[api_type][reason] += 1
            # 失败不记录 content_first，下次重试不算"多请求"

    def summary(self) -> dict:
        """生成统计报告"""
        with self._lock:
            api_types = set(list(self.total.keys()) + list(self.success.keys()) + list(self.fail.keys()))
            details = {}
            grand_total = grand_success = grand_fail = 0
            for t in sorted(api_types):
                tot = self.total.get(t, 0)
                suc = self.success.get(t, 0)
                fal = self.fail.get(t, 0)
                label = self.API_LABELS.get(t, t)
                fail_reasons = dict(self.fail_reason.get(t, {}))
                details[label] = {
                    "total": tot,
                    "success": suc,
                    "fail": fal,
                    "fail_rate": round(fal / tot * 100, 1) if tot > 0 else 0,
                    "fail_reasons": fail_reasons,
                }
                grand_total += tot
                grand_success += suc
                grand_fail += fal

            # 多请求分析
            all_content = list(self.content_count.items())
            retry_after_fail = sum(1 for h, c in all_content
                                   if c > 1 and h not in self.content_first)
            extra = self.extra_requests

            return {
                "total_requests": grand_total,
                "total_success": grand_success,
                "total_fail": grand_fail,
                "total_fail_rate": round(grand_fail / grand_total * 100, 1) if grand_total > 0 else 0,
                "extra_requests_after_success": extra,
                "details": details,
                "note": {
                    "extra_requests_after_success": "内容已成功获取后又被重复请求的次数（真正的浪费）",
                    "retry_after_fail": "失败后重试次数（正常行为，非浪费）",
                }
            }


STATS = RequestStats()


# ============ 速率限制器（令牌桶） ============
class RateLimiter:
    """简单的每分钟请求数限制器"""

    def __init__(self, limit_per_min: int):
        self.limit = limit_per_min
        self._lock = threading.Lock()
        self._tokens = float(limit_per_min)
        self._last_refill = time.time()

    def _refill(self):
        now = time.time()
        elapsed = now - self._last_refill
        # 每秒补充 limit/60 个令牌
        self._tokens = min(self.limit, self._tokens + elapsed * (self.limit / 60.0))
        self._last_refill = now

    def acquire(self) -> bool:
        """尝试获取一个令牌。返回 True 表示允许，False 表示被限流。"""
        if self.limit <= 0:
            return True
        with self._lock:
            self._refill()
            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False

    def headers(self) -> dict:
        """生成 X-RateLimit-* 响应头"""
        if self.limit <= 0:
            return {}
        with self._lock:
            self._refill()
            remaining = int(self._tokens)
            reset_at = int(self._last_refill + 60)
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, remaining)),
            "X-RateLimit-Reset": str(reset_at),
        }


RATE_LIMITER = RateLimiter(RATE_LIMIT)


@app.after_request
def _add_rate_limit_headers(response):
    for k, v in RATE_LIMITER.headers().items():
        response.headers[k] = v
    return response


# ============ 统计查看端点 ============
@app.route('/__stats')
def show_stats():
    return jsonify(STATS.summary())


@app.route('/__stats/reset', methods=['POST'])
def reset_stats():
    global STATS
    STATS = RequestStats()
    return jsonify({"ok": True})


# ============ 故障注入工具 ============
def _maybe_fail():
    if FAIL_RATE > 0 and random.random() < FAIL_RATE:
        return True
    return False


def _random_delay():
    delay = random.uniform(TIMEOUT_MIN, TIMEOUT_MAX)
    time.sleep(delay)


def _check_auth():
    if EXPECTED_API_KEY is None:
        return None
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {EXPECTED_API_KEY}":
        return jsonify({
            "error": {
                "message": "Incorrect API key provided. You can find your API Key at https://platform.openai.com/account/api-keys.",
                "type": "invalid_request_error",
                "param": None,
                "code": "invalid_api_key"
            }
        }), 401
    return None


# ============ Token 计数（近似） ============
def _count_tokens(text: str) -> int:
    """近似 token 计数：中文 ~1.5 token/字，英文 ~1.3 token/词"""
    if not text:
        return 0
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    other_chars = len(text) - chinese_chars
    # 中文约 1.5 token/字，英文约 4 字符/token
    return int(chinese_chars * 1.5 + other_chars / 4)


def _count_message_tokens(messages: list) -> int:
    """计算 messages 数组的总 prompt token 数"""
    total = 3  # 基础开销
    for msg in messages:
        total += 4  # role + content 标记
        content = msg.get('content', '')
        if isinstance(content, str):
            total += _count_tokens(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    total += _count_tokens(part.get('text', ''))
    return total


# ============ 思考/推理内容生成 ============
_THINKING_TEMPLATES = {
    'extract_roles': [
        "让我分析这段小说文本...\n首先识别主要角色，通过对话和叙述判断角色身份。\n提取角色的外貌、性格、关系等信息。\n检查是否有遗漏的配角。\n整理为结构化输出。",
        "开始角色提取...\n扫描文本中的所有人名和称呼。\n分析每个角色的出场频率和重要性。\n构建角色关系图。\n格式化输出结果。",
    ],
    'split_script': [
        "分析剧本结构...\n识别场景边界，按自然段落拆分。\n为每个镜头提取对话、动作、场景描述。\n确保不遗漏任何细节。\n输出结构化镜头列表。",
        "开始脚本拆分...\n按物理段落结构分割文本。\n为每段标注场景类型（对话/旁白/动作）。\n提取关键信息。\n生成单镜头文案。",
    ],
    'storyboard': [
        "理解章节内容...\n为每个镜头设计画面构图。\n确定镜头角度和景别。\n考虑角色站位和动作。\n生成专业分镜描述。",
        "开始分镜描述生成...\n分析镜头内容...\n设计视觉呈现方式...\n优化描述细节...\n输出分镜方案。",
    ],
    'layout': [
        "分析章节镜头数量...\n规划页面布局，每页 4-6 个镜头。\n考虑阅读节奏和视觉流畅性。\n平衡对话量和画面留白。\n生成排版方案。",
        "开始页面排版...\n统计镜头总数...\n分配镜头到各页面...\n优化布局结构...\n输出排版结果。",
    ],
    'image_prompt': [
        "分析分镜内容...\n提取关键视觉元素。\n构建生图提示词，包含风格、角色、场景。\n优化提示词以获得最佳生成效果。\n输出提示词列表。",
        "开始提示词生成...\n解析镜头信息...\n识别角色和场景元素...\n构建详细提示词...\n输出结果。",
    ],
    'chat': [
        "分析用户请求...\n理解问题意图...\n检索相关知识...\n组织回答结构...\n生成最终回复。",
        "思考中...\n解析输入内容...\n构建推理链条...\n验证逻辑合理性...\n准备输出。",
    ],
}


def _generate_thinking(api_type: str, user_content: str) -> str:
    """根据 API 类型和用户内容生成思考文本"""
    templates = _THINKING_TEMPLATES.get(api_type, _THINKING_TEMPLATES['chat'])
    base = random.choice(templates)
    # 根据内容长度附加更多思考
    content_len = len(user_content or '')
    if content_len > 2000:
        base += "\n内容较长，需要仔细处理每个部分..."
    elif content_len > 500:
        base += "\n逐步处理内容..."
    return base


def _thinking_delay(user_content: str) -> float:
    """根据内容长度计算思考延迟"""
    base = random.uniform(THINKING_MIN, THINKING_MAX)
    # 内容越长，思考越久（每 1000 字多 0.5s，上限 +10s）
    extra = min(len(user_content or '') / 1000 * 0.5, 10.0)
    return base + extra


# ============ 故障注入路由 ============
@app.route('/__inject/fail', methods=['POST'])
def inject_fail():
    body = request.get_json() or {}
    app.config['_ONE_SHOT_FAIL'] = body.get('type', 'timeout')
    return jsonify({"ok": True, "next_fail": app.config.get('_ONE_SHOT_FAIL')})


def _check_one_shot_fail():
    fail_type = app.config.pop('_ONE_SHOT_FAIL', None)
    if fail_type is None:
        return None
    if fail_type == 'timeout':
        time.sleep(120)
        return jsonify({"error": "timeout"}), 504
    elif fail_type == 'non_json':
        return Response("Internal Server Error", status=500, content_type='text/plain')
    elif fail_type == 'empty':
        return Response("", status=200)
    elif fail_type == 'malformed_json':
        return jsonify({"choices": [{"message": {"role": "assistant"}}]})
    elif fail_type == 'http_429':
        return jsonify({"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}}), 429
    elif fail_type == 'http_503':
        return jsonify({"error": {"message": "Service Unavailable", "type": "server_error"}}), 503
    return None


# ============ 规则匹配函数 ============
def get_response(system_content, user_content):
    """根据 system 和 user 消息内容匹配规则，返回对应的响应文本。"""
    # 规则1: 角色提取
    if ("你是一位专业的小说角色提取专家" in system_content and
        "我是京圈太子爷身边唯一的金丝雀" in user_content):
        with open('角色.json', 'r', encoding='utf-8') as f:
            return f.read()

    # 规则2: 脚本拆分
    if ("你的任务是将我提供的剧本文本，严格按照文本的物理结构（自然段落或序号），拆分并整理为独立的\"单镜头文案\"" in system_content and
        "我是京圈太子爷身边唯一的金丝雀" in user_content):
        with open('脚本.json', 'r', encoding='utf-8') as f:
            return f.read()

    # 规则3: 分镜描述
    if "你的任务是根据我提供的单个章节的脚本数据，为每个镜头生成专业、详细的分镜描述" in system_content:
        match = re.search(r'"chapterTitle"\s*:\s*"([^"]+)"', user_content)
        if match:
            chapter = match.group(1)
            data = _load_json('分镜.json')
            result = data.get(chapter, f"未找到章节 '{chapter}' 的数据")
            return json.dumps(result, ensure_ascii=False)

    # 规则4: 页面排版
    if "Page Layout Planner" in system_content:
        match = re.search(r'"chapterTitle"\s*:\s*"([^"]+)"', user_content)
        if match:
            chapter = match.group(1)
            data = _load_json('排版.json')
            result = data.get(chapter, f"未找到章节 '{chapter}' 的数据")
            return json.dumps(result, ensure_ascii=False)

    # 规则5: 生图提示词
    if "根据提供的分页分镜如" in system_content:
        try:
            user_data = json.loads(user_content)
            current_page = user_data.get('currentPage')
            if not current_page:
                return json.dumps({"error": "Missing currentPage"}, ensure_ascii=False)
            shots = current_page.get('shots', [])
            if not shots:
                return json.dumps({"shots": []}, ensure_ascii=False)
            prompt_data = _load_json('提示词.json')
            new_shots = []
            for shot in shots:
                shot_id = shot.get('shotId')
                prompt_value = prompt_data.get(shot_id)
                if isinstance(prompt_value, dict):
                    image_prompt = prompt_value.get('imagePrompt', '')
                else:
                    image_prompt = prompt_value if prompt_value is not None else ''
                new_shots.append({"pageId": current_page.get('pageId'), "imagePrompt": image_prompt})
            return json.dumps({"shots": new_shots}, ensure_ascii=False)
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid user content: {str(e)}"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    return "未匹配到规则，请检查 system 和 user 消息内容。"


# ============ 流式生成器 ============
def generate_stream(content, model='gpt-4o', thinking_content=None,
                    prompt_tokens=0, include_usage=False):
    """
    生成 SSE 流式响应。
    - thinking_content: 推理模型的思考内容（先于 content 输出，放在 reasoning_content 字段）
    - include_usage: 是否在最后一个 chunk 附带 usage 统计
    """
    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    def _chunk(delta, finish_reason=None, usage=None):
        payload = {
            'id': chunk_id,
            'object': 'chat.completion.chunk',
            'created': created,
            'model': model,
            'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish_reason}],
        }
        if usage is not None:
            payload['usage'] = usage
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    # 1. 初始 role chunk
    yield _chunk({'role': 'assistant'})

    # 2. 思考/推理阶段（reasoning_content）
    if thinking_content:
        # 模拟思考延迟
        delay = random.uniform(THINKING_MIN, min(THINKING_MAX, THINKING_MIN + 2))
        time.sleep(delay)
        # 按句号/换行分段输出思考内容
        parts = re.split(r'(\n)', thinking_content)
        for part in parts:
            if part:
                yield _chunk({'reasoning_content': part})

    # 3. 正式内容
    completion_tokens = 0
    for i in range(0, len(content), 10):
        part = content[i:i+10]
        completion_tokens += _count_tokens(part)
        yield _chunk({'content': part})

    # 4. 结束 chunk
    completion_tokens = max(completion_tokens, _count_tokens(content))
    usage = None
    if include_usage:
        usage = {
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': prompt_tokens + completion_tokens,
        }
    yield _chunk({}, finish_reason='stop', usage=usage)

    yield "data: [DONE]\n\n"


# ============ 模拟生图 API ============
@app.route('/v1/api/generate', methods=['POST'])
def generate_image():
    auth_err = _check_auth()
    if auth_err:
        return auth_err

    # 速率限制
    if not RATE_LIMITER.acquire():
        return jsonify({"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}}), 429

    req_data = request.get_json() or {}
    api_type = STATS.record_request(req_data, 'image')

    one_shot = _check_one_shot_fail()
    if one_shot:
        STATS.record_fail(api_type, 'one_shot_injection', req_data)
        return one_shot

    if _maybe_fail():
        fail_type = random.choice(['timeout', 'http_500', 'http_429', 'non_json', 'empty_result'])
        STATS.record_fail(api_type, fail_type, req_data)
        if fail_type == 'timeout':
            time.sleep(120)
            return jsonify({"error": "timeout"}), 504
        elif fail_type == 'http_500':
            return jsonify({"error": "Internal server error"}), 500
        elif fail_type == 'http_429':
            return jsonify({"error": {"message": "Rate limit exceeded"}}), 429
        elif fail_type == 'non_json':
            return Response("Service Unavailable", status=503, content_type='text/html')
        elif fail_type == 'empty_result':
            return jsonify({"id": f"7-{uuid.uuid4().hex[:24]}", "status": "failed", "results": []})

    _random_delay()

    prompt = req_data.get('prompt', '')
    n = min(req_data.get('n', 1), 4)  # 最多 4 张
    size = req_data.get('size', '1024x1024')
    response_format = req_data.get('response_format', 'url')  # 'url' 或 'b64_json'
    model = req_data.get('model', 'dall-e-3')

    # 根据 prompt 选择图片文件
    filename = None
    if prompt.startswith('徐婉'):
        filename = '徐婉.png'
    elif prompt.startswith('周停'):
        filename = '周停.png'
    else:
        match = re.search(r'【shotId】[：:]\s*(\d+)', prompt)
        if match:
            shot_id = match.group(1).zfill(2)
            page_id = SHOT_PAGE_MAP.get(shot_id)
            filename = f"{page_id}.png" if page_id else 'default.png'
        else:
            filename = 'default.png'

    base_url = request.host_url.rstrip('/')
    response_id = f"7-{uuid.uuid4().hex[:24]}"

    results = []
    for i in range(n):
        if response_format == 'b64_json':
            # 返回 base64 编码的图片（用占位图）
            try:
                img_path = os.path.join(os.path.dirname(__file__), 'img', filename)
                with open(img_path, 'rb') as f:
                    b64 = base64.b64encode(f.read()).decode('utf-8')
                results.append({"b64_json": b64, "revised_prompt": prompt})
            except FileNotFoundError:
                # 文件不存在时返回 1x1 透明 PNG 的 base64
                results.append({"b64_json": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==", "revised_prompt": prompt})
        else:
            image_url = f"{base_url}/images/{filename}"
            results.append({"url": image_url, "revised_prompt": prompt})

    result = {
        "id": response_id,
        "model": model,
        "status": "succeeded",
        "results": results,
        "progress": 100,
        "size": size,
    }

    STATS.record_success(api_type, req_data)
    return jsonify(result)


@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory('img', filename)


# ============ OpenAI 兼容聊天补全端点 ============
@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    auth_err = _check_auth()
    if auth_err:
        return auth_err

    # 速率限制
    if not RATE_LIMITER.acquire():
        return jsonify({"error": {"message": "Rate limit exceeded. Please try again later.", "type": "rate_limit_error", "code": "rate_limit_exceeded"}}), 429

    req_data = request.get_json() or {}
    api_type = STATS.record_request(req_data, 'chat')

    one_shot = _check_one_shot_fail()
    if one_shot:
        STATS.record_fail(api_type, 'one_shot_injection', req_data)
        return one_shot

    if _maybe_fail():
        fail_type = random.choice([
            'timeout', 'http_500', 'http_429', 'http_503',
            'non_json', 'malformed_json', 'empty_content',
        ])
        STATS.record_fail(api_type, fail_type, req_data)
        if fail_type == 'timeout':
            time.sleep(120)
            return jsonify({"error": "timeout"}), 504
        elif fail_type == 'http_500':
            return jsonify({"error": "Internal server error"}), 500
        elif fail_type == 'http_429':
            return jsonify({"error": {"message": "Rate limit exceeded. Please try again later.", "type": "rate_limit_error", "code": "rate_limit_exceeded"}}), 429
        elif fail_type == 'http_503':
            return jsonify({"error": {"message": "The server is currently overloaded.", "type": "server_error", "code": "service_unavailable"}}), 503
        elif fail_type == 'non_json':
            return Response("<html><body><h1>502 Bad Gateway</h1></body></html>", status=502, content_type='text/html')
        elif fail_type == 'malformed_json':
            return jsonify({"choices": [{"index": 0, "message": {"role": "assistant"}}]})
        elif fail_type == 'empty_content':
            return jsonify({"id": f"chatcmpl-{uuid.uuid4().hex[:24]}", "object": "chat.completion", "created": int(time.time()), "model": req_data.get('model', DEFAULT_MODEL), "choices": [{"index": 0, "message": {"role": "assistant", "content": "{}"}, "finish_reason": "stop"}]})

    _random_delay()

    messages = req_data.get('messages', [])
    stream = req_data.get('stream', False)
    model = req_data.get('model', DEFAULT_MODEL)
    max_tokens = req_data.get('max_tokens', 0)  # 0 = 不限制

    # stream_options.include_usage
    stream_options = req_data.get('stream_options', {})
    include_usage = stream_options.get('include_usage', False) if isinstance(stream_options, dict) else False

    # 提取 system / user 内容
    system_content = None
    user_content = None
    for msg in messages:
        role = msg.get('role')
        if role == 'system':
            system_content = msg.get('content')
        elif role == 'user':
            user_content = msg.get('content')

    if system_content is None or user_content is None:
        STATS.record_fail(api_type, 'missing_messages', req_data)
        return jsonify({"error": "Missing system or user message"}), 400

    response_text = get_response(system_content, user_content)

    # max_tokens 截断
    finish_reason = 'stop'
    if max_tokens and max_tokens > 0:
        response_token_count = _count_tokens(response_text)
        if response_token_count > max_tokens:
            # 按比例截断
            ratio = max_tokens / response_token_count
            cut_len = int(len(response_text) * ratio)
            response_text = response_text[:cut_len]
            finish_reason = 'length'

    # 计算思考内容
    thinking_content = None
    if THINKING_ENABLED:
        # 推理模型始终产生 thinking；非推理模型有概率产生
        is_reasoning = _is_reasoning_model(model)
        if is_reasoning or random.random() < 0.3:
            thinking_content = _generate_thinking(api_type, user_content)

    # 计算 token 使用量
    prompt_tokens = _count_message_tokens(messages)
    completion_tokens = _count_tokens(response_text)
    if thinking_content:
        completion_tokens += _count_tokens(thinking_content)

    usage = {
        'prompt_tokens': prompt_tokens,
        'completion_tokens': completion_tokens,
        'total_tokens': prompt_tokens + completion_tokens,
    }
    if thinking_content:
        usage['completion_tokens_details'] = {'reasoning_tokens': _count_tokens(thinking_content)}

    if stream:
        STATS.record_success(api_type, req_data)
        return Response(
            generate_stream(
                response_text, model=model,
                thinking_content=thinking_content,
                prompt_tokens=prompt_tokens,
                include_usage=include_usage,
            ),
            mimetype='text/event-stream',
        )
    else:
        message = {"role": "assistant", "content": response_text}
        # DeepSeek 风格：非流式响应中包含 reasoning_content
        if thinking_content:
            message["reasoning_content"] = thinking_content

        resp = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
            "usage": usage,
        }
        STATS.record_success(api_type, req_data)
        return jsonify(resp)


# ============ 模型列表端点 ============
@app.route('/v1/models', methods=['GET'])
def list_models():
    auth_err = _check_auth()
    if auth_err:
        return auth_err
    return jsonify({"object": "list", "data": SUPPORTED_MODELS})


@app.route('/v1/models/<model_id>', methods=['GET'])
def get_model(model_id):
    auth_err = _check_auth()
    if auth_err:
        return auth_err
    for m in SUPPORTED_MODELS:
        if m['id'] == model_id:
            return jsonify(m)
    return jsonify({"error": {"message": f"The model '{model_id}' does not exist", "type": "invalid_request_error", "code": "model_not_found"}}), 404


# ============ Embeddings 端点 ============
@app.route('/v1/embeddings', methods=['POST'])
def create_embedding():
    auth_err = _check_auth()
    if auth_err:
        return auth_err

    if not RATE_LIMITER.acquire():
        return jsonify({"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}}), 429

    req_data = request.get_json() or {}
    api_type = STATS.record_request(req_data, 'chat')  # 归入 chat 统计

    _random_delay()

    input_text = req_data.get('input', '')
    model = req_data.get('model', 'text-embedding-3-small')
    encoding_format = req_data.get('encoding_format', 'float')  # 'float' 或 'base64'

    if isinstance(input_text, str):
        inputs = [input_text]
    elif isinstance(input_text, list):
        inputs = input_text
    else:
        return jsonify({"error": "Invalid input"}), 400

    embeddings = []
    for text in inputs:
        # 基于文本内容生成稳定的伪随机向量（同一文本总是返回同一向量）
        seed = int(hashlib.md5(text.encode('utf-8')).hexdigest()[:8], 16)
        rng = random.Random(seed)
        dim = 1536
        vec = [rng.uniform(-1, 1) for _ in range(dim)]
        # 归一化
        norm = sum(v * v for v in vec) ** 0.5
        vec = [v / norm for v in vec]

        if encoding_format == 'base64':
            import struct
            b = b''.join(struct.pack('f', v) for v in vec)
            vec_data = base64.b64encode(b).decode('utf-8')
        else:
            vec_data = vec

        embeddings.append({
            "object": "embedding",
            "index": len(embeddings),
            "embedding": vec_data,
        })

    prompt_tokens = sum(_count_tokens(t) for t in inputs)
    resp = {
        "object": "list",
        "data": embeddings,
        "model": model,
        "usage": {"prompt_tokens": prompt_tokens, "total_tokens": prompt_tokens},
    }
    STATS.record_success(api_type, req_data)
    return jsonify(resp)


# ============ 健康检查 / 配置 ============
@app.route('/')
def index():
    return jsonify({
        "status": "running",
        "mock_fail_rate": FAIL_RATE,
        "mock_timeout_range": [TIMEOUT_MIN, TIMEOUT_MAX],
        "mock_api_key_required": EXPECTED_API_KEY is not None,
        "mock_thinking_enabled": THINKING_ENABLED,
        "mock_rate_limit": RATE_LIMIT,
        "endpoints": {
            "chat": "POST /v1/chat/completions",
            "images": "POST /v1/images/generations",
            "models": "GET /v1/models",
            "embeddings": "POST /v1/embeddings",
            "stats": "GET /__stats",
            "inject_fail": "POST /__inject/fail",
            "config": "GET /__config",
        },
    })


@app.route('/__config')
def show_config():
    return jsonify({
        "FAIL_RATE": FAIL_RATE,
        "TIMEOUT_MIN": TIMEOUT_MIN,
        "TIMEOUT_MAX": TIMEOUT_MAX,
        "EXPECTED_API_KEY": EXPECTED_API_KEY,
        "THINKING_ENABLED": THINKING_ENABLED,
        "THINKING_MIN": THINKING_MIN,
        "THINKING_MAX": THINKING_MAX,
        "RATE_LIMIT": RATE_LIMIT,
        "DEFAULT_MODEL": DEFAULT_MODEL,
        "SUPPORTED_MODELS": [m["id"] for m in SUPPORTED_MODELS],
    })


if __name__ == '__main__':
    port = int(os.environ.get("MOCK_PORT", "5000"))
    print(f"🚀 Mock AI API 启动在 http://0.0.0.0:{port}")
    print(f"   故障率: {FAIL_RATE} | 延迟: {TIMEOUT_MIN}s ~ {TIMEOUT_MAX}s")
    print(f"   思考模拟: {'开启' if THINKING_ENABLED else '关闭'} | 延迟: {THINKING_MIN}s ~ {THINKING_MAX}s")
    print(f"   速率限制: {RATE_LIMIT if RATE_LIMIT > 0 else '无限制'} req/min")
    if EXPECTED_API_KEY:
        print(f"   API Key 校验: Bearer {EXPECTED_API_KEY}")
    else:
        print(f"   API Key 校验: 关闭")
    print(f"   支持模型: {[m['id'] for m in SUPPORTED_MODELS]}")
    print(f"   统计端点: GET /__stats")
    print(f"   注入端点: POST /__inject/fail")
    print(f"   配置端点: GET /__config")
    app.run(debug=False, host='127.0.0.1', port=port)
