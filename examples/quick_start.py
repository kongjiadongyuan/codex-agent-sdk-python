#!/usr/bin/env python3
"""Quick start example for Codex Agent SDK.

This mirrors the Claude SDK quick start pattern with Codex options and events.
"""

import anyio
from _common import (
    is_assistant_item,
    iter_text_fragments,
    quiet_stderr,
    stable_config_overrides,
)

from codex_agent_sdk import CodexAgentOptions, query


async def main() -> None:
    options = CodexAgentOptions(
        model="gpt-5-codex",
        sandbox="workspace-write",
        ask_for_approval="on-request",
        config_overrides=stable_config_overrides(),
        stderr=quiet_stderr,
    )

    print("User: Summarize what this repository is for.")
    async for event in query(
        prompt="Summarize what this repository is for in 3 bullet points.",
        options=options,
    ):
        if is_assistant_item(event):
            for text in iter_text_fragments(event):
                print(f"Codex: {text}")


if __name__ == "__main__":
    anyio.run(main)
