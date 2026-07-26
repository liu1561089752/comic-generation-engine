"""
Flow API 桥接服务（OpenAI 兼容版）

油猴脚本在浏览器中运行，通过轮询这个桥接服务接收任务。
其他项目通过 OpenAI 兼容接口调用。

启动:
    uvicorn flow_api_bridge:app --host 0.0.0.0 --port 8567 --reload

然后在油猴面板点击 "🔗 启动桥接模式"。

其他项目调用（OpenAI SDK 兼容）:
    from openai import OpenAI
    client = OpenAI(base_url="http://localhost:8567/v1", api_key="sk-flow")
    resp = client.images.generate(model="nano_banana_pro", prompt="一只猫", size="1:1")
"""

import json
import uuid
import time
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

HOST = "0.0.0.0"
PORT = 8567

VALID_API_KEYS = {"sk-flow", "sk-123456"}

MODEL_MAPPING = {
    "nano_banana_pro": "GEM_PIX_2",
    "nano_banana_2": "NARWHAL",
    "nano_banana_2_lite": "HARBOR_SEAL",
}

MODEL_KEY_MAP = {}
for client_model, flow_model in MODEL_MAPPING.items():
    MODEL_KEY_MAP[client_model] = flow_model


def parse_aspect_ratio(size_str):
    if not size_str:
        return "IMAGE_ASPECT_RATIO_SQUARE"
    s = str(size_str).strip().lower()

    KNOWN = {
        "1:1":      "IMAGE_ASPECT_RATIO_SQUARE",
        "3:4":      "IMAGE_ASPECT_RATIO_PORTRAIT_THREE_FOUR",
        "4:3":      "IMAGE_ASPECT_RATIO_LANDSCAPE_FOUR_THREE",
        "9:16":     "IMAGE_ASPECT_RATIO_PORTRAIT",
        "16:9":     "IMAGE_ASPECT_RATIO_LANDSCAPE",
        "square":   "IMAGE_ASPECT_RATIO_SQUARE",
        "portrait": "IMAGE_ASPECT_RATIO_PORTRAIT",
        "landscape":"IMAGE_ASPECT_RATIO_LANDSCAPE",
        "1024x1024":"IMAGE_ASPECT_RATIO_SQUARE",
        "768x1024": "IMAGE_ASPECT_RATIO_PORTRAIT_THREE_FOUR",
        "1024x768": "IMAGE_ASPECT_RATIO_LANDSCAPE_FOUR_THREE",
        "768x1366": "IMAGE_ASPECT_RATIO_PORTRAIT",
        "1366x768": "IMAGE_ASPECT_RATIO_LANDSCAPE",
    }
    return KNOWN.get(s, "IMAGE_ASPECT_RATIO_SQUARE")


def verify_api_key(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Invalid API Key",
                    "type": "invalid_request_error",
                    "param": None,
                    "code": "invalid_api_key"
                }
            }
        )
    api_key = auth[7:]
    if api_key not in VALID_API_KEYS:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Invalid API Key",
                    "type": "invalid_request_error",
                    "param": None,
                    "code": "invalid_api_key"
                }
            }
        )


_pending_tasks: Dict[str, Dict[str, Any]] = {}
_completed_tasks: Dict[str, Dict[str, Any]] = {}
_task_events: Dict[str, asyncio.Event] = {}
_next_poll_id = 0

MAX_COMPLETED = 100
WAIT_TIMEOUT = 120

_stats = {"total": 0, "success": 0, "failure": 0}


app = FastAPI(title="Flow API Bridge", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail,
    )


async def cleanup_expired_tasks():
    while True:
        await asyncio.sleep(60)
        now = time.time()
        expired_pending = []
        for tid, task in _pending_tasks.items():
            if task["status"] in ("timeout", "error"):
                expired_pending.append(tid)
            elif task["status"] == "processing" and now - task.get("_start_time", 0) > 300:
                expired_pending.append(tid)
                logger.warning(f"Task {tid} processing for too long, marking as timeout")

        for tid in expired_pending:
            _pending_tasks.pop(tid, None)
            _task_events.pop(tid, None)

        if len(_completed_tasks) > MAX_COMPLETED:
            keys = sorted(_completed_tasks.keys(), key=lambda k: _completed_tasks[k].get("_time", 0))
            for k in keys[:len(keys) - MAX_COMPLETED]:
                _completed_tasks.pop(k, None)


@app.on_event("startup")
async def startup():
    asyncio.create_task(cleanup_expired_tasks())
    logger.info(f"🚀 Flow API 桥接服务启动: http://{HOST}:{PORT}")
    logger.info(f"📌 OpenAI 兼容接口: POST http://localhost:{PORT}/v1/images/generations")
    logger.info(f"📌 原生接口: POST http://localhost:{PORT}/generate")
    logger.info(f"📌 桥接状态: http://localhost:{PORT}/health")


@app.post("/v1/images/generations")
async def generate_image(request: Request):
    verify_api_key(request)

    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "message": "Invalid JSON body",
                    "type": "invalid_request_error",
                    "param": None,
                    "code": "invalid_json"
                }
            }
        )

    prompt = body.get("prompt", "")
    if not prompt:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "message": "You must provide a prompt",
                    "type": "invalid_request_error",
                    "param": "prompt",
                    "code": "missing_prompt"
                }
            }
        )

    if isinstance(prompt, list):
        prompt = " ".join(p.get("text", "") for p in prompt)

    model_input_raw = body.get("model", "GEM_PIX_2")
    model_key = MODEL_KEY_MAP.get(model_input_raw.lower() if model_input_raw else "GEM_PIX_2", "GEM_PIX_2")

    n = body.get("n", 1)
    if not (1 <= n <= 10):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "message": "n must be between 1 and 10",
                    "type": "invalid_request_error",
                    "param": "n",
                    "code": "invalid_n"
                }
            }
        )

    size = body.get("size", "1024x1024")
    aspect_ratio = parse_aspect_ratio(size)

    response_format = body.get("response_format", "url")
    if response_format not in ("url", "b64_json"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "message": "response_format must be 'url' or 'b64_json'",
                    "type": "invalid_request_error",
                    "param": "response_format",
                    "code": "invalid_response_format"
                }
            }
        )

    # 归一化 image_base64 为数组
    image_base64_raw = body.get("image_base64")
    if image_base64_raw is None:
        images_base64 = []
    elif isinstance(image_base64_raw, list):
        images_base64 = image_base64_raw
    else:
        images_base64 = [image_base64_raw]

    image_mime_raw = body.get("image_mime_type", "image/png")
    if isinstance(image_mime_raw, list):
        images_mime = image_mime_raw
    else:
        images_mime = [image_mime_raw] * len(images_base64)

    task_id = str(uuid.uuid4())[:8]

    _stats["total"] += 1
    _pending_tasks[task_id] = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "model": model_key,
        "seed": body.get("seed"),
        "n": n,
        "response_format": response_format,
        "user": body.get("user"),
        "images_base64": images_base64,
        "images_mime_type": images_mime,
        "status": "pending",
        "result": None,
        "_start_time": time.time(),
    }

    event = asyncio.Event()
    _task_events[task_id] = event

    logger.info(f"Task {task_id} created: model={model_key}, prompt={prompt[:50]}...")

    try:
        await asyncio.wait_for(event.wait(), timeout=WAIT_TIMEOUT)
    except asyncio.TimeoutError:
        _pending_tasks[task_id]["status"] = "timeout"
        _stats["failure"] += 1
        _task_events.pop(task_id, None)
        logger.error(f"Task {task_id} timed out after {WAIT_TIMEOUT}s")
        raise HTTPException(
            status_code=504,
            detail={
                "error": {
                    "message": f"task {task_id} timed out after {WAIT_TIMEOUT}s",
                    "type": "server_error",
                    "param": None,
                    "code": "timeout"
                }
            }
        )

    completed = _completed_tasks.get(task_id)
    _task_events.pop(task_id, None)

    if completed and completed.get("success"):
        images = []
        meta_list = completed.get("image_meta", [])
        urls = completed.get("images", [])
        for i, url in enumerate(urls):
            entry = {
                "url": url if response_format == "url" else None,
                "b64_json": None,
                "revised_prompt": "",
            }
            if i < len(meta_list) and meta_list[i].get("mediaId"):
                entry["media_id"] = meta_list[i]["mediaId"]
            images.append(entry)
        logger.info(f"Task {task_id} completed successfully: {len(images)} images")
        return {
            "created": int(time.time()),
            "data": images,
        }
    else:
        completed_data = completed or _pending_tasks.get(task_id) or {}
        err_msg = completed_data.get("error", "unknown error")
        err_code = completed_data.get("error_code")
        err_status = completed_data.get("error_status")
        
        _stats["failure"] += 1
        logger.error(f"Task {task_id} failed: code={err_code}, status={err_status}, message={err_msg}")

        status_code = 500
        error_type = "server_error"
        error_code = "generation_failed"

        if err_code or err_status:
            if err_code == 429 or err_status == "RESOURCE_EXHAUSTED":
                status_code = 429
                error_type = "rate_limit_error"
                error_code = "rate_limit_exceeded"
            elif err_code == 401 or err_status == "UNAUTHENTICATED":
                status_code = 401
                error_type = "invalid_request_error"
                error_code = "authentication_error"
            elif err_code == 400 or err_status == "INVALID_ARGUMENT":
                status_code = 400
                error_type = "invalid_request_error"
                error_code = "invalid_argument"
            elif err_code == 503 or err_status == "UNAVAILABLE":
                status_code = 503
                error_type = "server_error"
                error_code = "service_unavailable"
        else:
            err_msg_lower = err_msg.lower()
            if "bearer" in err_msg_lower or "recaptcha" in err_msg_lower:
                status_code = 503
                error_type = "server_error"
                error_code = "bridge_not_ready"

        raise HTTPException(
            status_code=status_code,
            detail={
                "error": {
                    "message": err_msg,
                    "type": error_type,
                    "param": None,
                    "code": error_code
                }
            }
        )


@app.post("/generate")
async def generate_raw(request: Request):
    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "message": "Invalid JSON body",
                    "type": "invalid_request_error",
                    "param": None,
                    "code": "invalid_json"
                }
            }
        )

    task_id = str(uuid.uuid4())[:8]

    model_input_raw = body.get("model", "GEM_PIX_2")
    model_key = MODEL_KEY_MAP.get(model_input_raw.lower() if model_input_raw else "GEM_PIX_2", "GEM_PIX_2")
    ar_input = body.get("aspect_ratio", body.get("size", "portrait_3_4"))
    aspect_ratio = parse_aspect_ratio(ar_input)

    # 归一化 image_base64 为数组
    image_base64_raw = body.get("image_base64")
    if image_base64_raw is None:
        images_base64 = []
    elif isinstance(image_base64_raw, list):
        images_base64 = image_base64_raw
    else:
        images_base64 = [image_base64_raw]

    image_mime_raw = body.get("image_mime_type", "image/png")
    if isinstance(image_mime_raw, list):
        images_mime = image_mime_raw
    else:
        images_mime = [image_mime_raw] * len(images_base64)

    _stats["total"] += 1
    _pending_tasks[task_id] = {
        "prompt": body.get("prompt", "test"),
        "aspect_ratio": aspect_ratio,
        "model": model_key,
        "seed": body.get("seed"),
        "n": 1,
        "response_format": "url",
        "images_base64": images_base64,
        "images_mime_type": images_mime,
        "status": "pending",
        "result": None,
        "_start_time": time.time(),
    }

    logger.info(f"Raw task {task_id} created")
    return {"task_id": task_id, "status": "queued"}


@app.post("/result")
async def submit_result(request: Request):
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return {"ok": False, "error": "Invalid JSON body"}, 400

    task_id = body.get("task_id", "")
    if not task_id:
        return {"ok": False, "error": "Missing task_id"}, 400

    if task_id in _pending_tasks:
        _pending_tasks[task_id]["status"] = body.get("status", "done")
        _pending_tasks[task_id]["result"] = body
        _completed_tasks[task_id] = body
        _completed_tasks[task_id]["_time"] = time.time()

        if body.get("success"):
            _stats["success"] += 1
            logger.info(f"Task {task_id} marked as success")
        else:
            _stats["failure"] += 1
            logger.error(f"Task {task_id} marked as failure: {body.get('error', '')}")

        event = _task_events.get(task_id)
        if event:
            event.set()

    return {"ok": True}


@app.get("/poll")
async def poll_tasks():
    global _next_poll_id
    for tid, task in list(_pending_tasks.items()):
        if task["status"] == "pending":
            task["status"] = "processing"
            _next_poll_id += 1
            logger.debug(f"Task {tid} picked up by bridge worker")
            return {
                "task_id": tid,
                "prompt": task["prompt"],
                "aspect_ratio": task["aspect_ratio"],
                "model": task["model"],
                "seed": task["seed"],
                "n": task.get("n", 1),
                "response_format": task.get("response_format", "url"),
                "images_base64": task.get("images_base64", []),
                "images_mime_type": task.get("images_mime_type", []),
                "poll_id": _next_poll_id,
            }
    return {"task_id": None}


@app.get("/result")
async def get_result(task_id: Optional[str] = None):
    if not task_id:
        return {
            "created": int(time.time()),
            "data": [],
            "task_id": None,
            "status": "no_task_id",
        }

    if task_id in _completed_tasks:
        result = _completed_tasks[task_id]
        images = []
        meta_list = result.get("image_meta", [])
        urls = result.get("images", [])
        for i, url in enumerate(urls):
            entry = {
                "url": url,
                "b64_json": None,
                "revised_prompt": "",
            }
            if i < len(meta_list) and meta_list[i].get("mediaId"):
                entry["media_id"] = meta_list[i]["mediaId"]
            images.append(entry)
        return {
            "created": int(time.time()),
            "data": images,
            "task_id": task_id,
            "status": result.get("status", "done"),
            "error": result.get("error"),
        }
    elif task_id in _pending_tasks:
        return {
            "created": int(time.time()),
            "data": [],
            "task_id": task_id,
            "status": _pending_tasks[task_id]["status"],
        }
    else:
        return {
            "created": int(time.time()),
            "data": [],
            "task_id": task_id,
            "status": "not_found",
        }


@app.get("/health")
async def health_check():
    return {
        "ok": True,
        "total": _stats["total"],
        "success": _stats["success"],
        "failure": _stats["failure"],
        "pending": len(_pending_tasks),
        "completed": len(_completed_tasks),
        "processing": sum(1 for t in _pending_tasks.values() if t["status"] == "processing"),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/v1/models")
async def list_models(request: Request):
    verify_api_key(request)
    models = []
    for mid in MODEL_MAPPING.keys():
        models.append({
            "id": mid,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "flow",
            "permission": [],
            "root": mid,
            "parent": None,
        })
    return {"object": "list", "data": models}





if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
