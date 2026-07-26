import json
import logging
from typing import List, Dict, Any
from app.infra.agents.base_agent import BaseAgent, AgentContext, AgentResult
from app.infra.adapters.base_llm import ChatMessage
from app.infra.adapters.llm_adapter import LLMAdapter
from app.core.config import settings
from app.infra.prompt_loader import get_prompt

logger = logging.getLogger(__name__)


class StoryboardPlannerAgent(BaseAgent):
    """
    分镜规划 Agent ④

    职责: 将 Panel 文本转化为视觉分镜方案
    - 根据文本内容设计画面构图
    - 确定视觉焦点和关键元素
    - 提供色彩基调和情绪氛围建议

    输入:
        panels: List[dict] — Panel 对象列表，每个包含 text, characters, action, emotion 等字段

    输出:
        storyboard: List[dict] — 分镜方案列表，每个包含 shot_description, composition,
                    focus, background, key_elements, color_palette, mood
    """

    BATCH_SIZE = 8

    async def process(self, context: AgentContext, **kwargs) -> AgentResult:
        """
        处理分镜规划请求。

        Args:
            context: Agent 执行上下文
            **kwargs: 需包含:
                - panels: List[dict] — Panel 对象列表

        Returns:
            AgentResult: data 包含 storyboard 列表
        """
        try:
            panels: List[Dict[str, Any]] = kwargs.get("panels", [])
            if not panels:
                return AgentResult(success=False, error="panels 参数为空")

            scene_mood = kwargs.get("scene_mood", "neutral")
            scene_location = kwargs.get("scene_location", "")

            # 分批调用 LLM，每 5-10 个 Panel 一批
            batch_size = min(self.BATCH_SIZE, max(5, len(panels) // 3 + 1))
            batches = [
                panels[i:i + batch_size]
                for i in range(0, len(panels), batch_size)
            ]

            all_storyboards: List[Dict[str, Any]] = []
            llm = LLMAdapter(
                api_base=settings.LLM_API_BASE,
                api_key=settings.LLM_API_KEY,
                model=settings.LLM_MODEL,
            )

            for batch_index, batch in enumerate(batches):
                batch_result = await self._process_batch(
                    llm, batch, batch_index, batch_size, scene_mood, scene_location,
                )
                if batch_result:
                    all_storyboards.extend(batch_result)

            return AgentResult(success=True, data={
                "storyboard": all_storyboards,
                "total_panels": len(panels),
                "batches_processed": len(batches),
            })

        except Exception as e:
            logger.error(f"StoryboardPlannerAgent failed: {e}", exc_info=True)
            return AgentResult(success=False, error=str(e))

    async def _process_batch(
        self,
        llm: LLMAdapter,
        panels: List[Dict[str, Any]],
        batch_index: int,
        batch_size: int,
        scene_mood: str,
        scene_location: str,
    ) -> List[Dict[str, Any]]:
        """处理一个批次的 Panel 分镜生成。

        batch_size 必须是 process 实际使用的动态批大小，
        否则跨批次的全局序号会跳号，误导 LLM 的连续性推理。
        """
        panel_summaries = []
        for i, p in enumerate(panels):
            panel_summaries.append(
                f"Panel {i + 1 + batch_index * batch_size}:\n"
                f"  文本: {p.get('source_text', p.get('text', ''))}\n"
                f"  人物: {', '.join(p.get('characters', []) or [])}\n"
                f"  动作: {p.get('action', '')}\n"
                f"  情绪: {p.get('emotion', '')}"
            )

        user_message = (
            f"【场景信息】\n"
            f"情绪基调: {scene_mood}\n"
            f"地点: {scene_location}\n\n"
            f"【Panel 列表】\n"
            f"{chr(10).join(panel_summaries)}\n\n"
            f"请为以上每个 Panel 生成分镜方案，以 JSON 数组格式返回。"
        )

        system_prompt = await get_prompt("storyboard_system")
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_message),
        ]

        result = await llm.chat(
            messages=messages,
            temperature=0.6,
            max_tokens=4096,
        )

        return self._parse_llm_response(result.content, len(panels))

    def _parse_llm_response(
        self, content: str, expected_count: int,
    ) -> List[Dict[str, Any]]:
        """解析 LLM 返回的 JSON 响应"""
        try:
            # 尝试从 markdown 代码块中提取 JSON
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            storyboards = json.loads(json_str)
            if isinstance(storyboards, dict):
                storyboards = [storyboards]
            if not isinstance(storyboards, list):
                raise ValueError(f"LLM 响应顶层类型不受支持: {type(storyboards).__name__}")

            # 确保每个条目包含必要字段
            validated = []
            for sb in storyboards:
                if not isinstance(sb, dict):
                    # 元素是字符串等非对象时用空字典占位，保持与 panels 的位置对应
                    sb = {}
                validated.append({
                    "shot_description": sb.get("shot_description", ""),
                    "composition": sb.get("composition", "居中构图"),
                    "focus": sb.get("focus", ""),
                    "background": sb.get("background", ""),
                    "key_elements": sb.get("key_elements", []),
                    "color_palette": sb.get("color_palette", "中性色调"),
                    "mood": sb.get("mood", "中性"),
                })
            return validated

        except (json.JSONDecodeError, IndexError, ValueError, AttributeError, TypeError) as e:
            logger.warning(f"解析 LLM 响应失败: {e}，原始内容: {content[:200]}")
            # 降级: 返回简单结构
            return [
                {
                    "shot_description": "",
                    "composition": "居中构图",
                    "focus": "",
                    "background": "",
                    "key_elements": [],
                    "color_palette": "中性色调",
                    "mood": "中性",
                }
                for _ in range(expected_count)
            ]
