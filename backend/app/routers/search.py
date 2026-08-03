from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, func
from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.schemas.common import ApiResponse

router = APIRouter()


@router.get("")
async def global_search(
    q: str = Query("", min_length=1, description="搜索关键词"),
    module: str = Query("all", description="搜索范围: all/projects/novels/characters/tasks"),
    type: str = Query(None, description="(兼容) 搜索范围别名"),
    limit: int = Query(5, ge=1, le=50, description="每模块返回条数"),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """全局搜索 - 跨模块搜索项目、小说、人物、任务等（仅当前用户的项目）. """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="搜索关键词不能为空")

    # 兼容旧的 type 参数
    search_module = type or module

    keyword = f"%{q.strip()}%"
    results = {}

    # 搜索项目（仅当前用户，排除已归档）
    if search_module in ("all", "projects"):
        sql = text(
            "SELECT id, name, status, updated_at "
            "FROM projects WHERE (name LIKE :keyword OR description LIKE :keyword) "
            "AND user_id = :user_id "
            "AND archived_at IS NULL "
            "ORDER BY CASE WHEN name LIKE :exact THEN 0 ELSE 1 END, updated_at DESC "
            "LIMIT :limit"
        )
        rows = await db.execute(sql, {"keyword": keyword, "user_id": user_id, "exact": q.strip(), "limit": limit})
        projects = [
            {
                "id": str(row[0]),
                "name": row[1],
                "status": row[2],
                "updated_at": row[3].isoformat() if row[3] else None,
            }
            for row in rows
        ]
        results["projects"] = projects

    # 搜索小说（仅当前用户项目下的小说）
    if search_module in ("all", "novels"):
        sql = text(
            "SELECT n.id, n.title, n.project_id, p.name as project_name "
            "FROM novels n LEFT JOIN projects p ON n.project_id = p.id "
            "WHERE n.title LIKE :keyword AND p.user_id = :user_id AND (p.archived_at IS NULL) "
            "ORDER BY CASE WHEN n.title LIKE :exact THEN 0 ELSE 1 END, n.updated_at DESC "
            "LIMIT :limit"
        )
        rows = await db.execute(sql, {"keyword": keyword, "user_id": user_id, "exact": q.strip(), "limit": limit})
        novels = [
            {
                "id": str(row[0]),
                "title": row[1],
                "project_id": str(row[2]),
                "project_name": row[3],
            }
            for row in rows
        ]
        results["novels"] = novels

    # 搜索人物（仅当前用户项目下的人物）
    if search_module in ("all", "characters"):
        sql = text(
            "SELECT c.id, c.name, c.role_type, c.project_id, p.name as project_name "
            "FROM characters c LEFT JOIN projects p ON c.project_id = p.id "
            "WHERE c.name LIKE :keyword AND p.user_id = :user_id AND (p.archived_at IS NULL) "
            "ORDER BY CASE WHEN c.name LIKE :exact THEN 0 ELSE 1 END, c.updated_at DESC "
            "LIMIT :limit"
        )
        rows = await db.execute(sql, {"keyword": keyword, "user_id": user_id, "exact": q.strip(), "limit": limit})
        characters = [
            {
                "id": str(row[0]),
                "name": row[1],
                "role_type": row[2],
                "project_id": str(row[3]),
                "project_name": row[4],
            }
            for row in rows
        ]
        results["characters"] = characters

    # 搜索任务（仅当前用户项目的任务）
    if search_module in ("all", "tasks"):
        sql = text(
            "SELECT t.id, t.task_type, t.status, t.project_id, t.progress "
            "FROM tasks t LEFT JOIN projects p ON t.project_id = p.id "
            "WHERE (t.task_type LIKE :keyword OR CAST(t.id AS TEXT) LIKE :keyword) "
            "AND p.user_id = :user_id "
            "AND (t.project_id IS NULL OR p.archived_at IS NULL) "
            "ORDER BY CASE WHEN t.task_type LIKE :exact THEN 0 ELSE 1 END, t.created_at DESC "
            "LIMIT :limit"
        )
        rows = await db.execute(sql, {"keyword": keyword, "user_id": user_id, "exact": q.strip(), "limit": limit})
        tasks = [
            {
                "id": str(row[0]),
                "task_type": row[1],
                "status": row[2],
                "project_id": str(row[3]) if row[3] else None,
                "progress": row[4],
            }
            for row in rows
        ]
        results["tasks"] = tasks

    return ApiResponse(data=results)
