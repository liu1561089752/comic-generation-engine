"""Prompt 模板管理路由 - Prompt 中心。

提供模板的增删改查、设置生效模板、编辑单个模块提示词等功能。
路由前缀由 main.py 设置为 /api/v1。
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.infra.prompt_loader import clear_prompt_cache
from app.middleware.auth import get_current_user
from app.models.prompt_template import (
    PROMPT_MODULE_DEFS,
    PromptModule,
    PromptTemplate,
)
from app.schemas.common import ApiResponse
from app.schemas.prompt_template_schema import (
    PromptModuleResponse,
    PromptModuleUpdate,
    PromptTemplateCreate,
    PromptTemplateResponse,
    PromptTemplateUpdate,
    SetActiveRequest,
)

router = APIRouter()


@router.get("/prompt-templates")
async def list_prompt_templates(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """列出所有模板（含 modules）。"""
    result = await db.execute(
        select(PromptTemplate)
        .options(selectinload(PromptTemplate.modules))
        .order_by(PromptTemplate.created_at.desc())
    )
    templates = result.scalars().all()
    return ApiResponse(
        data=[PromptTemplateResponse.model_validate(t) for t in templates]
    )


@router.post("/prompt-templates")
async def create_prompt_template(
    data: PromptTemplateCreate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """创建新模板，并自动为 PROMPT_MODULE_DEFS 中每个模块创建一个空 content 的 PromptModule。"""
    template = PromptTemplate(
        name=data.name,
        description=data.description,
        cover_image_url=data.cover_image_url,
    )
    # 预先在内存中建立 modules 关系，按定义顺序设置 sort_order
    template.modules = [
        PromptModule(
            module_key=mod_def["key"],
            module_label=mod_def["label"],
            category=mod_def["category"],
            content="",
            sort_order=idx,
        )
        for idx, mod_def in enumerate(PROMPT_MODULE_DEFS)
    ]
    db.add(template)
    await db.flush()

    # 重新查询以加载 modules 关系用于响应
    result = await db.execute(
        select(PromptTemplate)
        .options(selectinload(PromptTemplate.modules))
        .where(PromptTemplate.id == template.id)
    )
    template = result.scalar_one()
    return ApiResponse(data=PromptTemplateResponse.model_validate(template))


# 静态路由必须放在 /prompt-templates/{template_id} 之前，避免被当作 UUID 解析
@router.get("/prompt-templates/active")
async def get_active_template(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """获取当前生效的模板。"""
    result = await db.execute(
        select(PromptTemplate)
        .options(selectinload(PromptTemplate.modules))
        .where(PromptTemplate.is_active.is_(True))
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="当前没有生效的模板")
    return ApiResponse(data=PromptTemplateResponse.model_validate(template))


@router.get("/prompt-templates/module-defs")
async def get_module_defs(
    user_id: str = Depends(get_current_user),
) -> ApiResponse:
    """获取所有模块定义列表。"""
    return ApiResponse(data=PROMPT_MODULE_DEFS)


@router.get("/prompt-templates/{template_id}")
async def get_prompt_template(
    template_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """获取模板详情（含所有 modules）。"""
    result = await db.execute(
        select(PromptTemplate)
        .options(selectinload(PromptTemplate.modules))
        .where(PromptTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="模板不存在")
    return ApiResponse(data=PromptTemplateResponse.model_validate(template))


@router.put("/prompt-templates/{template_id}")
async def update_prompt_template(
    template_id: UUID,
    data: PromptTemplateUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """更新模板基本信息。"""
    result = await db.execute(
        select(PromptTemplate).where(PromptTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="模板不存在")

    if data.name is not None:
        template.name = data.name
    if data.description is not None:
        template.description = data.description
    if data.cover_image_url is not None:
        template.cover_image_url = data.cover_image_url
    await db.flush()

    # 重新查询以加载 modules 关系用于响应
    result = await db.execute(
        select(PromptTemplate)
        .options(selectinload(PromptTemplate.modules))
        .where(PromptTemplate.id == template_id)
    )
    template = result.scalar_one()
    return ApiResponse(data=PromptTemplateResponse.model_validate(template))


@router.delete("/prompt-templates/{template_id}")
async def delete_prompt_template(
    template_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """删除模板（is_default=True 的系统默认模板不允许删除）。"""
    result = await db.execute(
        select(PromptTemplate).where(PromptTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="模板不存在")
    if template.is_default:
        raise HTTPException(status_code=400, detail="系统默认模板不允许删除")

    await db.delete(template)
    # 删除模板后清除提示词缓存
    clear_prompt_cache()
    return ApiResponse(message="删除成功")


@router.post("/prompt-templates/{template_id}/activate")
async def activate_prompt_template(
    template_id: UUID,
    body: Optional[SetActiveRequest] = None,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """设置为生效模板：先将所有模板 is_active 设为 False，再将目标模板设为 True。"""
    result = await db.execute(
        select(PromptTemplate).where(PromptTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 先将所有模板置为不生效
    await db.execute(update(PromptTemplate).values(is_active=False))
    # 再将目标模板置为生效
    await db.execute(
        update(PromptTemplate)
        .where(PromptTemplate.id == template_id)
        .values(is_active=True)
    )
    # 切换生效模板后清除提示词缓存
    clear_prompt_cache()
    return ApiResponse(message="已设置为生效模板")


@router.put("/prompt-templates/{template_id}/modules/{module_key}")
async def update_prompt_module(
    template_id: UUID,
    module_key: str,
    data: PromptModuleUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """更新单个模块的提示词内容。"""
    result = await db.execute(
        select(PromptModule).where(
            PromptModule.template_id == template_id,
            PromptModule.module_key == module_key,
        )
    )
    module = result.scalar_one_or_none()
    if module is None:
        raise HTTPException(status_code=404, detail="模块不存在")

    module.content = data.content
    await db.flush()
    # 更新模块内容后清除提示词缓存
    clear_prompt_cache()
    return ApiResponse(data=PromptModuleResponse.model_validate(module))
