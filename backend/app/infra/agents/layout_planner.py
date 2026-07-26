import json
import logging
from typing import List, Dict, Any, Optional
from app.infra.agents.base_agent import BaseAgent, AgentContext, AgentResult
from app.infra.adapters.base_llm import ChatMessage
from app.infra.adapters.llm_adapter import LLMAdapter
from app.core.config import settings
from app.infra.prompt_loader import get_prompt

logger = logging.getLogger(__name__)


class LayoutPlannerAgent(BaseAgent):
    """
    版式规划 Agent ⑥

    职责: 将 Panel 序列编排为 Webtoon 页面布局
    - 根据 Panel 内容和节奏标记选择合适的版式模板
    - 分配每格的位置和尺寸
    - 标记页面的叙事意图

    输入:
        panels: List[dict] — Panel 序列，每个包含 text, beat, emotion 等字段
        beat_markers: Optional[List[str]] — 节奏标记列表（如 "climax", "dialogue", "transition"）

    输出:
        pages: List[dict] — 页面布局列表
    """

    BATCH_SIZE = 20

    # 版式模板 -> 格数映射
    TEMPLATE_PANEL_COUNTS = {
        "single": 1,
        "double": 2,
        "triple": 3,
        "quad": 4,
        "quint": 5,
        "cross": 2,
    }

    async def process(self, context: AgentContext, **kwargs) -> AgentResult:
        """
        处理版式规划请求。

        Args:
            context: Agent 执行上下文
            **kwargs: 需包含:
                - panels: List[dict] — Panel 对象列表
                - beat_markers: Optional[List[str]] — 节奏标记

        Returns:
            AgentResult: data 包含 pages 列表
        """
        try:
            panels: List[Dict[str, Any]] = kwargs.get("panels", [])
            if not panels:
                return AgentResult(success=False, error="panels 参数为空")

            beat_markers: Optional[List[str]] = kwargs.get("beat_markers")

            # 尝试基于规则做初步分组
            panel_groups = self._group_panels_by_beat(panels, beat_markers)

            llm = LLMAdapter(
                api_base=settings.LLM_API_BASE,
                api_key=settings.LLM_API_KEY,
                model=settings.LLM_MODEL,
            )

            all_pages: List[Dict[str, Any]] = []

            for group_index, group in enumerate(panel_groups):
                group_result = await self._process_group(
                    llm, group, group_index,
                )
                if group_result:
                    all_pages.extend(group_result)

            return AgentResult(success=True, data={
                "pages": all_pages,
                "total_panels": len(panels),
                "total_pages": len(all_pages),
            })

        except Exception as e:
            logger.error(f"LayoutPlannerAgent failed: {e}", exc_info=True)
            return AgentResult(success=False, error=str(e))

    def _group_panels_by_beat(
        self,
        panels: List[Dict[str, Any]],
        beat_markers: Optional[List[str]],
    ) -> List[List[Dict[str, Any]]]:
        """根据节奏标记对 Panel 进行初步分组"""
        if beat_markers and len(beat_markers) == len(panels):
            groups = []
            current_group = []
            for i, p in enumerate(panels):
                current_group.append(p)
                beat = beat_markers[i] if i < len(beat_markers) else ""
                # 高潮/重要场景单独成组
                if beat in ("climax", "important") and len(current_group) >= 1:
                    groups.append(current_group)
                    current_group = []
                # 每组最多 6 个 Panel（一页最多容纳）
                elif len(current_group) >= 6:
                    groups.append(current_group)
                    current_group = []
            if current_group:
                groups.append(current_group)
            return groups

        # 无节奏标记：按每页 4-6 格划分
        groups = []
        page_size = 5
        for i in range(0, len(panels), page_size):
            groups.append(panels[i:i + page_size])
        return groups

    async def _process_group(
        self,
        llm: LLMAdapter,
        panels: List[Dict[str, Any]],
        group_index: int,
    ) -> List[Dict[str, Any]]:
        """处理一组 Panel 的版式规划"""
        panel_summaries = []
        for i, p in enumerate(panels):
            text = p.get("source_text", p.get("text", ""))[:80]
            beat = p.get("beat", "")
            emotion = p.get("emotion", "")
            panel_summaries.append(
                f"Panel {i + 1}:\n"
                f"  文本: {text}...\n"
                f"  节奏: {beat or '普通'}\n"
                f"  情绪: {emotion or '中性'}"
            )

        user_message = (
            f"请将以下 {len(panels)} 个 Panel 编排为 1 个或多个 Webtoon 页面。\n"
            f"每组 Panel 数量: {len(panels)}\n\n"
            f"【Panel 列表】\n"
            f"{chr(10).join(panel_summaries)}\n\n"
            f"请选择合适的版式模板，以 JSON 数组格式返回页面布局。"
        )

        system_prompt = await get_prompt("layout_system")
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_message),
        ]

        result = await llm.chat(
            messages=messages,
            temperature=0.5,
            max_tokens=4096,
        )

        return self._parse_llm_response(result.content, group_index)

    def _parse_llm_response(
        self, content: str, group_index: int,
    ) -> List[Dict[str, Any]]:
        """解析 LLM 返回的 JSON 响应"""
        try:
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            pages = json.loads(json_str)
            if isinstance(pages, dict):
                pages = [pages]

            validated = []
            for page in pages:
                validated.append({
                    "page_number": page.get("page_number", len(validated) + 1),
                    "layout_template": page.get("layout_template", "triple"),
                    "panel_positions": page.get("panel_positions", []),
                    "page_intent": page.get("page_intent", ""),
                })
            return validated

        except (json.JSONDecodeError, IndexError) as e:
            logger.warning(f"解析 LLM 响应失败: {e}")
            return [
                {
                    "page_number": group_index + 1,
                    "layout_template": "triple",
                    "panel_positions": [],
                    "page_intent": "常规推进",
                }
            ]
