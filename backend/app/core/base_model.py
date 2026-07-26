"""Base model mixins for stable entity IDs and version tracking (T9 problem 2/4)."""
from sqlalchemy import Column, String


class StableKeyMixin:
    """稳定业务键 mixin (T9 问题2).

    Provides a stable_key column that identifies an entity across regeneration
    runs, enabling upsert instead of delete-and-recreate.
    """

    stable_key = Column(String(200), nullable=True, index=True)


class VersionedMixin:
    """版本号 + stale 标记 mixin (T9 问题4).

    Tracks which upstream version an entity was generated from, allowing
    downstream entities to be marked stale when upstream changes.
    """

    source_version = Column(String(50), nullable=True)
    content_hash = Column(String(64), nullable=True)
    sync_status = Column(String(20), default="fresh")  # fresh / stale / regenerating
