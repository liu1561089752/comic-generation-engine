import asyncio
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.core.dependencies import oauth2_scheme
from app.models.user import User
from app.core.security import (
    verify_password,
    hash_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    revoke_token,
    revoke_refresh_token,
    is_refresh_token_revoked,
)
from app.infra.rate_limit import login_limiter
from app.middleware.auth import get_current_user
from app.schemas.common import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str = ""


@router.post("/login")
async def login(request: LoginRequest, raw_request: Request, db: AsyncSession = Depends(get_db)):
    """用户登录（数据库验证，带登录限流）"""
    # 登录限流：每 (IP + 用户名) 5 次 / 60 秒，防暴力破解
    client_ip = raw_request.client.host if raw_request.client else "unknown"
    limit_key = f"login:{client_ip}:{request.username}"
    if not await login_limiter.allow(limit_key):
        raise HTTPException(
            status_code=429,
            detail="登录尝试过于频繁，请稍后再试",
        )

    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    user = result.scalar_one_or_none()

    if user is None or not await asyncio.to_thread(verify_password, request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账户已被禁用")

    access_token = create_access_token(data={
        "sub": str(user.id),
        "username": user.username,
    })
    refresh_token = create_refresh_token(data={
        "sub": str(user.id),
        "username": user.username,
    })

    return ApiResponse(data={
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "username": user.username,
            "email": user.email or "",
            "is_admin": user.is_admin or False,
        },
    })


@router.post("/refresh")
async def refresh_token(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """刷新令牌"""
    payload = decode_token(request.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="无效的刷新令牌")
    # 检查 refresh token 是否已被撤销（登出后立即失效）
    if is_refresh_token_revoked(request.refresh_token):
        raise HTTPException(status_code=401, detail="刷新令牌已被撤销，请重新登录")
    try:
        user_uuid = UUID(str(payload.get("sub")))
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="无效的刷新令牌")

    result = await db.execute(
        select(User).where(User.id == user_uuid)
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已被禁用")

    user_id = str(user.id)
    username = user.username
    access_token = create_access_token(data={"sub": user_id, "username": username})
    new_refresh_token = create_refresh_token(data={"sub": user_id, "username": username})
    return ApiResponse(data={
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    })


@router.get("/me")
async def get_me(user_id: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """获取当前用户信息"""
    try:
        from uuid import UUID
        result = await db.execute(
            select(User).where(User.id == UUID(user_id))
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        return ApiResponse(data={
            "id": str(user.id),
            "username": user.username,
            "email": user.email or "",
            "is_admin": user.is_admin or False,
        })
    except Exception:
        raise HTTPException(status_code=404, detail="用户不存在")


@router.post("/logout")
async def logout(
    body: LogoutRequest = LogoutRequest(),
    token: str = Depends(oauth2_scheme),
    user_id: str = Depends(get_current_user),
):
    """登出（撤销 access token；若传入 refresh_token 则一并撤销，立即失效）"""
    revoke_token(token)
    if body.refresh_token:
        revoke_refresh_token(body.refresh_token)
    logger.info(f"用户 {user_id} 已登出，令牌已撤销")
    return ApiResponse(data={"message": "登出成功，令牌已失效"})
