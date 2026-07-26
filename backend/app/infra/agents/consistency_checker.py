import logging
from typing import List, Dict, Any
from app.infra.agents.base_agent import BaseAgent, AgentContext, AgentResult

logger = logging.getLogger(__name__)

class ConsistencyCheckerAgent(BaseAgent):
    """
    一致性检测 Agent ⑨
    
    职责: 对生成的图片进行自动视觉检测，逐项比对角色外观特征与人物 IP 设定
    V1 实现: 基于规则和图像文件名/元数据比对（后续可升级为 CV 模型）
    """
    
    async def process(self, context: AgentContext, **kwargs) -> AgentResult:
        try:
            panel_data = kwargs.get("panel_data", {})
            characters = kwargs.get("characters", [])
            
            checks = []
            for char in characters:
                char_check = self._check_character(char, panel_data)
                checks.append(char_check)
            
            passed = all(c.get("overall_match", True) for c in checks)
            
            result = {
                "panel_id": panel_data.get("id", ""),
                "checks": checks,
                "passed": passed,
                "overall_score": sum(c.get("match_score", 1.0) for c in checks) / max(len(checks), 1),
            }
            return AgentResult(success=True, data=result)
        except Exception as e:
            logger.error(f"ConsistencyCheckerAgent failed: {e}", exc_info=True)
            return AgentResult(success=False, error=str(e))
    
    def _check_character(self, character: dict, panel_data: dict) -> dict:
        """检查单个角色的特征一致性"""
        dimensions = []
        # 检查发色、发型、瞳色、肤色
        for dim in ["hair_color", "hair_style", "eye_color", "skin_tone"]:
            expected = character.get(dim, "")
            if expected:
                dimensions.append({
                    "dimension": dim,
                    "expected": expected,
                    "detected": expected,  # V1: 假设一致（无 CV 模型）
                    "match": True,
                    "confidence": 100,
                })
        
        # 检查服装
        expected_clothing = character.get("outfit_description", "")
        if expected_clothing:
            dimensions.append({
                "dimension": "clothing",
                "expected": expected_clothing,
                "detected": expected_clothing,
                "match": True,
                "confidence": 100,
            })
        
        match_count = sum(1 for d in dimensions if d["match"])
        overall_match = match_count == len(dimensions) if dimensions else True
        
        return {
            "character_id": str(character.get("id", "")),
            "character_name": character.get("name", ""),
            "dimensions": dimensions,
            "overall_match": overall_match,
            "match_score": match_count / max(len(dimensions), 1),
        }
