"""兼容性重导出 - 实际认证依赖已迁移到 app.core.dependencies"""
from app.core.dependencies import oauth2_scheme, get_current_user

__all__ = ["oauth2_scheme", "get_current_user"]
