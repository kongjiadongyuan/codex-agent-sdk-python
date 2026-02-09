#!/usr/bin/env python3
"""Example: plugin-like extension pattern for Codex SDK.

Codex does not expose Claude-style `plugins=[...]` in the CLI protocol.
Equivalent behavior can be implemented with dynamic tools + instructions.
"""

from __future__ import annotations

from pathlib import Path

import anyio
from _common import is_assistant_item, iter_text_fragments, stable_config_overrides

from codex_agent_sdk import CodexAgentOptions, CodexSDKClient, tool


@tool("greet", "Greet a user", {"name": {"type": "string"}})
async def greet(args: dict[str, object]) -> dict[str, object]:
    name = str(args.get("name", "friend"))
    return {
        "content": [
            {
                "type": "text",
                "text": (
                    f"Hello {name}! This greeting came from a dynamic tool "
                    "registered by the Python SDK."
                ),
            }
        ]
    }


async def main() -> None:
    plugin_asset = Path(__file__).parent / "plugins" / "demo-plugin"
    print(f"Reference plugin-like asset path: {plugin_asset}")

    options = CodexAgentOptions(
        use_app_server=True,
        dynamic_tools=[greet],
        ask_for_approval="never",
        sandbox="workspace-write",
        config_overrides=stable_config_overrides(
            {
                "developer_instructions": (
                    "When the user asks for a greeting, call the greet tool with "
                    "the requested name."
                )
            }
        ),
    )

    async with CodexSDKClient(options) as client:
        await client.query("Please greet Alice.")
        async for event in client.receive_response():
            if is_assistant_item(event):
                for text in iter_text_fragments(event):
                    print(f"Codex: {text}")


if __name__ == "__main__":
    anyio.run(main)
