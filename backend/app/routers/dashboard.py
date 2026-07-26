from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_, and_
from datetime import datetime, timezone

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.models.novel import Project, Novel, Chapter
from app.models.task import Task
from app.models.world import WorldBuilding
from app.models.character import Character
from app.schemas.common import ApiResponse

router = APIRouter()


@router.get("/stats")
async def get_dashboard_stats(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取 Dashboard 统计数据（仅当前用户的项目）"""

    # 获取当前用户的项目列表
    user_project_ids = select(Project.id).where(Project.user_id == user_id).scalar_subquery()

    # ===================== stats =====================
    # 总项目数
    result = await db.execute(
        select(func.count(Project.id)).where(Project.user_id == user_id)
    )
    total_projects = result.scalar() or 0

    # 进行中项目数
    result = await db.execute(
        select(func.count(Project.id)).where(
            Project.user_id == user_id,
            Project.status.in_(["draft", "planning", "generating", "editing", "active", "in_progress"]),
        )
    )
    active_projects = result.scalar() or 0

    # 本月完成章节数（仅当前用户项目下的章节）
    now = datetime.now(timezone.utc)
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(Chapter.id)).where(
            Chapter.status == "completed",
            Chapter.updated_at >= first_of_month,
            Chapter.novel_id.in_(
                select(Novel.id).where(Novel.project_id.in_(
                    select(Project.id).where(Project.user_id == user_id)
                ))
            ),
        )
    )
    monthly_chapters = result.scalar() or 0

    # 待审核图片数（仅当前用户项目下的图片）
    # Image/Panel/Scene 模型已删除，返回 0
    pending_review_images = 0

    # 累计生成的图片总数（仅当前用户项目下的图片）
    # Image/Panel/Scene 模型已删除，返回 0
    total_generated_images = 0

    # ===================== recent_projects =====================
    result = await db.execute(
        select(Project).where(Project.user_id == user_id).order_by(desc(Project.updated_at)).limit(5)
    )
    projects = result.scalars().all()

    # C15: 缓存每个项目的 stages 字典，避免 target_project 重复查询 10+ 次
    stages_cache: dict = {}
    recent_projects = []
    for p in projects:
        stages = await _get_production_stages(db, p.id)
        stages_cache[p.id] = stages
        progress = sum(s["weight"] for s in stages if s["completed"])
        recent_projects.append({
            "id": str(p.id),
            "name": p.name,
            "status": p.status,
            "description": p.description,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            "progress": progress,
            "cover_url": p.cover_image_url,
        })

    # ===================== production_progress =====================
    # 取最近项目中状态为非 completed 的第一个项目
    target_project = None
    for p in projects:
        if p.status != "completed":
            target_project = p
            break
    if target_project is None and projects:
        target_project = projects[0]

    prod_progress_data = None
    if target_project:
        stages = stages_cache.get(target_project.id) or await _get_production_stages(db, target_project.id)
        overall = sum(s["weight"] for s in stages if s["completed"])
        prod_progress_data = {
            "project_id": str(target_project.id),
            "project_name": target_project.name,
            "stages": stages,
            "overall_progress": overall,
        }

    # ===================== pending_tasks =====================
    result = await db.execute(
        select(Task).where(
            Task.project_id.in_(
                select(Project.id).where(Project.user_id == user_id)
            ),
            or_(
                and_(
                    or_(
                        Task.task_type.ilike("%qc%"),
                        Task.task_type.ilike("%quality%"),
                    ),
                    Task.status == "completed",
                ),
                Task.status == "failed",
            )
        ).order_by(Task.priority, desc(Task.created_at)).limit(10)
    )
    tasks = result.scalars().all()

    pending_tasks = []
    for t in tasks:
        if t.status == "completed":
            task_type = "review"
        elif t.status == "failed":
            task_type = "failed"
        else:
            task_type = "update"

        priority_map = {"high": "high", "urgent": "high", "normal": "medium", "low": "low"}
        priority = priority_map.get(t.priority, "medium")

        pending_tasks.append({
            "id": str(t.id),
            "type": task_type,
            "task_type": task_type,
            "title": f"{t.task_type} 任务",
            "description": t.error_message or f"任务 {t.task_type} 待处理",
            "priority": priority,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "related_url": f"/projects/{t.project_id}/quality" if t.project_id else None,
            "related_project_id": str(t.project_id) if t.project_id else None,
        })

    stats_data = {
        "total_projects": total_projects,
        "active_projects": active_projects,
        "monthly_chapters": monthly_chapters,
        "pending_review_images": pending_review_images,
        "total_generated_images": total_generated_images,
    }
    # 前端 Dashboard 直接读顶层的 total_projects 等字段，同时保留 stats 嵌套结构
    return ApiResponse(data={
        **stats_data,
        "stats": stats_data,
        "recent_projects": recent_projects,
        "production_progress": prod_progress_data,
        "pending_tasks": pending_tasks,
    })


async def _get_production_stages(db: AsyncSession, project_id):
    """检查生产各阶段是否完成"""

    # ---- novel_processing: 是否有 novel 且有章节已清洗 ----
    result = await db.execute(
        select(Novel.id).where(Novel.project_id == project_id).limit(1)
    )
    novel = result.scalar()
    novel_ok = novel is not None
    chapters_cleaned = False
    if novel_ok:
        # 一个项目可能有多本小说，必须用 IN 而不是 =，否则子查询返回多行会报错
        subq = select(Novel.id).where(Novel.project_id == project_id)
        result = await db.execute(
            select(Chapter.id).where(
                Chapter.novel_id.in_(subq),
                Chapter.status == "completed",
            ).limit(1)
        )
        chapters_cleaned = result.scalar() is not None

    # ---- world_setting: 是否有世界观设定 ----
    result = await db.execute(
        select(WorldBuilding.id).where(WorldBuilding.project_id == project_id).limit(1)
    )
    world_done = result.scalar() is not None

    # ---- character_design: 是否有角色 ----
    result = await db.execute(
        select(func.count(Character.id)).where(Character.project_id == project_id)
    )
    char_done = (result.scalar() or 0) > 0

    # 项目下的 novel_ids 子查询（多个阶段共享）
    sq_novel = select(Novel.id).where(Novel.project_id == project_id)

    # ---- story_breakdown: 是否有 scene 和 panel ----
    # Scene/Panel 模型已删除，story_done = False
    sq_chapter = select(Chapter.id).where(Chapter.novel_id.in_(sq_novel))
    story_done = False

    # ---- storyboard_layout: 是否有分页/版式数据 ----
    # Page 模型已删除，layout_done = False
    layout_done = False

    # ---- prompt_generation: 是否有 prompt ----
    # Prompt 模型已删除，prompt_done = False
    prompt_done = False

    # ---- ai_generation: 是否有生成的 images ----
    # Image 模型已删除，ai_done = False
    ai_done = False

    # ---- quality_check: 是否有质量检测数据 ----
    # Image 模型已删除，quality_done = False
    quality_done = False

    # ---- edit_export: 是否有导出记录 ----
    result = await db.execute(
        select(Task.id).where(
            Task.project_id == project_id,
            Task.task_type.ilike("%export%"),
            Task.status == "completed",
        ).limit(1)
    )
    export_done = result.scalar() is not None

    stages = [
        {"stage": "novel_processing", "label": "小说处理", "weight": 10, "completed": novel_ok and chapters_cleaned},
        {"stage": "world_setting", "label": "世界观设定", "weight": 10, "completed": world_done},
        {"stage": "character_design", "label": "角色设计", "weight": 15, "completed": char_done},
        {"stage": "story_breakdown", "label": "剧情拆解", "weight": 15, "completed": story_done},
        {"stage": "storyboard_layout", "label": "分镜版式", "weight": 15, "completed": layout_done},
        {"stage": "prompt_generation", "label": "Prompt生成", "weight": 10, "completed": prompt_done},
        {"stage": "ai_generation", "label": "AI生图", "weight": 15, "completed": ai_done},
        {"stage": "quality_check", "label": "质量检测", "weight": 5, "completed": quality_done},
        {"stage": "edit_export", "label": "编辑导出", "weight": 5, "completed": export_done},
    ]
    # 前端 Dashboard 读的是 name/status/progress，这里由 label/completed 派生，保留原字段供其他调用方使用
    for s in stages:
        s["name"] = s["label"]
        s["status"] = "completed" if s["completed"] else "pending"
        s["progress"] = 100 if s["completed"] else 0
    return stages
