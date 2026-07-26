"""兼容性重导出 - 实际 BaseRepository 已迁移到 app.core.base_repository"""
from app.core.base_repository import BaseRepository, ModelType

__all__ = ["BaseRepository", "ModelType"]
