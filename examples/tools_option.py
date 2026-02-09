#!/usr/bin/env python3
"""Examples for Codex tool-related configuration options.

Claude's `tools=` option does not have a direct 1:1 equivalent in Codex CLI,
but you can tune tool availability through config overrides.
"""

from __future__ import annotations

import anyio
from _common import is_assistant_item, iter_text_fragments, stable_config_overrides

from codex_agent_sdk import CodexAgentOptions, query


async def run_case(title: str, options: CodexAgentOptions) -> None:
    print(f"=== {title} ===")
    async for event in query(
        prompt="What tools are currently available to you? Keep it short.",
        options=options,
    ):
        if is_assistant_item(event):
            for text in iter_text_fragments(event):
                print(f"Codex: {text}")
    print()


async def main() -> None:
    await run_case(
        "Default Tool Set",
        CodexAgentOptions(
            sandbox="workspace-write",
            ask_for_approval="on-request",
            config_overrides=stable_config_overrides(),
        ),
    )

    await run_case(
        "Disable Shell Tool",
        CodexAgentOptions(
            sandbox="workspace-write",
            ask_for_approval="on-request",
            config_overrides=stable_config_overrides(
                {"features.shell_tool": False}
            ),
        ),
    )

    await run_case(
        "Enable Live Web Search",
        CodexAgentOptions(
            sandbox="workspace-write",
            ask_for_approval="on-request",
            search=True,
            config_overrides=stable_config_overrides(),
        ),
    )


if __name__ == "__main__":
    anyio.run(main)
