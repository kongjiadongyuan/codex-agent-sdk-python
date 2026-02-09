#!/usr/bin/env python3
"""Example: dynamic tools via Codex app-server."""

import anyio
from _common import stable_config_overrides

from codex_agent_sdk import CodexAgentOptions, CodexSDKClient, tool


@tool("add", "Add two numbers", {"a": {"type": "number"}, "b": {"type": "number"}})
async def add_numbers(args):
    result = args.get("a", 0) + args.get("b", 0)
    return {"content": [{"type": "text", "text": f"Sum: {result}"}]}


async def main() -> None:
    options = CodexAgentOptions(
        dynamic_tools=[add_numbers],
        use_app_server=True,
        ask_for_approval="never",
        sandbox="workspace-write",
        config_overrides=stable_config_overrides(),
    )

    async with CodexSDKClient(options) as client:
        await client.query("Use add tool to add 2 and 3")
        async for event in client.receive_response():
            print(event)


if __name__ == "__main__":
    anyio.run(main)
