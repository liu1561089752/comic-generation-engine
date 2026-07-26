import os
import asyncio
import logging
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from pydantic import BaseModel

from app.infra.task_progress import TaskProgressTracker, find_running_task
from app.infra.task_registry import spawn_background_task
from app.core.database import get_db, async_session_factory

logger = logging.getLogger(__name__)

class RegeneratePagePromptRequest(BaseModel):
    page_id: str

class GenerateSingleImageRequest(BaseModel):
    page_id: str
    reference_ids: list[str] = []

class GeneratePageImagesRequest(BaseModel):
    reference_ids: dict[str, list[str]] = {}

from app.middleware.auth import get_current_user
from app.core.dependencies import require_project_novel
from app.modules.novel.facade import NovelService
from app.modules.image_recovery.service import ImageRecoveryService
from app.schemas.common import ApiResponse
from app.schemas.novel_schema import (
    ChapterUpdate,
    EditorSaveRequest,
    MergeChapterRequest,
    SplitChapterRequest,
    SplitShotRequest,
    SaveScriptRequest,
    SaveStoryboardRequest,
    SaveLayoutRequest,
)


class UpdateNovelTextRequest(BaseModel):
    raw_text: str

class BatchDeletePagesRequest(BaseModel):
    start_page: int
    end_page: int
    delete_type: str  # "prompt" | "reference" | "page"


router = APIRouter()


# =====================================================================
# 小说基础 API
# =====================================================================

@router.post("/{project_id}/novels/upload")
async def upload_novel(
    project_id: UUID,
    file: UploadFile = File(...),
    title: str = Form(None),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传小说文件"""
    MAX_SIZE = 100 * 1024 * 1024

    allowed_extensions = {".txt", ".docx", ".md"}
    if file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in allowed_extensions:
            raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}，仅支持 txt/docx/md")

    # 分块读取并即时累计，超限立刻中断，避免超大文件被整体读进内存
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_SIZE:
            raise HTTPException(status_code=413, detail="文件大小超过限制 (最大 100MB)")
        chunks.append(chunk)
    contents = b"".join(chunks)

    service = NovelService(db)
    try:
        result = await service.upload_novel(project_id, contents, file.filename, title)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class RecoverImagesRequest(BaseModel):
    authorization: str
    xtx: str
    limit: int = 100


async def _run_recover_images(project_id, novel_id, authorization, xtx, limit, tracker):
    async with async_session_factory() as session:
        try:
            service = ImageRecoveryService(session)
            await tracker.rebind_session(session)
            await tracker.set_running()
            result = await service.recover_images(project_id, novel_id, authorization, xtx, limit, tracker=tracker)
            await tracker.complete(result, broadcast=False)
            await session.commit()
            await tracker._broadcast()
        except Exception as e:
            logger.exception(f"补图任务失败: {e}")
            await session.rollback()
            try:
                await tracker.fail(str(e))
                await session.commit()
            except:
                await session.rollback()


@router.post("/{project_id}/novels/{novel_id}/recover-images")
async def recover_images(
    project_id: UUID,
    novel_id: UUID,
    body: RecoverImagesRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """从 GRS AI 积分记录中恢复未生成图片的漫画页"""
    existing = await find_running_task(db, project_id, "recover_images", str(novel_id))
    if existing:
        return ApiResponse(data={"task_id": str(existing.id), "message": "已有正在执行的补图任务"})
    # authorization / xtx 属于临时凭证，不写入 input_data（避免明文落库）
    tracker = await TaskProgressTracker.create(
        db, project_id, "recover_images",
        "补图", {"novel_id": str(novel_id), "limit": body.limit}
    )
    spawn_background_task(
        tracker.task.id,
        _run_recover_images(project_id, novel_id, body.authorization, body.xtx, body.limit, tracker),
    )
    return ApiResponse(data={"task_id": str(tracker.task.id)})


@router.delete("/{project_id}/novels/{novel_id}/layout-pages")
async def delete_all_layout_pages(
    project_id: UUID,
    novel_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """删除小说所有漫画页的图片（数据库记录 + 文件系统图片）"""
    service = NovelService(db)
    try:
        result = await service.delete_all_layout_pages(project_id, novel_id)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/novels/{novel_id}/batch-delete-pages")
async def batch_delete_pages(
    project_id: UUID,
    novel_id: UUID,
    body: BatchDeletePagesRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """批量删除指定页面的内容（按范围 + 类型删除数据库记录）.

    delete_type 可选值:
      - "prompt": 清空生图提示词
      - "reference": 清空参考图
      - "page": 删除漫画页图片（图片文件 + image_url）
    """
    service = NovelService(db)
    try:
        result = await service.batch_delete_pages_content(
            project_id, novel_id, body.start_page, body.end_page, body.delete_type,
        )
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ===================================================================
# 后台任务辅助函数
# ===================================================================

async def _run_background_task(
    project_id: UUID,
    novel_id: UUID,
    tracker: TaskProgressTracker,
    task_type: str,
    **kwargs,
):
    """通用后台任务执行器：创建独立 session，绑定 tracker，执行 service 方法"""
    async with async_session_factory() as session:
        try:
            service = NovelService(session)
            await tracker.rebind_session(session)
            await tracker.set_running()

            method_name = kwargs.get("_method", task_type)
            method = getattr(service, method_name, None)
            if method is None:
                raise ValueError(f"Unknown method: {method_name}")

            # 支持额外参数
            extra_args = {k: v for k, v in kwargs.items() if not k.startswith("_")}
            result = await method(novel_id, **extra_args)

            await tracker.complete(result)
            await session.commit()
            await tracker._broadcast()
        except Exception as e:
            logger.exception(f"后台任务失败: {e}")
            # D7: 先回滚丢弃半成品数据，再写失败状态
            await session.rollback()
            try:
                await tracker.fail(str(e))
                await session.commit()
            except:
                await session.rollback()


async def _run_generate_script(project_id, novel_id, tracker):
    logger.info(f"_run_generate_script 开始: novel_id={novel_id}")
    async with async_session_factory() as session:
        try:
            service = NovelService(session)
            logger.info("开始 rebind_session...")
            await tracker.rebind_session(session)
            logger.info("rebind_session 完成")
            await tracker.set_running()
            logger.info("set_running 完成, 开始 generate_script...")
            result = await service.generate_script(novel_id)
            logger.info(f"generate_script 完成, 开始 complete...")
            await tracker.complete(result)
            logger.info("complete 完成, 开始 commit...")
            await session.commit()
            logger.info("commit 完成, 开始 broadcast...")
            await tracker._broadcast()
            logger.info("broadcast 完成")
        except Exception as e:
            logger.exception(f"后台任务失败: {e}")
            # D7: 先回滚丢弃半成品数据，再写失败状态
            await session.rollback()
            try:
                await tracker.fail(str(e))
                await session.commit()
            except:
                await session.rollback()


async def _run_generate_storyboard(project_id, novel_id, tracker):
    async with async_session_factory() as session:
        try:
            service = NovelService(session)
            await tracker.rebind_session(session)
            await tracker.set_running()
            result = await service.generate_storyboard(novel_id)
            await tracker.complete(result)
            await session.commit()
            await tracker._broadcast()
        except Exception as e:
            logger.exception(f"后台任务失败: {e}")
            # D7: 先回滚丢弃半成品数据，再写失败状态
            await session.rollback()
            try:
                await tracker.fail(str(e))
                await session.commit()
            except:
                await session.rollback()


async def _run_generate_layout(project_id, novel_id, tracker):
    async with async_session_factory() as session:
        try:
            service = NovelService(session)
            await tracker.rebind_session(session)
            await tracker.set_running()
            result = await service.generate_layout(novel_id)
            await tracker.complete(result)
            await session.commit()
            await tracker._broadcast()
        except Exception as e:
            logger.exception(f"后台任务失败: {e}")
            # D7: 先回滚丢弃半成品数据，再写失败状态
            await session.rollback()
            try:
                await tracker.fail(str(e))
                await session.commit()
            except:
                await session.rollback()


async def _run_generate_image_prompts(project_id, novel_id, tracker):
    async with async_session_factory() as session:
        try:
            service = NovelService(session)
            await tracker.rebind_session(session)
            await tracker.set_running()
            result = await service.generate_image_prompts(novel_id)
            await tracker.complete(result, broadcast=False)
            await session.commit()
            await tracker._broadcast()
        except Exception as e:
            logger.exception(f"后台任务失败: {e}")
            # D7: 先回滚丢弃半成品数据，再写失败状态
            await session.rollback()
            try:
                await tracker.fail(str(e))
                await session.commit()
            except:
                await session.rollback()


async def _run_regenerate_page_prompt(project_id, novel_id, page_id, tracker):
    async with async_session_factory() as session:
        try:
            service = NovelService(session)
            await tracker.rebind_session(session)
            await tracker.set_running()
            result = await service.regenerate_page_prompt(novel_id, page_id)
            await tracker.complete(result)
            await session.commit()
            await tracker._broadcast()
        except Exception as e:
            logger.exception(f"后台任务失败: {e}")
            # D7: 先回滚丢弃半成品数据，再写失败状态
            await session.rollback()
            try:
                await tracker.fail(str(e))
                await session.commit()
            except:
                await session.rollback()

async def _run_match_references(project_id, novel_id, tracker):
    async with async_session_factory() as session:
        try:
            service = NovelService(session)
            await tracker.rebind_session(session)
            await tracker.set_running()
            result = await service.match_references(novel_id, project_id)
            await tracker.complete(result)
            await session.commit()
            await tracker._broadcast()
        except Exception as e:
            logger.exception(f"后台任务失败: {e}")
            # D7: 先回滚丢弃半成品数据，再写失败状态
            await session.rollback()
            try:
                await tracker.fail(str(e))
                await session.commit()
            except:
                await session.rollback()


async def _run_generate_single_image(project_id, novel_id, page_id, reference_ids, tracker):
    async with async_session_factory() as session:
        try:
            service = NovelService(session)
            await tracker.rebind_session(session)
            await tracker.set_running()
            result = await service.generate_single_page_image(
                project_id, novel_id, page_id,
                reference_ids=reference_ids,
            )
            await tracker.complete(result)
            await session.commit()
            await tracker._broadcast()
        except Exception as e:
            logger.exception(f"后台任务失败: {e}")
            # D7: 先回滚丢弃半成品数据，再写失败状态
            await session.rollback()
            try:
                await tracker.fail(str(e))
                await session.commit()
            except:
                await session.rollback()


async def _run_generate_page_images(project_id, novel_id, reference_ids, tracker):
    async with async_session_factory() as session:
        try:
            service = NovelService(session)
            await tracker.rebind_session(session)
            await tracker.set_running()
            result = await service.generate_page_images(
                project_id, novel_id,
                reference_ids=reference_ids,
            )
            await tracker.complete(result, broadcast=False)
            await session.commit()
            await tracker._broadcast()
        except Exception as e:
            logger.exception(f"后台任务失败: {e}")
            # D7: 先回滚丢弃半成品数据，再写失败状态
            await session.rollback()
            try:
                await tracker.fail(str(e))
                await session.commit()
            except:
                await session.rollback()


async def _run_preprocess_novel(project_id, novel_id, tracker):
    async with async_session_factory() as session:
        try:
            service = NovelService(session)
            await tracker.rebind_session(session)
            await tracker.set_running()
            result = await service.preprocess_novel(novel_id)
            await tracker.complete(result)
            await session.commit()
            await tracker._broadcast()
        except Exception as e:
            logger.exception(f"后台任务失败: {e}")
            # D7: 先回滚丢弃半成品数据，再写失败状态
            await session.rollback()
            try:
                await tracker.fail(str(e))
                await session.commit()
            except:
                await session.rollback()


# ===================================================================
# 注册任务执行器 — 供 retry 功能重新派发后台任务
# ===================================================================
from app.infra.task_dispatcher import register_task_runner as _register


@_register("generate_script")
async def _redispatch_generate_script(task, tracker):
    novel_id = UUID(task.input_data["novel_id"])
    await _run_generate_script(task.project_id, novel_id, tracker)


@_register("generate_storyboard")
async def _redispatch_generate_storyboard(task, tracker):
    novel_id = UUID(task.input_data["novel_id"])
    await _run_generate_storyboard(task.project_id, novel_id, tracker)


@_register("generate_layout")
async def _redispatch_generate_layout(task, tracker):
    novel_id = UUID(task.input_data["novel_id"])
    await _run_generate_layout(task.project_id, novel_id, tracker)


@_register("generate_image_prompts")
async def _redispatch_generate_image_prompts(task, tracker):
    novel_id = UUID(task.input_data["novel_id"])
    await _run_generate_image_prompts(task.project_id, novel_id, tracker)


@_register("regenerate_page_prompt")
async def _redispatch_regenerate_page_prompt(task, tracker):
    novel_id = UUID(task.input_data["novel_id"])
    page_id = task.input_data.get("page_id", "")
    await _run_regenerate_page_prompt(task.project_id, novel_id, page_id, tracker)


@_register("match_references")
async def _redispatch_match_references(task, tracker):
    novel_id = UUID(task.input_data["novel_id"])
    await _run_match_references(task.project_id, novel_id, tracker)


@_register("generate_single_image")
async def _redispatch_generate_single_image(task, tracker):
    novel_id = UUID(task.input_data["novel_id"])
    page_id = task.input_data.get("page_id", "")
    reference_ids = task.input_data.get("reference_ids")
    await _run_generate_single_image(task.project_id, novel_id, page_id, reference_ids, tracker)


@_register("generate_page_images")
async def _redispatch_generate_page_images(task, tracker):
    novel_id = UUID(task.input_data["novel_id"])
    reference_ids = task.input_data.get("reference_ids")
    await _run_generate_page_images(task.project_id, novel_id, reference_ids, tracker)


@_register("preprocess_novel")
async def _redispatch_preprocess_novel(task, tracker):
    novel_id = UUID(task.input_data["novel_id"])
    await _run_preprocess_novel(task.project_id, novel_id, tracker)


@_register("recover_images")
async def _redispatch_recover_images(task, tracker):
    novel_id = UUID(task.input_data["novel_id"])
    authorization = task.input_data.get("authorization") or ""
    xtx = task.input_data.get("xtx") or ""
    limit = task.input_data.get("limit", 100)
    # 凭证不落库，重试时拿不到；用空凭证调外部接口只会得到 401，直接失败并说明原因
    if not authorization or not xtx:
        await tracker.fail("补图凭证已失效，请重新发起补图任务", exc_info=False)
        return
    await _run_recover_images(task.project_id, novel_id, authorization, xtx, limit, tracker)


# ===================================================================
# 生成 API — 所有 generate_* 端点立即返回 task_id
# ===================================================================

@router.post("/{project_id}/novels/{novel_id}/generate-storyboard")
async def generate_storyboard(
    project_id: UUID,
    novel_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """调用LLM生成所有章节的分镜"""
    existing = await find_running_task(db, project_id, "generate_storyboard", str(novel_id))
    if existing:
        return ApiResponse(data={"task_id": str(existing.id), "message": "已有正在执行的生成分镜任务"})
    tracker = await TaskProgressTracker.create(
        db, project_id, "generate_storyboard",
        "生成分镜", {"novel_id": str(novel_id)}
    )
    spawn_background_task(tracker.task.id, _run_generate_storyboard(project_id, novel_id, tracker))
    return ApiResponse(data={"task_id": str(tracker.task.id)})


@router.get("/{project_id}/novels/{novel_id}/storyboard")
async def get_storyboard(
    project_id: UUID,
    novel_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """获取小说的分镜数据"""
    service = NovelService(db)
    try:
        result = await service.get_storyboard(novel_id)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{project_id}/novels/{novel_id}/storyboard")
async def save_storyboard(
    project_id: UUID,
    novel_id: UUID,
    body: SaveStoryboardRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """保存分镜数据"""
    service = NovelService(db)
    try:
        result = await service.save_storyboard(novel_id, [ch.model_dump() for ch in body.chapters])
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}/novels/{novel_id}/storyboard")
async def delete_all_storyboard(
    project_id: UUID,
    novel_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """删除所有分镜及下游数据（排版、生图提示词、参考图、漫画页图片）."""
    service = NovelService(db)
    try:
        result = await service.delete_all_storyboard_and_generation(project_id, novel_id)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/novels/{novel_id}/generate-layout")
async def generate_layout(
    project_id: UUID,
    novel_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """调用LLM生成所有章节的排版"""
    existing = await find_running_task(db, project_id, "generate_layout", str(novel_id))
    if existing:
        return ApiResponse(data={"task_id": str(existing.id), "message": "已有正在执行的生成排版任务"})
    tracker = await TaskProgressTracker.create(
        db, project_id, "generate_layout",
        "生成排版", {"novel_id": str(novel_id)}
    )
    spawn_background_task(tracker.task.id, _run_generate_layout(project_id, novel_id, tracker))
    return ApiResponse(data={"task_id": str(tracker.task.id)})


@router.get("/{project_id}/novels/{novel_id}/layout")
async def get_layout(
    project_id: UUID,
    novel_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """获取小说的排版数据"""
    service = NovelService(db)
    try:
        result = await service.get_layout(novel_id)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{project_id}/novels/{novel_id}/layout")
async def save_layout(
    project_id: UUID,
    novel_id: UUID,
    body: SaveLayoutRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """保存排版数据"""
    service = NovelService(db)
    try:
        result = await service.save_layout(novel_id, [ch.model_dump() for ch in body.chapters])
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{project_id}/novels/{novel_id}/layout")
async def delete_all_layout(
    project_id: UUID,
    novel_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """删除所有排版及下游数据（生图提示词、参考图、漫画页图片），保留分镜数据."""
    service = NovelService(db)
    try:
        result = await service.delete_all_layout_and_generation(project_id, novel_id)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{project_id}/novels/{novel_id}/layout/{chapter_id}")
async def delete_layout_chapter(
    project_id: UUID,
    novel_id: UUID,
    chapter_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """删除指定章节的排版及下游数据（生图提示词、参考图、漫画页图片），保留分镜数据."""
    service = NovelService(db)
    try:
        result = await service.delete_layout_chapter(novel_id, chapter_id)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/novels/{novel_id}/generate-image-prompts")
async def generate_image_prompts(
    project_id: UUID,
    novel_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """调用LLM为所有排版页面生成生图提示词"""
    existing = await find_running_task(db, project_id, "generate_image_prompts", str(novel_id))
    if existing:
        return ApiResponse(data={"task_id": str(existing.id), "message": "已有正在执行的生成提示词任务"})
    tracker = await TaskProgressTracker.create(
        db, project_id, "generate_image_prompts",
        "生成生图提示词", {"novel_id": str(novel_id)}
    )
    spawn_background_task(tracker.task.id, _run_generate_image_prompts(project_id, novel_id, tracker))
    return ApiResponse(data={"task_id": str(tracker.task.id)})


@router.post("/{project_id}/novels/{novel_id}/regenerate-page-prompt")
async def regenerate_page_prompt(
    project_id: UUID,
    novel_id: UUID,
    body: RegeneratePagePromptRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """重新生成指定页面的生图提示词"""
    tracker = await TaskProgressTracker.create(
        db, project_id, "regenerate_page_prompt",
        "重新生成页面提示词", {"novel_id": str(novel_id), "page_id": body.page_id}
    )
    spawn_background_task(tracker.task.id, _run_regenerate_page_prompt(project_id, novel_id, body.page_id, tracker))
    return ApiResponse(data={"task_id": str(tracker.task.id)})


@router.post("/{project_id}/novels/{novel_id}/match-references")
async def match_references(
    project_id: UUID,
    novel_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """根据每页的 image_prompt 智能匹配项目中的参考图"""
    existing = await find_running_task(db, project_id, "match_references", str(novel_id))
    if existing:
        return ApiResponse(data={"task_id": str(existing.id), "message": "已有正在执行的匹配参考图任务"})
    tracker = await TaskProgressTracker.create(
        db, project_id, "match_references",
        "匹配参考图", {"novel_id": str(novel_id)}
    )
    spawn_background_task(tracker.task.id, _run_match_references(project_id, novel_id, tracker))
    return ApiResponse(data={"task_id": str(tracker.task.id)})


@router.post("/{project_id}/novels/{novel_id}/generate-single-image")
async def generate_single_image(
    project_id: UUID,
    novel_id: UUID,
    body: GenerateSingleImageRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """为指定页面生成图片"""
    tracker = await TaskProgressTracker.create(
        db, project_id, "generate_single_image",
        "生成单页图片", {"novel_id": str(novel_id), "page_id": body.page_id}
    )
    spawn_background_task(tracker.task.id, _run_generate_single_image(project_id, novel_id, body.page_id, body.reference_ids, tracker))
    return ApiResponse(data={"task_id": str(tracker.task.id)})


@router.post("/{project_id}/novels/{novel_id}/generate-page-images")
async def generate_page_images(
    project_id: UUID,
    novel_id: UUID,
    body: GeneratePageImagesRequest = GeneratePageImagesRequest(),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """为已有提示词的页面生成图片"""
    existing = await find_running_task(db, project_id, "generate_page_images", str(novel_id))
    if existing:
        return ApiResponse(data={"task_id": str(existing.id), "message": "已有正在执行的生成页面图片任务"})
    tracker = await TaskProgressTracker.create(
        db, project_id, "generate_page_images",
        "生成页面图片", {"novel_id": str(novel_id)}
    )
    spawn_background_task(tracker.task.id, _run_generate_page_images(project_id, novel_id, body.reference_ids, tracker))
    return ApiResponse(data={"task_id": str(tracker.task.id)})


@router.get("/{project_id}/novels")
async def list_novels(
    project_id: UUID,
    skip: int = 0,
    limit: int = 20,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目下的小说列表"""
    service = NovelService(db)
    novels, total = await service.novel_repo.list(project_id=project_id, skip=skip, limit=limit)
    return ApiResponse(data={
        "items": [
            {
                "id": n.id,
                "title": n.title,
                "author": n.author,
                "word_count": n.word_count,
                "format": n.format,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "updated_at": n.updated_at.isoformat() if n.updated_at else None,
            }
            for n in novels
        ],
        "total": total,
        "skip": skip,
        "limit": limit,
    })


@router.get("/{project_id}/novels/{novel_id}")
async def get_novel(
    project_id: UUID,
    novel_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """获取小说详情"""
    service = NovelService(db)
    try:
        result = await service.get_novel_detail(novel_id)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{project_id}/novels/{novel_id}/preprocess")
async def preprocess_novel(
    project_id: UUID,
    novel_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """预处理小说文本"""
    existing = await find_running_task(db, project_id, "preprocess_novel", str(novel_id))
    if existing:
        return ApiResponse(data={"task_id": str(existing.id), "message": "已有正在执行的预处理任务"})
    tracker = await TaskProgressTracker.create(
        db, project_id, "preprocess_novel",
        "预处理小说", {"novel_id": str(novel_id)}
    )
    spawn_background_task(tracker.task.id, _run_preprocess_novel(project_id, novel_id, tracker))
    return ApiResponse(data={"task_id": str(tracker.task.id)})


@router.put("/{project_id}/novels/{novel_id}/text")
async def update_novel_text(
    project_id: UUID,
    novel_id: UUID,
    data: UpdateNovelTextRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """更新小说文本内容"""
    service = NovelService(db)
    try:
        result = await service.update_novel_text(novel_id, data.raw_text)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{project_id}/novels/{novel_id}/chapters")
async def list_chapters(
    project_id: UUID,
    novel_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """获取小说章节列表"""
    service = NovelService(db)
    try:
        chapters = await service.list_chapters(novel_id)
        return ApiResponse(data=chapters)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =====================================================================
# 编辑器 API
# =====================================================================

@router.get("/{project_id}/novels/{novel_id}/editor/chapters/{chapter_id}")
async def get_chapter_detail(
    project_id: UUID,
    novel_id: UUID,
    chapter_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """获取章节详情（含段落）"""
    service = NovelService(db)
    try:
        result = await service.get_chapter_detail(chapter_id)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{project_id}/novels/{novel_id}/editor/save")
async def save_editor(
    project_id: UUID,
    novel_id: UUID,
    body: EditorSaveRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """保存编辑器内容"""
    service = NovelService(db)
    try:
        result = await service.save_editor(
            chapter_id=body.chapter_id,
            paragraphs_data=[p.model_dump() for p in body.paragraphs],
            summary=body.summary,
        )
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{project_id}/novels/{novel_id}/editor/history")
async def get_version_history(
    project_id: UUID,
    novel_id: UUID,
    chapter_id: UUID = Query(..., description="章节ID"),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """获取版本历史"""
    service = NovelService(db)
    try:
        versions = await service.get_version_history(chapter_id)
        return ApiResponse(data=versions)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{project_id}/novels/{novel_id}/editor/versions/{version_id}")
async def get_version_detail(
    project_id: UUID,
    novel_id: UUID,
    version_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """获取版本详情"""
    service = NovelService(db)
    try:
        result = await service.get_version_detail(version_id)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{project_id}/novels/{novel_id}/editor/restore/{version_id}")
async def restore_version(
    project_id: UUID,
    novel_id: UUID,
    version_id: UUID,
    chapter_id: UUID = Query(..., description="章节ID"),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """恢复版本"""
    service = NovelService(db)
    try:
        result = await service.restore_version(chapter_id, version_id)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =====================================================================
# 章节管理 API
# =====================================================================

@router.put("/{project_id}/novels/{novel_id}/chapters/{chapter_id}")
async def update_chapter(
    project_id: UUID,
    novel_id: UUID,
    chapter_id: UUID,
    body: ChapterUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """更新章节信息"""
    service = NovelService(db)
    try:
        result = await service.update_chapter(chapter_id, body)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{project_id}/novels/{novel_id}/chapters/{chapter_id}/merge")
async def merge_chapters(
    project_id: UUID,
    novel_id: UUID,
    chapter_id: UUID,
    body: MergeChapterRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """合并章节（将当前章节合并到目标章节）"""
    service = NovelService(db)
    try:
        result = await service.merge_chapters(chapter_id, body.target_chapter_id)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/novels/{novel_id}/chapters/{chapter_id}/split")
async def split_chapter(
    project_id: UUID,
    novel_id: UUID,
    chapter_id: UUID,
    body: SplitChapterRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """分割章节"""
    service = NovelService(db)
    try:
        result = await service.split_chapter(chapter_id, body.split_at_paragraph_number)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/novels/{novel_id}/generate-script")
async def generate_script(
    project_id: UUID,
    novel_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """调用LLM生成脚本（章节+镜头）"""
    tracker = await TaskProgressTracker.create(
        db, project_id, "generate_script",
        "生成脚本", {"novel_id": str(novel_id)}
    )
    spawn_background_task(tracker.task.id, _run_generate_script(project_id, novel_id, tracker))
    return ApiResponse(data={"task_id": str(tracker.task.id)})


@router.get("/{project_id}/novels/{novel_id}/script")
async def get_script(
    project_id: UUID,
    novel_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """获取小说的脚本数据"""
    service = NovelService(db)
    try:
        result = await service.get_script(novel_id)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{project_id}/novels/{novel_id}/script")
async def save_script(
    project_id: UUID,
    novel_id: UUID,
    body: SaveScriptRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """保存完整的脚本数据"""
    service = NovelService(db)
    try:
        result = await service.save_script(novel_id, [ch.model_dump() for ch in body.chapters])
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/novels/{novel_id}/script/split-shot")
async def split_shot(
    project_id: UUID,
    novel_id: UUID,
    body: SplitShotRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """拆分镜头"""
    service = NovelService(db)
    try:
        from uuid import UUID as _UUID
        result = await service.split_shot(
            novel_id,
            _UUID(body.chapter_id),
            body.shot_id,
            body.content_before,
            body.content_after,
        )
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{project_id}/novels/{novel_id}/script")
async def delete_all_script(
    project_id: UUID,
    novel_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """删除所有脚本及下游数据（分镜、排版、生图提示词、参考图、漫画页图片）.

    保留：角色提取、世界观、场景、道具、建筑、服饰等资产数据不受影响。
    """
    service = NovelService(db)
    try:
        result = await service.delete_all_script_and_downstream(project_id, novel_id)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
