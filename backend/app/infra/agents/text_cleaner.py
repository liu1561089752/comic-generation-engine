import re
import logging
from typing import List, Optional
from app.infra.agents.base_agent import BaseAgent, AgentContext, AgentResult

logger = logging.getLogger(__name__)

# CJK 统一表意文字范围
CJK_RANGE = '[\u4e00-\u9fff]'
CJK_PATTERN = re.compile(CJK_RANGE)


class TextCleanerAgent(BaseAgent):
    """
    文本清洗 Agent

    职责: 对导入的原始小说文本进行标准化预处理
    - 删除多余空行
    - 统一标点符号（全角/半角）
    - 修正常见编码错误
    - 章节边界识别
    - 段落编号
    """

    async def process(self, context: AgentContext, text: str, filename: str = "") -> AgentResult:
        try:
            # 1. 基础清洗
            cleaned = self._clean_whitespace(text)
            cleaned = self._normalize_punctuation(cleaned)
            cleaned = self._fix_encoding_issues(cleaned)

            # 2. 章节拆分
            chapters = self._split_chapters(cleaned)

            # 3. 段落编号
            paragraphs = self._number_paragraphs(cleaned)

            result = {
                "cleaned_text": cleaned,
                "chapters": chapters,
                "paragraphs": paragraphs,
                "word_count": len(cleaned.replace(" ", "")),
                "chapter_count": len(chapters),
                "paragraph_count": len(paragraphs),
            }

            return AgentResult(success=True, data=result)
        except Exception as e:
            logger.error(f"TextCleanerAgent failed: {e}", exc_info=True)
            return AgentResult(success=False, error=str(e))

    def _clean_whitespace(self, text: str) -> str:
        """删除多余空行"""
        # 将 \r\n 统一为 \n
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        # 将 3 个以上连续空行压缩为 2 个
        text = re.sub(r'\n{4,}', '\n\n\n', text)
        # 删除行首行尾空白
        lines = [line.strip() for line in text.split('\n')]
        return '\n'.join(lines)

    def _normalize_punctuation(self, text: str) -> str:
        """统一标点符号"""
        # 半角引号 → 全角
        text = self._pair_double_quotes(text)
        # 半角标点 → 全角（中文字符前后的标点转换）
        # 逗号
        text = re.sub(
            '(?<=[\u4e00-\u9fff]),(?=[\u4e00-\u9fff])',
            '\uff0c', text
        )
        # 句号
        text = re.sub(
            '(?<=[\u4e00-\u9fff])\\.(?=[\u4e00-\u9fff])',
            '\u3002', text
        )
        # 问号
        text = re.sub(
            '(?<=[\u4e00-\u9fff])\\?(?=[\u4e00-\u9fff])',
            '\uff1f', text
        )
        # 感叹号
        text = re.sub(
            '(?<=[\u4e00-\u9fff])!(?=[\u4e00-\u9fff])',
            '\uff01', text
        )
        # 冒号
        text = re.sub(
            '(?<=[\u4e00-\u9fff]):(?=[\u4e00-\u9fff])',
            '\uff1a', text
        )
        # 分号
        text = re.sub(
            '(?<=[\u4e00-\u9fff]);(?=[\u4e00-\u9fff])',
            '\uff1b', text
        )
        return text

    def _pair_double_quotes(self, text: str) -> str:
        """把半角双引号按出现顺序交替替换为全角开引号 / 闭引号。

        半角直引号本身不区分开闭，无法用两次全局 replace 区分，
        只能依赖配对状态：第 1、3、5… 次出现为开引号，第 2、4、6… 次为闭引号。
        配对状态按行重置，避免某行落单的引号把后续全文的开闭关系整体反转。
        单引号不在此处理：英文缩写撇号（don't）与引号无法可靠区分，
        误转会破坏原文，因此保留半角。
        """
        result_lines = []
        for line in text.split('\n'):
            segments = line.split('"')
            if len(segments) > 1:
                rebuilt = segments[0]
                for idx, seg in enumerate(segments[1:]):
                    rebuilt += ('“' if idx % 2 == 0 else '”') + seg
                line = rebuilt
            result_lines.append(line)
        return '\n'.join(result_lines)

    def _fix_encoding_issues(self, text: str) -> str:
        """修正常见编码错误"""
        replacements = {
            'æˆ\u2018': '我',
            'ç\u0161„': '的',
            'æ\u02c6\u0178': '是',
            'äº†': '了',
            'ä¸\u008d': '不',
            'ä½ ': '你',
            'ä»\u2013': '他',
            'å¥¹': '她',
            'æœ‰': '有',
            'è¿™': '这',
            'é‚£': '那',
            'ä¹Ÿ': '也',
            'å°±': '就',
            'éƒ½': '都',
            'è¦\u0081': '要',
        }
        for wrong, correct in replacements.items():
            text = text.replace(wrong, correct)
        return text

    def _split_chapters(self, text: str) -> List[dict]:
        """识别章节边界并拆分"""
        chapters = []
        # 常见章节标题模式
        patterns = [
            r'第[0-9一二三四五六七八九十百千]+章\s*.*',  # 第1章 / 第一章
            r'Chapter\s+\d+[\s:].*',  # Chapter 1
            r'第[0-9]+节\s*.*',  # 第1节
        ]

        lines = text.split('\n')
        current_chapter = None
        current_content = []

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            is_chapter_title = False
            for pattern in patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    if current_chapter:
                        chapters.append({
                            "title": current_chapter,
                            "content": '\n'.join(current_content),
                            "start_line": current_start,
                            "end_line": i,
                        })
                    current_chapter = line
                    current_content = []
                    current_start = i
                    is_chapter_title = True
                    break

            if not is_chapter_title:
                current_content.append(line)

        # 最后一个章节
        if current_chapter:
            chapters.append({
                "title": current_chapter,
                "content": '\n'.join(current_content),
                "start_line": current_start,
                "end_line": len(lines),
            })

        # 如果没有识别到章节，整个文本作为一个章节
        if not chapters and text.strip():
            chapters.append({
                "title": "第1章",
                "content": text.strip(),
                "start_line": 0,
                "end_line": len(lines),
            })

        return chapters

    def _number_paragraphs(self, text: str) -> List[dict]:
        """为段落编号"""
        paragraphs = []
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        for i, line in enumerate(lines):
            if line:  # 跳过空行
                paragraphs.append({
                    "id": i + 1,
                    "text": line,
                    "is_chapter_title": any(
                        re.match(p, line, re.IGNORECASE)
                        for p in [
                            r'第[0-9一二三四五六七八九十百千]+章',
                            r'Chapter\s+\d+',
                        ]
                    )
                })

        return paragraphs
