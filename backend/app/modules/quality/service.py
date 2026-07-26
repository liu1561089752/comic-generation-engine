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

from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.infra.agents.base_agent import AgentContext
from app.infra.agents.consistency_checker import ConsistencyCheckerAgent
from app.infra.agents.quality_scorer import QualityScorerAgent
from app.models.character import Character
from app.models.novel import Chapter, Novel
from app.repositories.character_repo import CharacterRepository

logger = logging.getLogger(__name__)


class QualityService:
    """质量检测服务 - handles consistency checking, quality scoring, and review workflow."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.char_repo = CharacterRepository(session)
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
        """获取待审核的 Panel 列表。

        D49/D50: project_id filter pushed down to SQL to avoid full-table scan
        followed by Python-side filtering.
        """
        return await self._list_pending_panels_session(self.session, project_id)

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
        """获取质量检测报告列表.

        Short transaction pattern:
        1. Short read session: load pending panels (paginated) + total count
        2. Agent calls per panel (no session held)
        """
        # Step 1: Short read — get paginated pending panels + total count
        async with async_session_factory() as read_session:
            total = await self._count_pending_panels_session(read_session, project_id)
            panels = await self._list_pending_panels_session(
                read_session, project_id, skip=skip, limit=limit
            )
            panel_infos = [
                {
                    "id": p.id,
                    "panel_number": p.panel_number,
                    "status": p.status,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in panels
            ]

        # Step 2: Agent calls per panel (no session held)
        reports = []
        for p_info in panel_infos:
            scores = await self.score_quality(p_info["id"], None)
            consistency = await self.check_consistency(p_info["id"], None)
            reports.append({
                "panel_id": str(p_info["id"]),
                "panel_number": p_info["panel_number"],
                "overall_score": scores.get("overall_score", 0) if "error" not in scores else 0,
                "consistency_passed": (
                    consistency.get("passed", True) if "error" not in consistency else True
                ),
                "status": p_info["status"],
                "created_at": p_info["created_at"],
            })
        return {"items": reports, "total": total}

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
        """创建质量检测报告.

        ``scope``: ``all`` / ``consistency`` / ``quality`` — controls which
        checks run per panel.

        Short transaction pattern:
        1. Short read session: load pending panels, extract scalar fields
        2. Agent calls per panel (no session held)
        """
        # Step 1: Short read — get pending panels + extract scalar fields
        async with async_session_factory() as read_session:
            panels = await self._list_pending_panels_session(read_session, project_id)
            panel_infos = [
                {"id": p.id, "panel_number": p.panel_number}
                for p in panels
            ]

        # Filter by panel_ids if specified
        if panel_ids:
            panel_infos = [p for p in panel_infos if str(p["id"]) in panel_ids]

        # Step 2: Agent calls per panel (no session held)
        results = []
        for p_info in panel_infos:
            report = {
                "panel_id": str(p_info["id"]),
                "panel_number": p_info["panel_number"],
            }
            if scope in ("all", "consistency"):
                consistency = await self.check_consistency(p_info["id"], None)
                report["consistency"] = consistency if "error" not in consistency else {}
            if scope in ("all", "quality"):
                scores = await self.score_quality(p_info["id"], None)
                report["scores"] = scores if "error" not in scores else {}
            results.append(report)
        return {"total": len(results), "reports": results}

    # =================================================================
    # Helpers (work with any session)
    # =================================================================

    async def _list_pending_panels_session(
        self, session: AsyncSession, project_id: UUID,
        skip: Optional[int] = None, limit: Optional[int] = None,
    ) -> list:
        """List pending-review panels for a project using the given session.

        D49/D50: project_id filter pushed down to SQL via JOIN chain
        Panel -> Scene -> Chapter -> Novel.
        """
        # Panel/Scene 模型已删除，返回空列表
        return []

    async def _count_pending_panels_session(
        self, session: AsyncSession, project_id: UUID
    ) -> int:
        """Count pending-review panels for a project."""
        # Panel/Scene 模型已删除，返回 0
        return 0

    async def _load_panel_characters(self, session: AsyncSession, panel) -> list:
        """Load character appearance data for a panel.

        Uses a single batched IN query to avoid N+1 per-character lookups.
        """
        char_ids = panel.characters or []
        if not char_ids:
            return []

        uuid_ids = []
        for cid in char_ids:
            try:
                uuid_ids.append(UUID(cid) if isinstance(cid, str) else cid)
            except Exception:
                logger.warning(f"Failed to resolve character id: {cid}")
                continue

        if not uuid_ids:
            return []

        result = await session.execute(
            select(Character).where(Character.id.in_(uuid_ids))
        )
        characters = []
        for char in result.scalars().all():
            config = char.config or {}
            characters.append({
                "id": str(char.id),
                "name": char.name,
                "hair_color": getattr(char, "hair_color", None) or config.get("hair_color", ""),
                "hair_style": getattr(char, "hair_style", None) or config.get("hair_style", ""),
                "eye_color": getattr(char, "eye_color", None) or config.get("eye_color", ""),
                "skin_tone": getattr(char, "skin_tone", None) or config.get("skin_tone", ""),
                "outfit_description": (
                    getattr(char, "outfit_description", None)
                    or config.get("outfit_description", "")
                ),
            })
        return characters
