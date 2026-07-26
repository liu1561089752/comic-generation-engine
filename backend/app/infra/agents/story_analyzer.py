import re
import json
import logging
from typing import List, Optional
from app.infra.agents.base_agent import BaseAgent, AgentContext, AgentResult

logger = logging.getLogger(__name__)


class StoryAnalyzerAgent(BaseAgent):
    """
    剧情分析 Agent ②

    职责: 从章节文本中提取Scene结构
    - 识别场景边界（时间/地点切换）
    - 提取人物、地点、时间、情绪
    - 识别情节节点（开端/发展/高潮/结局）
    """

    async def process(self, context: AgentContext, chapter_text: str, chapter_title: str = "") -> AgentResult:
        try:
            scenes = self._extract_scenes(chapter_text)

            # 提取情节结构
            plot_structure = self._extract_plot_structure(scenes, chapter_text)

            result = {
                "chapter_title": chapter_title,
                "scenes": scenes,
                "plot_structure": plot_structure,
            }

            return AgentResult(success=True, data=result)
        except Exception as e:
            logger.error(f"StoryAnalyzerAgent failed: {e}", exc_info=True)
            return AgentResult(success=False, error=str(e))

    def _extract_scenes(self, text: str) -> List[dict]:
        """基于规则提取场景（规则引擎版本，后续可升级为LLM版本）"""
        scenes = []
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]

        current_scene = None
        scene_num = 0

        # 场景切换关键词
        scene_markers = [
            r'(?:这时|此时|突然|与此同时|另一边|与此同时)',
            r'(?:到了|来到|走进|离开|回到)',
            r'(?:第二天|次日|当天晚上|第二天早上|傍晚|深夜)',
            r'(?:在.*?(?:里|中|上|前))',
        ]

        for i, para in enumerate(paragraphs):
            # 检查是否场景切换
            is_new_scene = False
            for marker in scene_markers:
                if re.search(marker, para):
                    is_new_scene = True
                    break

            if is_new_scene or current_scene is None:
                if current_scene:
                    scenes.append(current_scene)
                scene_num += 1
                current_scene = {
                    "scene_number": scene_num,
                    "description": para[:100],
                    "start_paragraph": i + 1,
                    "characters": self._extract_characters(para),
                    "location": self._extract_location(para),
                    "mood": self._extract_mood(para),
                }

            if current_scene:
                current_scene["end_paragraph"] = i + 1

        # 最后一个场景
        if current_scene:
            scenes.append(current_scene)

        # 如果没有识别出场景，整个文本作为一个场景
        if not scenes and paragraphs:
            scenes.append({
                "scene_number": 1,
                "description": paragraphs[0][:100],
                "start_paragraph": 1,
                "end_paragraph": len(paragraphs),
                "characters": [],
                "location": "",
                "mood": "neutral",
            })

        return scenes

    def _extract_characters(self, text: str) -> List[str]:
        """提取人物（简单规则：找到的人名）"""
        characters = []
        # 常见人称代词
        pronouns = ['我', '你', '他', '她', '它', '我们', '你们', '他们', '她们']
        # 注意：这里的完整实现需要结合人物IP数据库
        # 目前返回空列表，由上层服务填充
        return characters

    def _extract_location(self, text: str) -> str:
        """提取地点"""
        match = re.search(r'在(.+?)(?:里|中|上|前|的)', text)
        if match:
            return match.group(1)
        return ""

    def _extract_mood(self, text: str) -> str:
        """提取情绪基调"""
        mood_keywords = {
            "紧张": ["紧张", "危险", "危机", "惊恐", "害怕"],
            "悲伤": ["悲伤", "哭泣", "泪", "伤心", "难过"],
            "欢乐": ["欢乐", "开心", "笑", "快乐", "幸福"],
            "愤怒": ["愤怒", "生气", "恼火", "怒"],
            "平静": ["平静", "安静", "宁静", "平和"],
            "悬疑": ["奇怪", "诡异", "神秘", "不解"],
        }

        for mood, keywords in mood_keywords.items():
            for kw in keywords:
                if kw in text:
                    return mood
        return "neutral"

    def _extract_plot_structure(self, scenes: List[dict], text: str) -> dict:
        """提取情节结构"""
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        total = len(paragraphs)

        return {
            "beginning": paragraphs[0] if paragraphs else "",
            "development": paragraphs[total // 3] if total > 2 else "",
            "climax": paragraphs[total // 2] if total > 1 else "",
            "ending": paragraphs[-1] if paragraphs else "",
        }
