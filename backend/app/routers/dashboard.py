import time

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_, and_, union_all
from datetime import datetime, timezone

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.models.novel import Project, Novel, Chapter, ScriptChapter
from app.models.task import Task
from app.models.world import WorldBuilding, SceneAsset, Prop, Building, Outfit
from app.models.character import Character, CharacterReferenceImage
from app.models.storyboard import StoryboardChapter
from app.models.layout import LayoutChapter, LayoutPage, GeneratedImage
from app.schemas.common import ApiResponse

router = APIRouter()

# O14: Dashboard 阶段进度结果缓存（进程内存，TTL 30 秒）。
# 打开 Dashboard 时最多 5 个项目的 8 工序进度会被反复计算（每项目 ~12 条 SQL），
# 缓存后 30 秒内再次请求直接复用结果，避免重复全量查询。
_stages_cache: dict[str, tuple[list, float]] = {}
_STAGES_CACHE_TTL = 30.0


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
    # O14: 升级为进程内 30s TTL 缓存，跨请求复用
    recent_projects = []
    for p in projects:
        stages = await _get_stages_cached(db, p.id)
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
    # 生产进度概览统计最新一个项目（最近更新的项目）的进度
    # projects 已按 updated_at 降序排列，取第一个即为最新项目
    target_project = projects[0] if projects else None

    prod_progress_data = None
    if target_project:
        stages = await _get_stages_cached(db, target_project.id)
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
                    Task.task_type.ilike("%qc%"),
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
            "related_url": f"/projects/{t.project_id}/tasks" if t.project_id else None,
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


async def _get_stages_cached(db: AsyncSession, project_id) -> list:
    """_get_production_stages 的 30s TTL 结果缓存（仅 Dashboard 使用）。

    key 仅依赖 project_id（结果与 db 无关），同一项目 30 秒内只全量计算一次。
    项目详情页（projects.py 的 get_project）仍直接调用 _get_production_stages，
    保证详情页看到的是实时进度。
    """
    key = str(project_id)
    now = time.monotonic()
    hit = _stages_cache.get(key)
    if hit and now - hit[1] < _STAGES_CACHE_TTL:
        return hit[0]
    stages = await _get_production_stages(db, project_id)
    _stages_cache[key] = (stages, now)
    return stages


async def _get_production_stages(db: AsyncSession, project_id):
    """检查生产各阶段进度（8 个工序）。

    规则：
    - 小说导入：导入小说（存在 Novel 记录）后完成
    - 角色设计：所有角色都生成默认形象图后完成
    - 世界观构建：世界观存在且所有场景/道具/建筑/服装资产都生成图片后完成
    - 脚本生成 / 分镜设计 / AI排版：拿到 AI 数据（对应章节表有记录）即完成
    - 画面生成：已生成漫画页数 / 总页数（允许 10%、11% 等中间进度）
    - 导出：点击过导出（存在 export 任务记录）即完成
    """
    # 项目下 novel_ids 子查询（多个阶段共享）
    sq_novel = select(Novel.id).where(Novel.project_id == project_id)

    # ---- 1. 小说导入：有小说即完成 ----
    result = await db.execute(
        select(Novel.id).where(Novel.project_id == project_id).limit(1)
    )
    novel_import_done = result.scalar() is not None

    # ---- 2. 角色设计：所有角色都有默认形象图（state_id IS NULL）时完成 ----
    char_count = (
        await db.execute(
            select(func.count(Character.id)).where(Character.project_id == project_id)
        )
    ).scalar() or 0
    character_design_done = False
    if char_count > 0:
        char_with_img = (
            await db.execute(
                select(func.count(func.distinct(CharacterReferenceImage.character_id))).where(
                    CharacterReferenceImage.character_id.in_(
                        select(Character.id).where(Character.project_id == project_id)
                    ),
                    CharacterReferenceImage.state_id.is_(None),
                )
            )
        ).scalar() or 0
        character_design_done = char_with_img >= char_count

    # ---- 3. 世界观构建：世界观存在且所有资产都生成图片时完成 ----
    world_count = (
        await db.execute(
            select(func.count(WorldBuilding.id)).where(WorldBuilding.project_id == project_id)
        )
    ).scalar() or 0
    world_building_done = False
    if world_count > 0:
        sq_world = select(WorldBuilding.id).where(WorldBuilding.project_id == project_id)

        # O14: 四类资产（场景/道具/建筑/服装）的计数合并为一条 UNION ALL 查询，
        # 原实现每类 2 条（共 8 条），合并后仅 2 条。
        def _asset_count_query(with_img: bool):
            subs = []
            for model in (SceneAsset, Prop, Building, Outfit):
                cond = model.world_id.in_(sq_world)
                if with_img:
                    cond = and_(cond, model.image_url.isnot(None), model.image_url != "")
                subs.append(select(model.id).where(cond))
            return select(func.count()).select_from(union_all(*subs).subquery())

        total_assets = (
            await db.execute(_asset_count_query(with_img=False))
        ).scalar() or 0
        assets_with_img = (
            await db.execute(_asset_count_query(with_img=True))
        ).scalar() or 0
        world_building_done = total_assets > 0 and assets_with_img >= total_assets

    # ---- 4. 脚本生成：有脚本数据即完成 ----
    script_done = (
        await db.execute(
            select(ScriptChapter.id).where(ScriptChapter.novel_id.in_(sq_novel)).limit(1)
        )
    ).scalar() is not None

    # ---- 5. 分镜设计：有分镜数据即完成 ----
    storyboard_done = (
        await db.execute(
            select(StoryboardChapter.id).where(StoryboardChapter.novel_id.in_(sq_novel)).limit(1)
        )
    ).scalar() is not None

    # ---- 6. AI排版：有排版数据即完成 ----
    layout_done = (
        await db.execute(
            select(LayoutChapter.id).where(LayoutChapter.novel_id.in_(sq_novel)).limit(1)
        )
    ).scalar() is not None

    # ---- 7. 画面生成：已生成漫画页数 / 总页数（允许中间进度） ----
    sq_layout_ch = select(LayoutChapter.id).where(LayoutChapter.novel_id.in_(sq_novel))
    total_pages = (
        await db.execute(
            select(func.count(LayoutPage.id)).where(LayoutPage.chapter_id.in_(sq_layout_ch))
        )
    ).scalar() or 0
    image_progress = 0
    if total_pages > 0:
        generated_pages = (
            await db.execute(
                select(func.count(func.distinct(GeneratedImage.page_id))).where(
                    GeneratedImage.page_id.in_(
                        select(LayoutPage.id).where(LayoutPage.chapter_id.in_(sq_layout_ch))
                    )
                )
            )
        ).scalar() or 0
        image_progress = int(round(generated_pages / total_pages * 100))

    # ---- 8. 导出：点击过导出（存在 export 任务记录）即完成 ----
    export_done = (
        await db.execute(
            select(Task.id).where(
                Task.project_id == project_id,
                Task.task_type.ilike("%export%"),
            ).limit(1)
        )
    ).scalar() is not None

    stages = [
        {"stage": "novel_import", "name": "小说导入", "weight": 12.5, "completed": novel_import_done},
        {"stage": "character_design", "name": "角色设计", "weight": 12.5, "completed": character_design_done},
        {"stage": "world_building", "name": "世界观构建", "weight": 12.5, "completed": world_building_done},
        {"stage": "script_generation", "name": "脚本生成", "weight": 12.5, "completed": script_done},
        {"stage": "storyboard", "name": "分镜设计", "weight": 12.5, "completed": storyboard_done},
        {"stage": "layout", "name": "AI排版", "weight": 12.5, "completed": layout_done},
        {"stage": "image_generation", "name": "画面生成", "weight": 12.5, "completed": image_progress >= 100, "progress": image_progress},
        {"stage": "export", "name": "导出", "weight": 12.5, "completed": export_done},
    ]
    # 前端 Dashboard 读的是 name/status/progress：
    # 画面生成允许中间进度（0 < progress < 100 → in_progress），其余工序仅 0% / 100%
    for s in stages:
        if "progress" not in s:
            s["progress"] = 100 if s["completed"] else 0
        if s["completed"]:
            s["status"] = "completed"
        elif s["progress"] > 0:
            s["status"] = "in_progress"
        else:
            s["status"] = "pending"
    return stages
