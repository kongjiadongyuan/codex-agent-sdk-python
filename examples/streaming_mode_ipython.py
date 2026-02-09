#!/usr/bin/env python3
"""IPython/Jupyter-oriented streaming example for CodexSDKClient.

In notebooks, call `await ask(...)` directly.
"""

from __future__ import annotations

import anyio
from _common import (
    is_assistant_item,
    iter_text_fragments,
    quiet_stderr,
    stable_config_overrides,
)

from codex_agent_sdk import CodexAgentOptions, CodexSDKClient

client = CodexSDKClient(
    CodexAgentOptions(
        model="gpt-5-codex",
        config_overrides=stable_config_overrides(),
        stderr=quiet_stderr,
    )
)


async def ask(prompt: str) -> None:
    """Notebook-friendly helper with top-level await support."""
    print(f"User: {prompt}")
    await client.connect()
    await client.query(prompt)
    async for event in client.receive_response():
        if is_assistant_item(event):
            for text in iter_text_fragments(event):
                print(f"Codex: {text}")


async def main() -> None:
    await ask("What is 2 + 2?")
    await ask("Now multiply that result by 5.")
    await client.disconnect()


if __name__ == "__main__":
    anyio.run(main)
