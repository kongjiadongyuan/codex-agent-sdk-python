#!/usr/bin/env python3
"""Trio backend example for CodexSDKClient streaming."""

from __future__ import annotations

import anyio
from _common import (
    is_assistant_item,
    iter_text_fragments,
    quiet_stderr,
    stable_config_overrides,
)

from codex_agent_sdk import CodexAgentOptions, CodexSDKClient


async def multi_turn_conversation() -> None:
    async with CodexSDKClient(
        CodexAgentOptions(
            model="gpt-5-codex",
            config_overrides=stable_config_overrides(),
            stderr=quiet_stderr,
        )
    ) as client:

        print("User: What's 15 + 27?")
        await client.query("What's 15 + 27?")
        async for event in client.receive_response():
            if is_assistant_item(event):
                for text in iter_text_fragments(event):
                    print(f"Codex: {text}")

        print("User: Now divide that by 7 and round to 2 decimals.")
        await client.query("Now divide that by 7 and round to 2 decimals.")
        async for event in client.receive_response():
            if is_assistant_item(event):
                for text in iter_text_fragments(event):
                    print(f"Codex: {text}")


if __name__ == "__main__":
    try:
        import trio  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "Install trio first: pip install trio"
        ) from exc

    anyio.run(multi_turn_conversation, backend="trio")
