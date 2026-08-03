import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Token 黑名单：{token_hash: expiry_timestamp}
# 用于登出后立即使 access token 失效。
# 使用哈希存储 token 本身，避免明文存储。
_token_blacklist: dict[str, float] = {}
_BLACKLIST_CLEANUP_INTERVAL = 300.0  # 每 5 分钟清理一次过期项
_last_blacklist_cleanup = [0.0]  # 用 list 包裹以在闭包中可变


def _is_token_blacklisted(token: str) -> bool:
    """检查 token 是否已被加入黑名单。先在 O(1) 时间内检查哈希后匹配。"""
    token_hash = str(hash(token))
    expiry = _token_blacklist.get(token_hash)
    if expiry is not None:
        if time.monotonic() < expiry:
            return True
        _token_blacklist.pop(token_hash, None)
    return False


def _cleanup_blacklist():
    """清理过期的黑名单项。"""
    now = time.monotonic()
    if now - _last_blacklist_cleanup[0] < _BLACKLIST_CLEANUP_INTERVAL:
        return
    _last_blacklist_cleanup[0] = now
    expired = [h for h, exp in _token_blacklist.items() if exp <= now]
    for h in expired:
        _token_blacklist.pop(h, None)


def revoke_token(token: str):
    """将 token 加入黑名单（根据 token 的 exp 计算黑名单过期时间）。
    
    调用的路由应同时返回新 token 给客户端，避免用户被强制登出。
    """
    payload = decode_token(token)
    if payload is None:
        return
    exp = payload.get("exp")
    if exp is None:
        return
    # 黑名单保留到 token 过期时间 + 5 分钟缓冲
    ttl = max(0.0, float(exp) - time.time()) + 300.0
    token_hash = str(hash(token))
    _token_blacklist[token_hash] = time.monotonic() + ttl
    _cleanup_blacklist()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta = timedelta(hours=2)) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.APP_SECRET_KEY, algorithm="HS256")


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.APP_SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.APP_SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        return None
