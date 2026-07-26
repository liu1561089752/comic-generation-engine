import logging
from app.infra.agents.base_agent import BaseAgent, AgentContext, AgentResult

logger = logging.getLogger(__name__)

class QualityScorerAgent(BaseAgent):
    """
    质量评分 Agent ⑩
    
    职责: 对生成的图片进行多维度质量评估
    V1 实现: 基于规则评分（后续可升级为 IQA 模型）
    """
    
    DIMENSIONS = ["composition", "character_integrity", "lighting", "detail", "style_consistency"]
    WEIGHTS = [0.25, 0.25, 0.15, 0.15, 0.20]  # 各维度权重
    
    async def process(self, context: AgentContext, **kwargs) -> AgentResult:
        try:
            panel_data = kwargs.get("panel_data", {})
            
            scores = []
            for dim, weight in zip(self.DIMENSIONS, self.WEIGHTS):
                score = self._score_dimension(dim, panel_data)
                scores.append({
                    "dimension": dim,
                    "score": score,
                    "weight": weight,
                    "comment": self._get_comment(dim, score),
                })
            
            overall = sum(s["score"] * s["weight"] for s in scores)
            
            if overall >= 85:
                recommendation = "best"
            elif overall >= 70:
                recommendation = "recommended"
            elif overall >= 50:
                recommendation = "acceptable"
            else:
                recommendation = "rejected"
            
            result = {
                "panel_id": panel_data.get("id", ""),
                "scores": scores,
                "overall_score": round(overall, 1),
                "defects": [],
                "recommendation": recommendation,
            }
            return AgentResult(success=True, data=result)
        except Exception as e:
            logger.error(f"QualityScorerAgent failed: {e}", exc_info=True)
            return AgentResult(success=False, error=str(e))
    
    def _score_dimension(self, dimension: str, panel_data: dict) -> float:
        """V1: 返回基础分（后续接入 CV 模型）"""
        return 75.0  # 默认中等偏上分数
    
    def _get_comment(self, dimension: str, score: float) -> str:
        if score >= 85: return "优秀"
        if score >= 70: return "良好"
        if score >= 50: return "一般"
        return "需要改进"
