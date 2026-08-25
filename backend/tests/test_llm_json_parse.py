"""测试 LLM 返回 JSON 解析器 parse_llm_json 的 5 层 fallback。"""
import pytest

from app.core.llm_utils import parse_llm_json


def test_standard_json():
    assert parse_llm_json('{"a": 1}') == {"a": 1}


def test_markdown_code_fence():
    text = '```json\n{"roles": [{"name": "张三"}]}\n```'
    assert parse_llm_json(text) == {"roles": [{"name": "张三"}]}


def test_markdown_fence_without_lang():
    text = '```\n{"a": 1}\n```'
    assert parse_llm_json(text) == {"a": 1}


def test_windows_crlf_fence():
    text = '```json\r\n{"a": 1}\r\n```'
    assert parse_llm_json(text) == {"a": 1}


def test_single_quotes_python_style():
    assert parse_llm_json("{'name': '张三', 'age': 18}") == {"name": "张三", "age": 18}


def test_trailing_commas():
    assert parse_llm_json('{"a": 1, "b": [1, 2,],}') == {"a": 1, "b": [1, 2]}


def test_unescaped_newlines_in_string():
    text = '{"desc": "第一行\n第二行", "ok": true}'
    parsed = parse_llm_json(text)
    assert parsed["desc"] == "第一行\n第二行"
    assert parsed["ok"] is True


def test_broken_prefix_but_extractable_object():
    # LLM 在 JSON 前后夹带说明文字
    text = '好的，这是结果：\n{"roles": []}\n以上。'
    assert parse_llm_json(text) == {"roles": []}


def test_unparseable_raises():
    with pytest.raises(ValueError):
        parse_llm_json("完全不是 JSON 的内容")
