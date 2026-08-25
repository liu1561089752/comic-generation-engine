from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, cast, Text as SAText
from app.core.database import get_db
from app.core.config import settings
from app.core.crypto import encrypt_secret, decrypt_secret
from app.middleware.auth import get_current_user
from app.core.dependencies import require_admin
from app.schemas.common import ApiResponse
from app.models.system import SystemLog, Plugin
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime, timezone
import logging
import uuid

router = APIRouter()
logger = logging.getLogger(__name__)


def _mask_key(key: str) -> str:
    """API Key 打码：保留前 8 后 4 位，中间省略。"""
    if not key:
        return ""
    if len(key) > 12:
        return key[:8] + "..." + key[-4:]
    return "***"

# ---------- Model Configuration API (第16篇) ----------

model_router = APIRouter()

# M10: 内存配置全局变量。使用 .clear()+.update() 更新（而非替换引用），
# 确保持有旧引用的协程也能看到新值。
_llm_config = {
    "api_base": settings.LLM_API_BASE,
    "api_key": settings.LLM_API_KEY,
    "model_name": settings.LLM_MODEL,
    "is_active": bool(settings.LLM_API_KEY),
}

_image_gen_config = {
    "api_base": settings.IMAGE_API_BASE,
    "api_key": settings.IMAGE_API_KEY,
    "model_name": settings.IMAGE_MODEL,
    "is_active": bool(settings.IMAGE_API_KEY),
}

# M10: 使用 bounded deque 防止内存泄漏（最多保留 1000 条日志）
# 统一使用共享实例，使 LLM 适配器的调用日志也能被 /model-logs 端点返回
from app.infra.model_logs import model_call_logs as _model_call_logs


class LLMConfigUpdate(BaseModel):
    api_base: str
    api_key: str
    model_name: str
    is_active: Optional[bool] = True


class ImageGenConfigUpdate(BaseModel):
    api_base: str
    api_key: str
    model_name: str
    is_active: Optional[bool] = True


async def _load_llm_config_from_db(db: AsyncSession) -> dict:
    """从数据库加载 LLM 配置，未找到时回退到 settings。

    api_key 落库为 AES-256-GCM 密文，读取时解密；
    旧明文数据（解密失败）按原样使用并记录 warning，保证升级不中断。
    """
    from app.models.system import LLMConfig
    result = await db.execute(select(LLMConfig).where(LLMConfig.is_active == True).limit(1))
    row = result.scalar_one_or_none()
    if row:
        api_key = row.api_key or ""
        if api_key:
            decrypted = decrypt_secret(api_key)
            if decrypted is None:
                logger.warning("LLM api_key 解密失败，按旧明文处理，请重新保存一次配置")
                decrypted = api_key
            api_key = decrypted
        return {
            "api_base": row.api_base or "",
            "api_key": api_key,
            "model_name": row.model_name or "",
            "is_active": row.is_active,
        }
    return {
        "api_base": settings.LLM_API_BASE,
        "api_key": settings.LLM_API_KEY,
        "model_name": settings.LLM_MODEL,
        "is_active": bool(settings.LLM_API_KEY),
    }


@model_router.get("/llm")
async def get_llm_config(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取 LLM 模型配置（从数据库读取，不修改内存缓存）"""
    db_config = await _load_llm_config_from_db(db)
    return ApiResponse(data={**db_config, "api_key": _mask_key(db_config["api_key"])})


@model_router.put("/llm")
async def update_llm_config(
    config: LLMConfigUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新 LLM 模型配置（持久化到数据库，api_key 加密存储）"""
    from app.models.system import LLMConfig
    # 查找已有配置
    result = await db.execute(select(LLMConfig).where(LLMConfig.is_active == True).limit(1))
    row = result.scalar_one_or_none()
    encrypted_key = encrypt_secret(config.api_key)
    if row:
        row.api_base = config.api_base
        row.api_key = encrypted_key
        row.model_name = config.model_name
        row.is_active = config.is_active
        row.updated_at = datetime.now(timezone.utc)
    else:
        row = LLMConfig(
            api_base=config.api_base,
            api_key=encrypted_key,
            model_name=config.model_name,
            is_active=config.is_active,
        )
        db.add(row)
    await db.commit()
    await db.refresh(row)
    # 更新内存缓存（内存中保留明文供运行时使用）
    _llm_config.update({
        "api_base": config.api_base,
        "api_key": config.api_key,
        "model_name": config.model_name,
        "is_active": config.is_active,
    })
    _model_call_logs.append({
        "id": str(uuid.uuid4()),
        "model_type": "llm",
        "model_name": config.model_name,
        "call_type": "config_update",
        "duration_ms": 0,
        "status": "success",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    # 响应不回显明文 api_key
    return ApiResponse(message="LLM 配置已更新", data={**_llm_config, "api_key": _mask_key(config.api_key)})


@model_router.post("/llm/test")
async def test_llm_connection(user_id: str = Depends(get_current_user)):
    """测试 LLM 连接（实际调一次 LLM 验证）"""
    import time
    start = time.time()
    try:
        if not _llm_config["api_key"]:
            raise HTTPException(status_code=400, detail="API Key 未配置")
        # 实际调用一次 LLM 验证连接
        from app.infra.adapters.llm_adapter import LLMAdapter, ChatMessage
        adapter = LLMAdapter(timeout=30)
        await adapter.chat(
            messages=[ChatMessage(role="user", content="Hello")],
            temperature=0.1,
            max_tokens=1,
        )
        duration_ms = int((time.time() - start) * 1000)
        _model_call_logs.append({
            "id": str(uuid.uuid4()),
            "model_type": "llm",
            "model_name": _llm_config["model_name"],
            "call_type": "llm_chat",
            "duration_ms": duration_ms,
            "status": "success",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return ApiResponse(message="连接测试成功", data={"duration_ms": duration_ms})
    except HTTPException:
        raise
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        _model_call_logs.append({
            "id": str(uuid.uuid4()),
            "model_type": "llm",
            "model_name": _llm_config["model_name"],
            "call_type": "llm_chat",
            "duration_ms": duration_ms,
            "status": "failed",
            "error_message": str(e),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        raise HTTPException(status_code=500, detail=f"连接测试失败: {str(e)}")


async def _load_image_gen_config_from_db(db: AsyncSession) -> dict:
    """从数据库加载生图配置，未找到时回退到 settings。

    api_key 落库为 AES-256-GCM 密文，读取时解密；
    旧明文数据（解密失败）按原样使用并记录 warning，保证升级不中断。
    """
    from app.models.system import ImageGenConfig
    result = await db.execute(select(ImageGenConfig).where(ImageGenConfig.is_active == True).limit(1))
    row = result.scalar_one_or_none()
    if row:
        api_key = row.api_key or ""
        if api_key:
            decrypted = decrypt_secret(api_key)
            if decrypted is None:
                logger.warning("生图 api_key 解密失败，按旧明文处理，请重新保存一次配置")
                decrypted = api_key
            api_key = decrypted
        return {
            "api_base": row.api_base or "",
            "api_key": api_key,
            "model_name": row.model_name or "",
            "is_active": row.is_active,
        }
    return {
        "api_base": settings.IMAGE_API_BASE,
        "api_key": settings.IMAGE_API_KEY or "",
        "model_name": settings.IMAGE_MODEL or "",
        "is_active": bool(settings.IMAGE_API_KEY),
    }


@model_router.get("/image-gen")
async def get_image_gen_config(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取生图模型配置（从数据库读取，不修改内存缓存）"""
    db_config = await _load_image_gen_config_from_db(db)
    return ApiResponse(data={**db_config, "api_key": _mask_key(db_config["api_key"])})


@model_router.put("/image-gen")
async def update_image_gen_config(
    config: ImageGenConfigUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新生图模型配置（持久化到数据库，api_key 加密存储）"""
    from app.models.system import ImageGenConfig
    # 查找已有配置
    result = await db.execute(select(ImageGenConfig).where(ImageGenConfig.is_active == True).limit(1))
    row = result.scalar_one_or_none()
    encrypted_key = encrypt_secret(config.api_key)
    if row:
        row.api_base = config.api_base
        row.api_key = encrypted_key
        row.model_name = config.model_name
        row.is_active = config.is_active
        row.updated_at = datetime.now(timezone.utc)
    else:
        row = ImageGenConfig(
            api_base=config.api_base,
            api_key=encrypted_key,
            model_name=config.model_name,
            is_active=config.is_active,
        )
        db.add(row)
    await db.commit()
    await db.refresh(row)
    # 更新内存缓存（内存中保留明文供运行时使用）
    _image_gen_config.update({
        "api_base": config.api_base,
        "api_key": config.api_key,
        "model_name": config.model_name,
        "is_active": config.is_active,
    })
    _model_call_logs.append({
        "id": str(uuid.uuid4()),
        "model_type": "image",
        "model_name": config.model_name,
        "call_type": "config_update",
        "duration_ms": 0,
        "status": "success",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    # 响应不回显明文 api_key
    return ApiResponse(message="生图模型配置已更新", data={**_image_gen_config, "api_key": _mask_key(config.api_key)})


@model_router.post("/image-gen/test")
async def test_image_gen_connection(user_id: str = Depends(get_current_user)):
    """测试生图模型连接（实际调用一次生图接口验证）"""
    import time
    start = time.time()
    try:
        if not _image_gen_config["api_key"]:
            raise HTTPException(status_code=400, detail="API Key 未配置")
        from app.infra.adapters.image_gen_adapter import ImageGenAdapter
        adapter = ImageGenAdapter(request_timeout=30)
        result = await adapter.generate("a simple test image of a red circle on white background")
        duration_ms = int((time.time() - start) * 1000)
        _model_call_logs.append({
            "id": str(uuid.uuid4()),
            "model_type": "image",
            "model_name": _image_gen_config["model_name"],
            "call_type": "image_generation",
            "duration_ms": duration_ms,
            "status": "success",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return ApiResponse(message="连接测试成功", data={"duration_ms": duration_ms})
    except HTTPException:
        raise
    except Exception as e:
        _model_call_logs.append({
            "id": str(uuid.uuid4()),
            "model_type": "image",
            "model_name": _image_gen_config["model_name"],
            "call_type": "image_generation",
            "duration_ms": int((time.time() - start) * 1000),
            "status": "failed",
            "error_message": str(e),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        raise HTTPException(status_code=500, detail=f"连接测试失败: {str(e)}")


@model_router.get("/logs")
async def get_model_logs(
    call_type: Optional[str] = Query(None, description="调用类型过滤"),
    status: Optional[str] = Query(None, description="状态过滤"),
    search: Optional[str] = Query(None, description="搜索模型名称"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user),
):
    """获取模型调用日志"""
    logs = list(_model_call_logs)
    logs.reverse()

    if call_type:
        logs = [l for l in logs if l.get("call_type") == call_type]
    if status:
        logs = [l for l in logs if l.get("status") == status]
    if search:
        logs = [l for l in logs if search.lower() in l.get("model_name", "").lower()]

    total = len(logs)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    return ApiResponse(data={
        "items": logs[start_idx:end_idx],
        "total": total,
        "page": page,
        "page_size": page_size,
    })


# ---------- Existing system endpoints ----------

@router.get("/health")
async def health_check(user_id: str = Depends(get_current_user)):
    """健康检查"""
    return ApiResponse(data={
        "status": "ok",
        "version": "1.0.0",
        "environment": settings.APP_ENV,
    })


@router.get("/stats")
async def system_stats(db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    """系统统计信息"""
    from app.models.novel import Project
    from app.models.novel import Novel
    from app.models.character import Character

    try:
        project_count = await db.scalar(select(func.count(Project.id)))
        novel_count = await db.scalar(select(func.count(Novel.id)))
        character_count = await db.scalar(select(func.count(Character.id)))
        # Scene/Image/Panel 模型已删除，相关统计返回 0
        scene_count = 0
        image_count = 0
        panel_count = 0
    except Exception as e:
        logger.error(f"system_stats 查询失败: {e}", exc_info=True)
        project_count = novel_count = character_count = scene_count = image_count = panel_count = 0

    return ApiResponse(data={
        "projects": project_count or 0,
        "novels": novel_count or 0,
        "characters": character_count or 0,
        "scenes": scene_count or 0,
        "panels": panel_count or 0,
        "generated_images": image_count or 0,
    })


@router.get("/config")
async def system_config(user_id: str = Depends(get_current_user), admin=Depends(require_admin)):
    """获取系统配置（不含敏感信息）"""
    return ApiResponse(data={
        "app_env": settings.APP_ENV,
        "app_debug": settings.APP_DEBUG,
        "app_log_level": settings.APP_LOG_LEVEL,
        "llm_model": settings.LLM_MODEL,
        "image_model": settings.IMAGE_MODEL,
        "image_default_width": settings.IMAGE_DEFAULT_WIDTH,
        "image_default_height": settings.IMAGE_DEFAULT_HEIGHT,
        "image_max_concurrent": settings.IMAGE_MAX_CONCURRENT,
        "storage_backend": settings.STORAGE_BACKEND,
        "export_max_file_size_mb": settings.EXPORT_MAX_FILE_SIZE_MB,
    })


class SystemConfigUpdate(BaseModel):
    """可运行时修改的系统配置项。改动只作用于当前进程，重启后回退到 .env"""
    image_max_concurrent: Optional[int] = Field(None, ge=1, le=32)
    storage_backend: Optional[Literal["local", "s3", "oss"]] = None
    app_debug: Optional[bool] = None
    app_log_level: Optional[Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]] = None


@router.put("/config")
async def update_system_config(config: SystemConfigUpdate, user_id: str = Depends(get_current_user), admin=Depends(require_admin)):
    """更新系统配置"""
    # 只写入本次显式提供的字段，避免未传的项被 None 覆盖
    changes = config.model_dump(exclude_unset=True, exclude_none=True)
    for k, v in changes.items():
        if hasattr(settings, k.upper()):
            setattr(settings, k.upper(), v)
    return ApiResponse(message="系统配置已更新")


# ---------- 操作日志 (第17篇) ----------

@router.get("/activity-logs")
async def get_activity_logs(
    module: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    """获取操作日志"""
    query = select(SystemLog).order_by(SystemLog.created_at.desc())
    if module:
        query = query.where(SystemLog.module == module)
    if action:
        query = query.where(SystemLog.action == action)
    if search:
        # details 是 JSON 列，PostgreSQL 无 json ~~* text 操作符，需先转成文本再模糊匹配
        query = query.where(cast(SystemLog.details, SAText).ilike(f"%{search}%"))

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    logs = result.scalars().all()

    return ApiResponse(data={
        "items": [
            {
                "id": str(log.id),
                "level": log.level,
                "module": log.module,
                "action": log.action,
                "user_id": log.user_id,
                "target_type": log.target_type,
                "details": log.details,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
        "total": total or 0,
        "page": page,
        "page_size": page_size,
    })


# ---------- 存储管理 (第17篇) ----------

@router.get("/storage/stats")
async def get_storage_stats(user_id: str = Depends(get_current_user)):
    """获取存储空间统计"""
    import os
    import asyncio
    storage_path = settings.STORAGE_LOCAL_PATH

    def _calc_storage_size(path):
        total_size = 0
        file_count = 0
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total_size += os.path.getsize(fp)
                    file_count += 1
                except OSError:
                    pass
        return total_size, file_count

    total_size, file_count = await asyncio.to_thread(_calc_storage_size, storage_path)
    return ApiResponse(data={
        "storage_path": storage_path,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "file_count": file_count,
        "storage_limit_mb": 10240,
    })


@router.post("/storage/clear-cache")
async def clear_cache(user_id: str = Depends(get_current_user), admin=Depends(require_admin)):
    """清理缓存"""
    import shutil
    import os
    import asyncio
    cache_dir = os.path.join(settings.STORAGE_LOCAL_PATH, ".cache")

    def _do_clear_cache(path):
        cleared = 0
        if os.path.exists(path):
            for f in os.listdir(path):
                fp = os.path.join(path, f)
                try:
                    if os.path.isfile(fp):
                        cleared += os.path.getsize(fp)
                        os.remove(fp)
                    elif os.path.isdir(fp):
                        cleared += sum(
                            os.path.getsize(os.path.join(dirpath, filename))
                            for dirpath, _, filenames in os.walk(fp)
                            for filename in filenames
                        )
                        shutil.rmtree(fp)
                except OSError:
                    pass
        return cleared

    cleared = await asyncio.to_thread(_do_clear_cache, cache_dir)
    return ApiResponse(data={
        "cleared_bytes": cleared,
        "cleared_mb": round(cleared / (1024 * 1024), 2),
        "message": "缓存已清理",
    })


# ---------- 数据备份 (第17篇) ----------
# 注：PostgreSQL 迁移后，文件级备份已失效。备份/恢复改用 pg_dump / pg_restore 外部工具。

@router.post("/backup")
async def create_backup(user_id: str = Depends(get_current_user), admin=Depends(require_admin)):
    """创建数据备份（PostgreSQL 迁移后已禁用，请使用 pg_dump）"""
    raise HTTPException(
        status_code=501,
        detail="文件级备份在 PostgreSQL 迁移后已禁用。请使用 `pg_dump -Fc -d $DATABASE_URL -f backup.dump` 进行备份。",
    )


@router.get("/backups")
async def list_backups(user_id: str = Depends(get_current_user), admin=Depends(require_admin)):
    """列出所有备份文件（仅 storage/backups 目录下的历史文件）"""
    import os
    import asyncio
    backup_dir = os.path.join(settings.STORAGE_LOCAL_PATH, "backups")

    def _list_backups_sync(path):
        backups = []
        if os.path.exists(path):
            for f in sorted(os.listdir(path), reverse=True):
                fp = os.path.join(path, f)
                if os.path.isfile(fp):
                    backups.append({
                        "name": f,
                        "size_bytes": os.path.getsize(fp),
                        "size_mb": round(os.path.getsize(fp) / (1024 * 1024), 2),
                        "created_at": datetime.fromtimestamp(os.path.getmtime(fp)).isoformat(),
                    })
        return backups

    backups = await asyncio.to_thread(_list_backups_sync, backup_dir)
    return ApiResponse(data=backups)


@router.post("/backup/restore")
async def restore_backup(backup_name: str, user_id: str = Depends(get_current_user), admin=Depends(require_admin)):
    """恢复备份（PostgreSQL 迁移后已禁用，请使用 pg_restore）"""
    raise HTTPException(
        status_code=501,
        detail="文件级恢复在 PostgreSQL 迁移后已禁用。请使用 `pg_restore -d $DATABASE_URL -c backup.dump` 进行恢复。",
    )


# ---------- 插件管理 (第18篇) ----------

@router.get("/plugins")
async def list_plugins(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    """获取插件列表"""
    query = select(Plugin).order_by(Plugin.name)
    total = await db.scalar(select(func.count(Plugin.id)))
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    plugins = result.scalars().all()
    return ApiResponse(data={
        "items": [
            {
                "id": str(p.id),
                "name": p.name,
                "version": p.version,
                "description": p.description,
                "plugin_type": p.plugin_type,
                "config_schema": p.config_schema,
                "enabled": p.enabled,
            }
            for p in plugins
        ],
        "total": total or 0,
        "page": page,
        "page_size": page_size,
    })


class PluginToggle(BaseModel):
    enabled: bool


@router.put("/plugins/{plugin_id}/toggle")
async def toggle_plugin(plugin_id: str, body: PluginToggle, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user), admin=Depends(require_admin)):
    """启用/禁用插件"""
    from pydantic import UUID4
    try:
        uid = uuid.UUID(plugin_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的插件 ID")
    result = await db.execute(select(Plugin).where(Plugin.id == uid))
    plugin = result.scalar_one_or_none()
    if not plugin:
        raise HTTPException(status_code=404, detail="插件不存在")
    plugin.enabled = body.enabled
    await db.commit()
    return ApiResponse(message=f"插件 {'已启用' if body.enabled else '已禁用'}")


@router.get("/plugins/{plugin_id}")
async def get_plugin_detail(plugin_id: str, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    """获取插件详情"""
    try:
        uid = uuid.UUID(plugin_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的插件 ID")
    result = await db.execute(select(Plugin).where(Plugin.id == uid))
    plugin = result.scalar_one_or_none()
    if not plugin:
        raise HTTPException(status_code=404, detail="插件不存在")
    return ApiResponse(data={
        "id": str(plugin.id),
        "name": plugin.name,
        "version": plugin.version,
        "description": plugin.description,
        "plugin_type": plugin.plugin_type,
        "config_schema": plugin.config_schema,
        "enabled": plugin.enabled,
    })
