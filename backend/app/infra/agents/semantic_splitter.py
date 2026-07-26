import re
import logging
from typing import List
from app.infra.agents.base_agent import BaseAgent, AgentContext, AgentResult

logger = logging.getLogger(__name__)


class SemanticSplitterAgent(BaseAgent):
    """
    语义切句 Agent ③

    职责: 将Scene文本按语义粒度拆分为Panel
    切句策略:
    1. 对话独立成格
    2. 动作拆解
    3. 描述合并
    4. 情绪转折点切换
    """

    async def process(self, context: AgentContext, scene_text: str, scene_id: str = "", characters: List[str] = None) -> AgentResult:
        try:
            panels = self._split_into_panels(scene_text, characters or [])
            result = {
                "scene_id": scene_id,
                "panels": panels,
                "panel_count": len(panels),
            }
            return AgentResult(success=True, data=result)
        except Exception as e:
            logger.error(f"SemanticSplitterAgent failed: {e}", exc_info=True)
            return AgentResult(success=False, error=str(e))

    def _split_into_panels(self, text: str, characters: List[str]) -> List[dict]:
        """按语义规则切分为Panel"""
        # 第一步：按句子切分
        sentences = self._split_sentences(text)

        # 第二步：按规则分组为Panel
        panels = []
        buffer = []

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sentence_type = self._classify_sentence(sentence)

            # 对话独立成格
            if sentence_type == "dialogue":
                if buffer:
                    panels.append(self._make_panel(len(panels) + 1, buffer, characters))
                    buffer = []
                panels.append(self._make_panel(len(panels) + 1, [sentence], characters, panel_type="dialogue"))

            # 动作/描述句
            elif sentence_type == "action":
                if len(buffer) >= 2:  # 攒够2个非对话句 → 新Panel
                    panels.append(self._make_panel(len(panels) + 1, buffer, characters))
                    buffer = []
                buffer.append(sentence)

            # 描述句
            elif sentence_type == "description":
                if buffer and self._is_emotion_shift(sentence, buffer):
                    panels.append(self._make_panel(len(panels) + 1, buffer, characters))
                    buffer = []
                buffer.append(sentence)

            # 旁白
            else:
                buffer.append(sentence)

        # 剩余内容作为一个Panel
        if buffer:
            panels.append(self._make_panel(len(panels) + 1, buffer, characters))

        return panels

    def _split_sentences(self, text: str) -> List[str]:
        """按标点切分句子"""
        # 保留引号内容完整性
        sentences = []
        current = ""
        in_quote = False

        for char in text:
            current += char
            if char in '""「」『』':
                in_quote = not in_quote
            if not in_quote and char in '。！？!?\n':
                if current.strip():
                    sentences.append(current.strip())
                current = ""

        if current.strip():
            sentences.append(current.strip())

        return sentences

    def _classify_sentence(self, sentence: str) -> str:
        """分类句子类型: dialogue/action/description/narration"""
        # 对话检测
        if re.search(r'["""「」『』].*?["""「」『』]', sentence):
            return "dialogue"
        if re.search(r'说|道|问|答|喊|叫|告诉|回应', sentence):
            return "dialogue"

        # 动作检测
        action_words = ['走', '跑', '跳', '跪', '站', '坐', '躺', '推', '拉', '拿', '放', '举', '抬', '踢', '打', '抱', '亲', '哭', '笑']
        if any(w in sentence for w in action_words):
            return "action"

        # 描述检测
        desc_words = ['是', '有', '像', '仿佛', '似乎', '显得', '充满', '到处']
        if any(w in sentence for w in desc_words):
            return "description"

        return "narration"

    def _is_emotion_shift(self, new_sentence: str, buffer: List[str]) -> bool:
        """检测情绪转折"""
        positive = ['笑', '开心', '高兴', '喜悦', '幸福', '激动']
        negative = ['哭', '悲伤', '伤心', '痛苦', '愤怒', '害怕', '紧张']

        def get_emotion_score(text: str) -> int:
            score = 0
            for w in positive:
                if w in text: score += 1
            for w in negative:
                if w in text: score -= 1
            return score

        if not buffer:
            return False

        new_score = get_emotion_score(new_sentence)
        old_score = get_emotion_score(buffer[-1])

        return abs(new_score - old_score) >= 2

    def _make_panel(self, number: int, sentences: List[str], characters: List[str], panel_type: str = "normal") -> dict:
        """创建Panel对象"""
        text = ''.join(sentences)
        return {
            "panel_number": number,
            "text": text,
            "panel_type": panel_type,
            "characters": self._detect_characters_in_text(text, characters),
            "emotion": self._detect_emotion(text),
            "action": self._detect_action(text),
        }

    def _detect_characters_in_text(self, text: str, characters: List[str]) -> List[str]:
        """检测文本中出现的角色"""
        found = []
        for char in characters:
            if char in text:
                found.append(char)
        return found

    def _detect_emotion(self, text: str) -> str:
        """检测情绪"""
        emotions = {
            "喜": ['笑', '开心', '高兴', '快乐', '幸福'],
            "怒": ['愤怒', '生气', '恼火', '怒'],
            "哀": ['悲伤', '哭', '泪', '伤心', '难过'],
            "惧": ['害怕', '恐惧', '惊恐', '紧张', '担心'],
            "惊": ['惊讶', '震惊', '吃惊', '意外'],
            "羞": ['脸红', '害羞', '尴尬', '不好意思'],
        }
        for emotion, keywords in emotions.items():
            for kw in keywords:
                if kw in text:
                    return emotion
        return "平静"

    def _detect_action(self, text: str) -> str:
        """提取动作描述"""
        action_patterns = [
            (r'(跪|站|坐|躺|趴|蹲)',),
            (r'(走|跑|跳|爬|飞)',),
            (r'(推|拉|拿|放|举|抬|踢|打|抱|亲)',),
            (r'(哭|笑|喊|叫|唱|说)',),
        ]
        for patterns in action_patterns:
            for p in patterns:
                match = re.search(p, text)
                if match:
                    return match.group(1)
        return ""
