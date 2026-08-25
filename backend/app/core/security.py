import hashlib
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 撤销列表：{标识符哈希: 过期时间(monotonic)}
# 用于 access token（按整串哈希）与 refresh token（按 jti 哈希）的统一撤销。
# 使用 sha256 而非内置 hash()：内置 hash 对 str 是进程内随机加盐，重启即失效。
_token_blacklist: dict[str, float] = {}
_BLACKLIST_CLEANUP_INTERVAL = 300.0  # 每 5 分钟清理一次过期项
_last_blacklist_cleanup = [0.0]  # 用 list 包裹以在闭包中可变


def _token_hash(identifier: str) -> str:
    """对令牌标识符做 sha256 哈希，用于黑名单存储（不存明文）。"""
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest()


def _is_blacklisted(identifier: str) -> bool:
    """检查标识符是否在撤销列表中。"""
    token_hash = _token_hash(identifier)
    expiry = _token_blacklist.get(token_hash)
    if expiry is not None:
        if time.monotonic() < expiry:
            return True
        _token_blacklist.pop(token_hash, None)
    return False


def _add_to_blacklist(identifier: str, ttl: float) -> None:
    """将标识符加入撤销列表，ttl 为存活秒数。"""
    _token_blacklist[_token_hash(identifier)] = time.monotonic() + max(0.0, ttl)
    _cleanup_blacklist()


def _cleanup_blacklist():
    """清理过期的黑名单项。"""
    now = time.monotonic()
    if now - _last_blacklist_cleanup[0] < _BLACKLIST_CLEANUP_INTERVAL:
        return
    _last_blacklist_cleanup[0] = now
    expired = [h for h, exp in _token_blacklist.items() if exp <= now]
    for h in expired:
        _token_blacklist.pop(h, None)


def is_token_blacklisted(token: str) -> bool:
    """检查 access token 是否已被撤销。"""
    return _is_blacklisted(token)


def revoke_token(token: str):
    """将 access token 加入撤销列表（根据 token 的 exp 计算过期时间）。

    调用的路由应同时返回新 token 给客户端，避免用户被强制登出。
    """
    payload = decode_token(token)
    if payload is None:
        return
    exp = payload.get("exp")
    if exp is None:
        return
    # 撤销列表保留到 token 过期时间 + 5 分钟缓冲
    ttl = max(0.0, float(exp) - time.time()) + 300.0
    _add_to_blacklist(token, ttl)


def revoke_refresh_token(refresh_token: str) -> None:
    """将 refresh token 加入撤销列表（按其 jti + exp）。

    用于登出时使 refresh token 立即失效，防止登出后仍能换取新 token。
    """
    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        return
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or exp is None:
        return
    ttl = max(0.0, float(exp) - time.time()) + 300.0
    _add_to_blacklist(jti, ttl)


def is_refresh_token_revoked(refresh_token: str) -> bool:
    """检查 refresh token 是否已被撤销（按 jti 匹配）。"""
    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        return True  # 无效 token 一律视为不可用
    jti = payload.get("jti")
    if not jti:
        return False  # 旧格式 token 无 jti，无法撤销，按未撤销处理
    return _is_blacklisted(jti)


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
    # jti：refresh token 唯一标识，用于登出后撤销
    to_encode.update({"exp": expire, "type": "refresh", "jti": str(uuid.uuid4())})
    return jwt.encode(to_encode, settings.APP_SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.APP_SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        return None
