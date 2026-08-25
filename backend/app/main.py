from contextlib import asynccontextmanager
import logging
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.database import init_db, async_session_factory

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    await init_db()

    # 清理回收站过期文件
    try:
        import asyncio
        from app.modules.character.service import CharacterService
        await asyncio.to_thread(CharacterService.cleanup_recycle_bin)
    except Exception as e:
        logger.warning(f"回收站清理失败: {e}")

    # 从数据库加载 LLM 配置到内存缓存
    try:
        from app.routers.system import _llm_config, _load_llm_config_from_db
        async with async_session_factory() as session:
            db_config = await _load_llm_config_from_db(session)
            _llm_config.update(db_config)
    except Exception as e:
        logger.warning(f"Failed to load LLM config from DB: {e}")

    # 从数据库加载生图配置到内存缓存
    try:
        from app.routers.system import _image_gen_config, _load_image_gen_config_from_db
        async with async_session_factory() as session:
            db_config = await _load_image_gen_config_from_db(session)
            _image_gen_config.update(db_config)
    except Exception as e:
        logger.warning(f"Failed to load image gen config from DB: {e}")

    # 启动时自动清理卡住的任务（queued/running 超过 30 分钟）
    try:
        from app.repositories.task_repo import cleanup_stuck_tasks
        await cleanup_stuck_tasks()
    except Exception as e:
        logger.warning(f"启动时清理卡住任务失败: {e}")

    yield

    # 关闭时：关闭 httpx client 连接池 + 释放数据库连接池
    try:
        from app.infra.adapters.http_client import HttpClientManager
        await HttpClientManager.close_all()
    except Exception as e:
        logger.warning(f"关闭 httpx client 失败: {e}")

    try:
        from app.core.database import engine
        await engine.dispose()
    except Exception as e:
        logger.warning(f"关闭数据库连接池失败: {e}")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Webtoon Factory",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 请求日志
    logging.basicConfig(level=logging.INFO, force=True)
    _req_logger = logging.getLogger("debug_requests")

    @app.middleware("http")
    async def log_requests(request, call_next):
        _req_logger.info(f"===== REQUEST: {request.method} {request.url.path} =====")
        response = await call_next(request)
        _req_logger.info(f"===== RESPONSE: {response.status_code} =====")
        return response

    # 注册路由
    from app.routers import auth, projects, novels, characters, generation, export, system, tasks, ws, search, worlds, notifications, prompts, dashboard
    from app.core.dependencies import require_project

    # 以下挂在 /api/v1/projects 下的 router，其每条路由路径都以 /{project_id} 开头，
    # 因此可以用 router 级 require_project 统一做项目归属校验
    _project_scoped = [Depends(require_project)]

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
    app.include_router(projects.router, prefix="/api/v1/projects", tags=["项目管理"])
    app.include_router(novels.router, prefix="/api/v1/projects", tags=["小说管理"], dependencies=_project_scoped)
    app.include_router(characters.router, prefix="/api/v1/projects", tags=["人物IP"], dependencies=_project_scoped)
    app.include_router(characters.global_router, prefix="/api/v1/characters", tags=["人物IP"])
    app.include_router(generation.router, prefix="/api/v1/projects", tags=["生图"], dependencies=_project_scoped)
    app.include_router(export.router, prefix="/api/v1/projects", tags=["导出"], dependencies=_project_scoped)
    app.include_router(system.router, prefix="/api/v1/system", tags=["系统"])
    app.include_router(tasks.router, prefix="/api/v1/projects", tags=["任务"], dependencies=_project_scoped)
    app.include_router(tasks.global_router, prefix="/api/v1/tasks", tags=["任务中心"])
    app.include_router(ws.router, prefix="/ws", tags=["WebSocket"])
    app.include_router(search.router, prefix="/api/v1/search", tags=["搜索"])
    app.include_router(worlds.router, prefix="/api/v1/projects", tags=["世界观"], dependencies=_project_scoped)
    app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["通知"])
    app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["仪表盘"])
    app.include_router(prompts.router, prefix="/api/v1", tags=["Prompt中心"])
    app.include_router(system.model_router, prefix="/api/v1/models", tags=["模型配置"])

    @app.get("/api/v1/health")
    async def health_check():
        return {"status": "ok", "version": "1.0.0"}

    # 挂载静态文件服务，提供本地存储图片的访问
    import os
    storage_path = settings.STORAGE_LOCAL_PATH
    if not os.path.isabs(storage_path):
        storage_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), storage_path)
    os.makedirs(storage_path, exist_ok=True)
    app.mount("/storage", StaticFiles(directory=storage_path), name="storage")

    return app


app = create_app()
