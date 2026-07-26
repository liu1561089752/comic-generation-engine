import json
import logging
import re
from typing import List, Dict, Any, Optional
from app.infra.agents.base_agent import BaseAgent, AgentContext, AgentResult
from app.infra.adapters.base_llm import ChatMessage
from app.infra.adapters.llm_adapter import LLMAdapter
from app.core.config import settings
from app.infra.prompt_loader import get_prompt

logger = logging.getLogger(__name__)


class BubblePlannerAgent(BaseAgent):
    """
    气泡规划 Agent ⑦

    职责: 识别 Panel 文本中的对话/旁白/内心独白
    - 基于规则初步分类 + LLM 精确识别
    - 分配气泡显示顺序和样式
    - 建议气泡在画面中的位置

    输入:
        panels: List[dict] — Panel 列表，每个包含 source_text 和 storyboard 信息

    输出:
        bubbles: Dict[str, List[dict]] — Panel ID 到气泡列表的映射
    """

    BATCH_SIZE = 10

    async def process(self, context: AgentContext, **kwargs) -> AgentResult:
        """
        处理气泡规划请求。

        Args:
            context: Agent 执行上下文
            **kwargs: 需包含:
                - panels: List[dict] — Panel 对象列表（含 source_text）

        Returns:
            AgentResult: data 包含 bubbles 映射
        """
        try:
            panels: List[Dict[str, Any]] = kwargs.get("panels", [])
            if not panels:
                return AgentResult(success=False, error="panels 参数为空")

            panel_bubbles: Dict[str, List[Dict[str, Any]]] = {}

            # 先用规则引擎快速处理简单 Panel
            simple_panels = []
            complex_panels = []

            for p in panels:
                text = p.get("source_text", p.get("text", ""))
                if not text:
                    panel_bubbles[self._get_panel_key(p)] = []
                    continue

                rule_based = self._rule_based_classify(text)
                # 如果规则引擎能清晰识别且 >0 个结果，直接使用
                if rule_based and self._is_rule_result_clean(rule_based):
                    panel_bubbles[self._get_panel_key(p)] = rule_based
                else:
                    complex_panels.append(p)

            # 对复杂 Panel 调用 LLM
            if complex_panels:
                llm = LLMAdapter(
                    api_base=settings.LLM_API_BASE,
                    api_key=settings.LLM_API_KEY,
                    model=settings.LLM_MODEL,
                )

                batch_size = min(self.BATCH_SIZE, len(complex_panels))
                for i in range(0, len(complex_panels), batch_size):
                    batch = complex_panels[i:i + batch_size]
                    batch_result = await self._process_batch(llm, batch)
                    for key, bubbles in batch_result.items():
                        panel_bubbles[key] = bubbles

            return AgentResult(success=True, data={
                "bubbles": panel_bubbles,
                "total_panels": len(panels),
                "llm_processed": len(complex_panels),
            })

        except Exception as e:
            logger.error(f"BubblePlannerAgent failed: {e}", exc_info=True)
            return AgentResult(success=False, error=str(e))

    def _get_panel_key(self, panel: Dict[str, Any]) -> str:
        """获取 Panel 的唯一标识"""
        return str(panel.get("id", f"panel_{id(panel)}"))

    def _rule_based_classify(self, text: str) -> List[Dict[str, Any]]:
        """基于规则的初步气泡分类"""
        bubbles = []
        order = 0

        # 提取对话（引号内容）
        # 匹配中文引号「」『』、全角弯引号（U+201C/U+201D、U+2018/U+2019）和 ASCII 直引号
        # TextCleanerAgent 会把 ASCII 双引号配对转成全角弯引号（单引号保留半角，
        # 以免破坏英文缩写），但它尚未接线到服务层，两种形态的文本都可能进来，
        # 所以全角与半角写法都要覆盖，否则规则降级路径永远失配
        dialogue_patterns = [
            r'「([^」]+)」',
            r'『([^』]+)』',
            r'“([^“”]+)”',  # 全角双引号（清洗后的文本）
            r'"([^"]+)"',  # 半角双引号（未清洗的文本）
            r'‘([^‘’]+)’',  # 全角单引号
            r"'([^']+)'",  # 半角单引号
        ]
        for pattern in dialogue_patterns:
            for match in re.finditer(pattern, text):
                order += 1
                bubbles.append({
                    "type": "dialogue",
                    "text": match.group(1),
                    "speaker": "",
                    "position_suggestion": "center",
                    "style_ref": "normal",
                    "order": order,
                })

        # 提取内心独白（心想、觉得、想道等）
        # 句末终止符同时兼容全角与半角，未经清洗的文本用的是半角句读
        thought_patterns = [
            r'(?:心想|心里想|暗自想|想道)[：:，,]\s*(.+?)(?:[。！？；;.!?]|$)',
            r'(?:觉得|感到)[：:，,]\s*(.+?)(?:[。！？；;.!?]|$)',
        ]
        for pattern in thought_patterns:
            for match in re.finditer(pattern, text):
                order += 1
                bubbles.append({
                    "type": "inner_thought",
                    "text": match.group(1),
                    "speaker": "",
                    "position_suggestion": "top",
                    "style_ref": "thought",
                    "order": order,
                })

        # 提取旁白（时间/地点交代等）
        # 断句字符集同时兼容全角与半角句读
        narration_patterns = [
            r'(?:这时|此时|那天|这天|当晚|第二天|与此同时|另一边)([^。！？.!?]{4,})',
        ]
        for pattern in narration_patterns:
            for match in re.finditer(pattern, text):
                order += 1
                bubbles.append({
                    "type": "narration",
                    "text": match.group(0),
                    "speaker": "",
                    "position_suggestion": "top",
                    "style_ref": "narration",
                    "order": order,
                })

        return bubbles

    def _is_rule_result_clean(self, bubbles: List[Dict[str, Any]]) -> bool:
        """判断规则引擎结果是否足够清晰"""
        if not bubbles:
            return False
        # 如果规则引擎找到了明确的对话/内心独白，视为清晰
        has_dialogue = any(b["type"] == "dialogue" for b in bubbles)
        return has_dialogue

    async def _process_batch(
        self,
        llm: LLMAdapter,
        panels: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """处理一个批次的复杂 Panel 气泡识别"""
        panel_inputs = []
        for i, p in enumerate(panels):
            text = p.get("source_text", p.get("text", ""))
            storyboard = p.get("storyboard", {})
            panel_inputs.append(
                f"Panel {i + 1}:\n"
                f"  原始文本: {text}\n"
                f"  画面描述: {storyboard.get('shot_description', '')}"
            )

        user_message = (
            f"请分析以下 Panel 文本，识别其中的对话、内心独白和旁白。\n\n"
            f"{chr(10).join(panel_inputs)}\n\n"
            f"请以 JSON 对象格式返回，key 为 Panel 序号，value 为气泡数组。"
        )

        system_prompt = await get_prompt("bubble_system")
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_message),
        ]

        result = await llm.chat(
            messages=messages,
            temperature=0.3,
            max_tokens=4096,
        )

        return self._parse_llm_response(result.content, panels)

    def _parse_llm_response(
        self, content: str, panels: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """解析 LLM 返回的 JSON 响应"""
        result: Dict[str, List[Dict[str, Any]]] = {}

        try:
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            parsed = json.loads(json_str)

            # 提示词未约束顶层必须是对象，LLM 可能返回数组，按位置映射为序号
            if isinstance(parsed, list):
                parsed = {str(i + 1): item for i, item in enumerate(parsed)}
            if not isinstance(parsed, dict):
                raise ValueError(f"LLM 响应顶层类型不受支持: {type(parsed).__name__}")

            # 解析为 panel_key -> bubbles 映射
            for key, bubbles_data in parsed.items():
                if isinstance(bubbles_data, list):
                    validated = []
                    for b in bubbles_data:
                        if not isinstance(b, dict):
                            continue
                        validated.append({
                            "type": b.get("type", "narration"),
                            "text": b.get("text", ""),
                            "speaker": b.get("speaker", ""),
                            "position_suggestion": b.get("position_suggestion", "center"),
                            "style_ref": b.get("style_ref", "normal"),
                            "order": b.get("order", len(validated) + 1),
                        })
                    # key 可能是 "1" / "Panel 1" / "panel_2" 等形式，从中提取序号；
                    # 提取不到就跳过，不能默认落到 panels[0] 上互相覆盖
                    match = re.search(r'\d+', str(key))
                    if not match:
                        logger.warning(f"LLM 返回的 key 无法解析为 Panel 序号: {key}")
                        continue
                    panel_index = int(match.group()) - 1
                    if 0 <= panel_index < len(panels):
                        panel_key = self._get_panel_key(panels[panel_index])
                        result[panel_key] = validated

        except (json.JSONDecodeError, IndexError, ValueError, AttributeError, TypeError) as e:
            logger.warning(f"解析 LLM 响应失败: {e}")
            # 降级: 对每个 Panel 用规则重试
            for p in panels:
                key = self._get_panel_key(p)
                text = p.get("source_text", p.get("text", ""))
                result[key] = self._rule_based_classify(text)

        # LLM 未覆盖到的 Panel 补规则降级结果，避免整批 Panel 静默丢失气泡
        for p in panels:
            key = self._get_panel_key(p)
            if key not in result:
                result[key] = self._rule_based_classify(
                    p.get("source_text", p.get("text", ""))
                )

        return result
