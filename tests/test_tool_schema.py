"""Tests for dynamic tool schema normalization."""

from __future__ import annotations

from typing import Any

import pytest

from codex_agent_sdk import tool
from codex_agent_sdk._internal.tool_schema import normalize_tool_input_schema


def test_normalize_shorthand_schema() -> None:
    schema = normalize_tool_input_schema({"name": {"type": "string"}})
    assert schema["type"] == "object"
    assert schema["properties"] == {"name": {"type": "string"}}


def test_normalize_object_schema_passthrough() -> None:
    original: dict[str, Any] = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
    }
    schema = normalize_tool_input_schema(original)
    assert schema == original
    assert schema is not original


def test_normalize_rejects_non_object_schema_type() -> None:
    with pytest.raises(ValueError):
        normalize_tool_input_schema({"type": "string"})


def test_tool_decorator_normalizes_schema() -> None:
    @tool("hello", "Say hello", {"name": {"type": "string"}})
    async def hello(args: dict[str, Any]) -> str:
        _ = args
        return "ok"

    assert hello.input_schema["type"] == "object"
    assert hello.input_schema["properties"] == {"name": {"type": "string"}}
