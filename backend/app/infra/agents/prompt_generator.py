import logging
from typing import Dict, Any, Optional
from app.infra.agents.base_agent import BaseAgent, AgentContext, AgentResult

logger = logging.getLogger(__name__)


class PromptGeneratorAgent(BaseAgent):
    """
    Prompt 生成 Agent ⑧

    职责: 聚合所有上游数据，组装 10 层结构化 Prompt
    实现方式: 纯模板引擎 + 数据聚合器，无需 LLM
    """

    LAYER_ORDER = [
        "character", "environment", "action", "emotion",
        "camera", "lighting", "composition",
        "webtoon_style", "bubble", "negative"
    ]

    async def process(self, context: AgentContext, **kwargs) -> AgentResult:
        """
        输入参数:
        - panel_data: dict - Panel 数据（角色、动作、情绪、镜头等）
        - character_data: dict - 角色设定
        - scene_data: dict - 场景设定
        - style_data: dict - 画风模板
        - bubble_data: list - 气泡文本
        """
        try:
            panel = kwargs.get("panel_data", {})
            character = kwargs.get("character_data", {})
            scene = kwargs.get("scene_data", {})
            style = kwargs.get("style_data", {})
            bubbles = kwargs.get("bubble_data", [])

            layers = {}

            # Layer 1: Character
            layers["character"] = self._build_character_layer(character, panel)
            # Layer 2: Environment
            layers["environment"] = self._build_environment_layer(scene)
            # Layer 3: Action
            layers["action"] = self._build_action_layer(panel)
            # Layer 4: Emotion
            layers["emotion"] = self._build_emotion_layer(panel)
            # Layer 5: Camera
            layers["camera"] = self._build_camera_layer(panel)
            # Layer 6: Lighting
            layers["lighting"] = self._build_lighting_layer(scene, panel)
            # Layer 7: Composition
            layers["composition"] = self._build_composition_layer(panel)
            # Layer 8: Webtoon Style
            layers["webtoon_style"] = self._build_style_layer(style)
            # Layer 9: Bubble
            layers["bubble"] = self._build_bubble_layer(bubbles)
            # Layer 10: Negative
            layers["negative"] = self._build_negative_layer(style)

            # 合并为完整 Prompt
            merged = self._merge_prompt(layers)

            result = {
                "layers": layers,
                "full_prompt": merged["prompt"],
                "negative_prompt": layers["negative"],
                "params": self._get_default_params(style),
            }

            return AgentResult(success=True, data=result)
        except Exception as e:
            logger.error(f"PromptGeneratorAgent failed: {e}", exc_info=True)
            return AgentResult(success=False, error=str(e))

    def _build_character_layer(self, char: dict, panel: dict) -> str:
        parts = []
        if char.get("name"):
            parts.append(char["name"])
        if char.get("hair_color") and char.get("hair_style"):
            parts.append(f"{char['hair_color']} {char['hair_style']}")
        if char.get("eye_color"):
            parts.append(f"{char['eye_color']} eyes")
        if char.get("skin_tone"):
            parts.append(f"{char['skin_tone']} skin")
        if char.get("key_features"):
            parts.append(char["key_features"])
        if char.get("outfit_description"):
            parts.append(f"wearing {char['outfit_description']}")
        return ", ".join(parts) if parts else "a person"

    def _build_environment_layer(self, scene: dict) -> str:
        parts = []
        if scene.get("location"):
            parts.append(f"at {scene['location']}")
        if scene.get("weather"):
            parts.append(scene["weather"])
        if scene.get("time_of_day"):
            parts.append(scene["time_of_day"])
        if scene.get("atmosphere"):
            parts.append(scene["atmosphere"])
        return ", ".join(parts) if parts else "simple background"

    def _build_action_layer(self, panel: dict) -> str:
        action = panel.get("action", "")
        if action:
            return action
        return "standing still"

    def _build_emotion_layer(self, panel: dict) -> str:
        emotion = panel.get("emotion", "")
        if emotion:
            return f"expression: {emotion}, mood: {emotion}"
        return "neutral expression"

    def _build_camera_layer(self, panel: dict) -> str:
        camera_type = panel.get("camera_type", "medium shot")
        angle = panel.get("camera_angle", "eye level")
        return f"{camera_type}, {angle} view"

    def _build_lighting_layer(self, scene: dict, panel: dict) -> str:
        lighting = scene.get("lighting", "natural lighting")
        return lighting

    def _build_composition_layer(self, panel: dict) -> str:
        comp = panel.get("composition", "rule of thirds")
        return f"{comp}, centered subject"

    def _build_style_layer(self, style: dict) -> str:
        parts = []
        if style.get("art_style"):
            parts.append(style["art_style"])
        if style.get("coloring_style"):
            parts.append(style["coloring_style"])
        if style.get("lineart_style"):
            parts.append(style["lineart_style"])
        return ", ".join(parts) if parts else "Webtoon style, semi-realistic, clean lines"

    def _build_bubble_layer(self, bubbles: list) -> str:
        if not bubbles:
            return ""
        texts = [b.get("text", "") for b in bubbles if b.get("text")]
        return "Speech bubble: " + " | ".join(texts) if texts else ""

    def _build_negative_layer(self, style: dict) -> str:
        base = "nsfw, low quality, blurry, distorted hands, extra fingers, bad anatomy"
        if style.get("negative_prompt"):
            base += ", " + style["negative_prompt"]
        return base

    def _merge_prompt(self, layers: dict) -> dict:
        """合并为最终 Prompt"""
        parts = []
        for layer_name in self.LAYER_ORDER:
            content = layers.get(layer_name, "").strip()
            if content and layer_name != "negative":
                parts.append(content)

        prompt = ", ".join(parts)
        # 限制长度
        if len(prompt) > 500:
            prompt = prompt[:497] + "..."

        return {"prompt": prompt}

    def _get_default_params(self, style: dict) -> dict:
        return {
            "width": style.get("width", 1080),
            "height": style.get("height", 1440),
            "steps": 30,
            "cfg_scale": 7.5,
            "seed": -1,
        }
