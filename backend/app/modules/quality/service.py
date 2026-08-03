"""Quality service - 质量检测 service (migrated from app/services/quality_service.py).

Implements short transaction pattern: AI/agent calls never hold a DB session.
Pattern: read (short session) -> close -> agent call -> (new session -> write if needed).

Key migrations vs. old app/services/quality_service.py:
- Imports use app.core.* / app.infra.* instead of app.services.* / app.adapters.* / app.config / app.database
- Agents imported from app.infra.agents.* (actual impl) instead of app.agents.* (compat re-export)
- AI-driven methods (check_consistency / score_quality / reports) use async_session_factory()
  for short-lived read sessions, so no session is held during agent calls
- Pure DB mutations (submit_review / approve_image / reject_image) still use the shared
  session from the router, matching the old interface
"""
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.agents.consistency_checker import ConsistencyCheckerAgent
from app.infra.agents.quality_scorer import QualityScorerAgent

logger = logging.getLogger(__name__)


class QualityService:
    """质量检测服务 - handles consistency checking, quality scoring, and review workflow."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.consistency_agent = ConsistencyCheckerAgent()
        self.quality_agent = QualityScorerAgent()

    # =================================================================
    # AI-driven checks (short transaction pattern: read -> close -> agent)
    # =================================================================

    async def check_consistency(self, panel_id: UUID, image_id: UUID) -> dict:
        """对 Panel 的图片做一致性检测。

        Short transaction pattern:
        1. Short read session: load panel + character appearance data
        2. Agent call (no session held)

        ``image_id`` is accepted for interface compatibility (used by the router)
        and reserved for future CV-model integration; V1 checks are rule-based.
        """
        # Panel/Scene 模型已删除，返回空结果
        return {}

    async def score_quality(self, panel_id: UUID, image_id: UUID) -> dict:
        """对 Panel 的图片做质量评分。

        Short transaction pattern:
        1. Short read session: verify panel exists
        2. Agent call (no session held)

        ``image_id`` is accepted for interface compatibility and reserved for
        future CV-model integration; V1 scoring is rule-based.
        """
        # Panel/Scene 模型已删除，返回空结果
        return {}

    async def get_consistency_report(self, panel_id: UUID, image_id: UUID) -> dict:
        """获取一致性检测报告（重新检测）"""
        return await self.check_consistency(panel_id, image_id)

    # =================================================================
    # DB-only operations (use shared session from router)
    # =================================================================

    async def list_pending_reviews(self, project_id: UUID) -> list:
        """获取待审核的 Panel 列表。"""
        # Panel 模型已删除，返回空列表
        return []

    async def submit_review(self, panel_id: UUID, action: str, note: str = "") -> dict:
        """提交审核结果: approve/reject/rework.

        D74: atomic conditional state transition to avoid TOCTOU and illegal
        state jumps.
        """
        # Panel 模型已删除，返回空结果
        return {"error": "Panel model not available"}

    async def approve_image(self, image_id: UUID, note: str = "") -> dict:
        """审核通过图片.

        D74: atomic UPDATE to avoid SELECT+setattr+flush TOCTOU.
        """
        # Image 模型已删除
        return {"error": "Image model not available"}

    async def reject_image(self, image_id: UUID, note: str = "") -> dict:
        """审核打回图片.

        D74: atomic conditional UPDATE — only non-rejected images need rejection.
        """
        # Image 模型已删除
        return {"error": "Image model not available"}

    # =================================================================
    # Report operations (composite: short read -> agent calls per panel)
    # =================================================================

    async def list_reports(self, project_id: UUID, skip: int = 0, limit: int = 20) -> dict:
        """获取质量检测报告列表。"""
        # Panel/Scene 模型已删除，返回空结果
        return {"items": [], "total": 0}

    async def get_report_detail(self, report_id: UUID) -> dict:
        """获取报告详情.

        ``report_id`` is treated as a panel_id (the report is derived from
        the panel's quality/consistency data).

        Short transaction pattern:
        1. Short read session: load panel scalar fields
        2. Agent calls (no session held)
        """
        # Panel 模型已删除，返回空结果
        return {"error": "Panel model not available"}

    async def create_report(
        self, project_id: UUID, scope: str = "all", panel_ids: Optional[list] = None
    ) -> dict:
        """创建质量检测报告。"""
        # Panel/Scene 模型已删除，返回空结果
        return {"total": 0, "reports": []}
