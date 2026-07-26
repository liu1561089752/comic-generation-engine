import json
import logging
from typing import List, Dict, Any, Optional
from app.infra.agents.base_agent import BaseAgent, AgentContext, AgentResult
from app.infra.adapters.base_llm import ChatMessage
from app.infra.adapters.llm_adapter import LLMAdapter
from app.core.config import settings
from app.infra.prompt_loader import get_prompt

logger = logging.getLogger(__name__)


class CameraPlannerAgent(BaseAgent):
    """
    镜头规划 Agent ⑤

    职责: 确定每个 Panel 的镜头类型、景别、运镜方式
    - 根据 Panel 内容和场景情绪选择镜头
    - 应用摄影规则和漫画镜头语言
    - 保证镜头多样性，避免重复

    输入:
        panels: List[dict] — Panel 对象列表
        scene_mood: str — 场景情绪基调
        previous_cameras: List[str] — 前序 Panel 的镜头类型（用于避免重复）

    输出:
        camera_plans: List[dict] — 镜头方案列表
    """

    BATCH_SIZE = 10

    async def process(self, context: AgentContext, **kwargs) -> AgentResult:
        """
        处理镜头规划请求。

        Args:
            context: Agent 执行上下文
            **kwargs: 需包含:
                - panels: List[dict] — Panel 对象列表
                - scene_mood: str — 场景情绪
                - previous_cameras: Optional[List[str]] — 前序镜头类型

        Returns:
            AgentResult: data 包含 camera_plans 列表
        """
        try:
            panels: List[Dict[str, Any]] = kwargs.get("panels", [])
            if not panels:
                return AgentResult(success=False, error="panels 参数为空")

            scene_mood = kwargs.get("scene_mood", "neutral")
            previous_cameras: List[str] = kwargs.get("previous_cameras", [])

            # 分批调用 LLM
            batch_size = min(self.BATCH_SIZE, max(5, len(panels) // 2 + 1))
            batches = [
                panels[i:i + batch_size]
                for i in range(0, len(panels), batch_size)
            ]

            all_camera_plans: List[Dict[str, Any]] = []
            llm = LLMAdapter(
                api_base=settings.LLM_API_BASE,
                api_key=settings.LLM_API_KEY,
                model=settings.LLM_MODEL,
            )

            cumulative_cameras = list(previous_cameras)

            for batch_index, batch in enumerate(batches):
                batch_result = await self._process_batch(
                    llm, batch, batch_index, batch_size, scene_mood, cumulative_cameras,
                )
                if batch_result:
                    all_camera_plans.extend(batch_result)
                    # 记录本批次的镜头类型用于后续批次去重
                    cumulative_cameras.extend(
                        p.get("camera_type", "") for p in batch_result
                    )

            return AgentResult(success=True, data={
                "camera_plans": all_camera_plans,
                "total_panels": len(panels),
            })

        except Exception as e:
            logger.error(f"CameraPlannerAgent failed: {e}", exc_info=True)
            return AgentResult(success=False, error=str(e))

    async def _process_batch(
        self,
        llm: LLMAdapter,
        panels: List[Dict[str, Any]],
        batch_index: int,
        batch_size: int,
        scene_mood: str,
        previous_cameras: List[str],
    ) -> List[Dict[str, Any]]:
        """处理一个批次的镜头规划。

        batch_size 必须是 process 实际使用的动态批大小，
        否则跨批次的全局序号会跳号，误导 LLM 的连续性推理。
        """
        panel_summaries = []
        for i, p in enumerate(panels):
            panel_summaries.append(
                f"Panel {i + 1 + batch_index * batch_size}:\n"
                f"  文本: {p.get('source_text', p.get('text', ''))}\n"
                f"  动作: {p.get('action', '')}\n"
                f"  情绪: {p.get('emotion', '')}\n"
                f"  角色: {', '.join(p.get('characters', []) or [])}"
            )

        # 判断是否为对话场景
        is_dialogue = any(
            "说" in (p.get("source_text", p.get("text", "")) or "")
            or "道" in (p.get("source_text", p.get("text", "")) or "")
            for p in panels
        )

        prev_cam_str = ", ".join(previous_cameras[-6:]) if previous_cameras else "无"

        user_message = (
            f"【场景信息】\n"
            f"情绪基调: {scene_mood}\n"
            f"对话场景: {'是' if is_dialogue else '否'}\n"
            f"前序镜头类型（最近 6 个）: {prev_cam_str}\n\n"
            f"【Panel 列表】\n"
            f"{chr(10).join(panel_summaries)}\n\n"
            f"请为以上每个 Panel 生成镜头方案，以 JSON 数组格式返回。"
            f"注意避免连续 3 个 Panel 使用同类型镜头。"
        )

        system_prompt = await get_prompt("camera_system")
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_message),
        ]

        result = await llm.chat(
            messages=messages,
            temperature=0.7,
            max_tokens=4096,
        )

        return self._parse_llm_response(result.content, len(panels))

    def _parse_llm_response(
        self, content: str, expected_count: int,
    ) -> List[Dict[str, Any]]:
        """解析 LLM 返回的 JSON 响应"""
        try:
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            plans = json.loads(json_str)
            if isinstance(plans, dict):
                plans = [plans]
            if not isinstance(plans, list):
                raise ValueError(f"LLM 响应顶层类型不受支持: {type(plans).__name__}")

            validated = []
            for p in plans:
                if not isinstance(p, dict):
                    # 元素是字符串等非对象时用空字典占位，保持与 panels 的位置对应
                    p = {}
                validated.append({
                    "camera_type": p.get("camera_type", "medium-shot"),
                    "camera_angle": p.get("camera_angle", "eye-level"),
                    "camera_movement": p.get("camera_movement", "static"),
                    "shot_size": p.get("shot_size", "中景"),
                    "composition_rule": p.get("composition_rule", "rule-of-thirds"),
                    "transition": p.get("transition", "cut"),
                })
            return validated

        except (json.JSONDecodeError, IndexError, ValueError, AttributeError, TypeError) as e:
            logger.warning(f"解析 LLM 响应失败: {e}")
            return [
                {
                    "camera_type": "medium-shot",
                    "camera_angle": "eye-level",
                    "camera_movement": "static",
                    "shot_size": "中景",
                    "composition_rule": "rule-of-thirds",
                    "transition": "cut",
                }
                for _ in range(expected_count)
            ]
