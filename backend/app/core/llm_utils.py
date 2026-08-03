"""Shared LLM utility functions."""
import ast
import json
import re


def parse_llm_json(content: str) -> dict:
    """Robustly parse LLM-returned JSON, tolerating single quotes,
    unquoted keys, trailing commas, unescaped newlines in string values,
    and markdown code fences.
    """
    text = content.strip()
    # str.strip("```json") 会按字符集剥离，误删 JSON 首尾的 n/o/s/j 等字符。
    # 改用正则精确移除 markdown 代码围栏（```json ... ``` 或 ``` ... ```）。
    # 兼容 Windows \r\n 换行
    text = re.sub(r'^```(?:json)?\s*\r?\n?', '', text)
    text = re.sub(r'\r?\n?```\s*$', '', text)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    try:
        result = ast.literal_eval(text)
        if isinstance(result, dict):
            return result
    except (SyntaxError, ValueError):
        pass

    try:
        fixed = text.replace("'", '"')
        fixed = re.sub(r',\s*}', '}', fixed)
        fixed = re.sub(r',\s*]', ']', fixed)
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # Fallback 4: LLM 经常在 JSON 字符串值中嵌入未转义的换行符。
    # 尝试剥离 JSON 字符串值中的字面换行 \r\n → \\n（保留语义）。
    # 方法是：在字符串值内容范围内将实换行替换为 \n 转义序列。
    try:
        fixed = _fix_unescaped_newlines_in_json(text)
        return json.loads(fixed)
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback 5: 最后的尝试 — 用正则提取可能的 JSON 对象片段
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            candidate = _fix_unescaped_newlines_in_json(match.group(0))
            return json.loads(candidate)
    except (json.JSONDecodeError, AttributeError):
        pass

    raise ValueError(f"无法解析 LLM 返回的 JSON: {text[:300]}...")


def _fix_unescaped_newlines_in_json(text: str) -> str:
    """将 JSON 字符串值中的字面换行替换为 \\n 转义序列。

    策略：遍历字符，在遇到 " 时进入/离开字符串范围。
    在字符串范围内，将所有 \r\n → \n, \n → \\n（仅当该 \n 不在 \\ 之后）。
    """
    result: list[str] = []
    in_string = False
    escape = False  # 当前字符前有反斜杠
    i = 0
    while i < len(text):
        ch = text[i]
        if escape:
            # 转义模式：什么字符都原样输出，然后退出转义
            result.append(ch)
            escape = False
            i += 1
            continue

        if ch == '\\' and in_string:
            # 字符串内的反斜杠→进入转义模式
            result.append(ch)
            escape = True
            i += 1
            continue

        if ch == '"' and not in_string:
            # 进入字符串
            in_string = True
            result.append(ch)
            i += 1
            continue

        if ch == '"' and in_string:
            # 退出字符串
            in_string = False
            result.append(ch)
            i += 1
            continue

        if in_string and ch in '\r\n':
            # 字符串内的字面换行 → 替换为 \\n
            # 跳过 \r（紧跟的 \n 会在下一轮回合被处理）
            if ch == '\r' and i + 1 < len(text) and text[i + 1] == '\n':
                i += 1  # 跳过 \r，让下一轮处理 \n
                continue
            result.append('\\n')
            i += 1
            continue

        result.append(ch)
        i += 1

    return ''.join(result)
