"""
模拟 AI API 服务 (Mock Server)
================================
支持多种故障注入场景，尽可能接近真实 LLM / 生图 API 的行为。
内置完备的请求统计：追踪各 API 的请求次数、成功/失败、重复请求。

支持的环境变量：
  MOCK_FAIL_RATE=0.3        # 全局请求失败概率 0.0 ~ 1.0，默认 0.0
  MOCK_TIMEOUT_MIN=2        # 最小响应延迟（秒），默认 0.5
  MOCK_TIMEOUT_MAX=8        # 最大响应延迟（秒），默认 2.0
  MOCK_API_KEY=sk-test      # 期望的 API Key
  MOCK_PORT=5000            # 监听端口
"""

import json
import re
import time
import uuid
import os
import random
import hashlib
import threading
from collections import defaultdict
from flask import Flask, request, Response, jsonify, send_from_directory

app = Flask(__name__)

# ============ 配置 ============
FAIL_RATE = float(os.environ.get("MOCK_FAIL_RATE", "0.1"))
TIMEOUT_MIN = float(os.environ.get("MOCK_TIMEOUT_MIN", "3.5"))
TIMEOUT_MAX = float(os.environ.get("MOCK_TIMEOUT_MAX", "300.0"))
EXPECTED_API_KEY = os.environ.get("MOCK_API_KEY", None)

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
def generate_stream(content):
    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    yield f"data: {json.dumps({'id': chunk_id, 'object': 'chat.completion.chunk', 'created': created, 'model': 'gpt-3.5-turbo', 'choices': [{'index': 0, 'delta': {'role': 'assistant'}, 'finish_reason': None}]}, ensure_ascii=False)}\n\n"
    for i in range(0, len(content), 10):
        part = content[i:i+10]
        yield f"data: {json.dumps({'id': chunk_id, 'object': 'chat.completion.chunk', 'created': created, 'model': 'gpt-3.5-turbo', 'choices': [{'index': 0, 'delta': {'content': part}, 'finish_reason': None}]}, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps({'id': chunk_id, 'object': 'chat.completion.chunk', 'created': created, 'model': 'gpt-3.5-turbo', 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


# ============ 模拟生图 API ============
@app.route('/v1/images/generations', methods=['POST'])
def generate_image():
    auth_err = _check_auth()
    if auth_err:
        return auth_err

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
    image_url = f"{base_url}/images/{filename}"
    response_id = f"7-{uuid.uuid4().hex[:24]}"
    result = {"id": response_id, "status": "succeeded", "results": [{"url": image_url}], "progress": 100}

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
            return jsonify({"id": f"chatcmpl-{uuid.uuid4().hex[:24]}", "object": "chat.completion", "created": int(time.time()), "model": "gpt-3.5-turbo", "choices": [{"index": 0, "message": {"role": "assistant", "content": "{}"}, "finish_reason": "stop"}]})

    _random_delay()

    messages = req_data.get('messages', [])
    stream = req_data.get('stream', False)
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

    if stream:
        STATS.record_success(api_type, req_data)
        return Response(generate_stream(response_text), mimetype='text/event-stream')
    else:
        resp = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "gpt-3.5-turbo",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": response_text}, "finish_reason": "stop"}]
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
    })


@app.route('/__config')
def show_config():
    return jsonify({
        "FAIL_RATE": FAIL_RATE,
        "TIMEOUT_MIN": TIMEOUT_MIN,
        "TIMEOUT_MAX": TIMEOUT_MAX,
        "EXPECTED_API_KEY": EXPECTED_API_KEY,
    })


if __name__ == '__main__':
    port = int(os.environ.get("MOCK_PORT", "5000"))
    print(f"🚀 Mock AI API 启动在 http://0.0.0.0:{port}")
    print(f"   故障率: {FAIL_RATE} | 延迟: {TIMEOUT_MIN}s ~ {TIMEOUT_MAX}s")
    if EXPECTED_API_KEY:
        print(f"   API Key 校验: Bearer {EXPECTED_API_KEY}")
    else:
        print(f"   API Key 校验: 关闭")
    print(f"   统计端点: GET /__stats")
    print(f"   注入端点: POST /__inject/fail")
    app.run(debug=False, host='0.0.0.0', port=port)
