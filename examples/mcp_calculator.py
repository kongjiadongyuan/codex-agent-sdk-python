#!/usr/bin/env python3
"""Example: calculator tools via Codex dynamic tools.

Claude's in-process MCP server maps to Codex app-server dynamic tools in this
SDK scaffold.
"""

from __future__ import annotations

from typing import Any

import anyio
from _common import is_assistant_item, iter_text_fragments, stable_config_overrides

from codex_agent_sdk import CodexAgentOptions, CodexSDKClient, tool


@tool("add", "Add two numbers", {"a": {"type": "number"}, "b": {"type": "number"}})
async def add_numbers(args: dict[str, Any]) -> dict[str, Any]:
    result = float(args.get("a", 0)) + float(args.get("b", 0))
    return {
        "content": [
            {"type": "text", "text": f"{args['a']} + {args['b']} = {result}"}
        ]
    }


@tool(
    "multiply",
    "Multiply two numbers",
    {"a": {"type": "number"}, "b": {"type": "number"}},
)
async def multiply_numbers(args: dict[str, Any]) -> dict[str, Any]:
    result = float(args.get("a", 0)) * float(args.get("b", 0))
    return {
        "content": [
            {"type": "text", "text": f"{args['a']} * {args['b']} = {result}"}
        ]
    }


@tool("divide", "Divide a by b", {"a": {"type": "number"}, "b": {"type": "number"}})
async def divide_numbers(args: dict[str, Any]) -> dict[str, Any]:
    denominator = float(args.get("b", 0))
    if denominator == 0:
        return {
            "content": [
                {"type": "text", "text": "Error: division by zero is not allowed"}
            ],
            "is_error": True,
        }
    result = float(args.get("a", 0)) / denominator
    return {
        "content": [
            {"type": "text", "text": f"{args['a']} / {args['b']} = {result}"}
        ]
    }


async def main() -> None:
    options = CodexAgentOptions(
        use_app_server=True,
        dynamic_tools=[add_numbers, multiply_numbers, divide_numbers],
        model="gpt-5-codex",
        sandbox="workspace-write",
        ask_for_approval="never",
        config_overrides=stable_config_overrides(),
    )

    prompt = "Use calculator tools to compute (12 + 8) * 3 / 2."
    print(f"User: {prompt}")

    async with CodexSDKClient(options) as client:
        await client.query(prompt)
        async for event in client.receive_response():
            if is_assistant_item(event):
                for text in iter_text_fragments(event):
                    print(f"Codex: {text}")


if __name__ == "__main__":
    anyio.run(main)
