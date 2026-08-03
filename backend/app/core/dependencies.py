"""FastAPI 依赖注入"""
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
# 归属校验依赖复用 app.core.database.get_db，保证与路由函数共享同一个 Session
from app.core.database import async_session_factory, get_db as _shared_get_db
from app.core.security import decode_token, _is_token_blacklisted

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db():
    """数据库 Session 依赖"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user_obj(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(_shared_get_db)):
    """获取当前登录用户对象（带 is_admin 等全部字段）"""
    from app.models.user import User

    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # 检查 Token 是否已被撤销（登出）
    if _is_token_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌已被撤销，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="无效的用户ID")
    user = await db.get(User, UUID(user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已被禁用")
    return user


async def require_admin(user = Depends(get_current_user_obj)):
    """管理员权限依赖"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """获取当前登录用户 ID"""
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # 检查 Token 是否已被撤销（登出）
    if _is_token_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌已被撤销，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="无效的用户ID")
    return user_id


async def require_project(
    project_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(_shared_get_db),
):
    """校验 path 中的 project_id 归属当前用户，返回 Project 对象。

    默认拒绝：project.user_id 为空/NULL 时同样拒绝，不允许"无主项目"被任意访问。
    """
    from app.models.novel import Project

    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    if str(project.user_id or "") != user_id:
        raise HTTPException(status_code=403, detail="无权访问该项目")
    return project


async def require_project_novel(
    project_id: UUID,
    novel_id: UUID,
    project = Depends(require_project),
    db: AsyncSession = Depends(_shared_get_db),
):
    """在 require_project 之上校验 novel_id 确实属于该项目，返回 Novel 对象。"""
    from app.models.novel import Novel

    result = await db.execute(
        select(Novel).where(Novel.id == novel_id, Novel.project_id == project_id)
    )
    novel = result.scalar_one_or_none()
    if novel is None:
        raise HTTPException(status_code=404, detail="小说不存在")
    return novel
