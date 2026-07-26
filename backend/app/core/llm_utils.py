"""Shared LLM utility functions."""
import ast
import json
import re


def parse_llm_json(content: str) -> dict:
    """Robustly parse LLM-returned JSON, tolerating single quotes,
    unquoted keys, trailing commas, and markdown code fences.
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

    raise ValueError(f"无法解析 LLM 返回的 JSON: {text[:300]}...")
