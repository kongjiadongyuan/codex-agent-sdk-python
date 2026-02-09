"""Helpers for normalizing dynamic tool JSON schemas."""

from __future__ import annotations

from typing import Any


def normalize_tool_input_schema(input_schema: dict[str, Any]) -> dict[str, Any]:
    """Normalize tool schema to an object JSON schema accepted by Codex APIs."""
    if not isinstance(input_schema, dict):
        raise TypeError(
            "Tool input schema must be a dict representing JSON schema or properties."
        )

    schema_type = input_schema.get("type")
    if schema_type == "object":
        return dict(input_schema)

    properties = input_schema.get("properties")
    if isinstance(properties, dict):
        normalized = dict(input_schema)
        normalized.setdefault("type", "object")
        return normalized

    if isinstance(schema_type, str):
        raise ValueError(
            "Tool input schema must be object-shaped. "
            f"Received schema type {schema_type!r}."
        )

    # Shorthand: {field_name: {field_schema...}}
    return {
        "type": "object",
        "properties": dict(input_schema),
    }
