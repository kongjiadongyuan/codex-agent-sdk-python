#!/usr/bin/env python3
"""Example of loading agent instructions from the filesystem.

This mirrors Claude's filesystem agent pattern using plain markdown files and
prompt composition.
"""

from __future__ import annotations

from pathlib import Path

import anyio
from _common import is_assistant_item, iter_text_fragments, stable_config_overrides

from codex_agent_sdk import CodexAgentOptions, query

AGENTS_DIR = Path(__file__).parent / "agents"


async def run_filesystem_agent(agent_name: str, user_task: str) -> None:
    agent_path = AGENTS_DIR / f"{agent_name}.md"
    if not agent_path.exists():
        raise FileNotFoundError(f"Agent file not found: {agent_path}")

    instructions = agent_path.read_text(encoding="utf-8")
    prompt = (
        f"Load this agent definition:\n\n{instructions}\n\n"
        f"Now complete the task:\n{user_task}"
    )

    options = CodexAgentOptions(
        model="gpt-5-codex",
        sandbox="workspace-write",
        ask_for_approval="on-request",
        config_overrides=stable_config_overrides(),
    )

    print(f"=== Filesystem Agent: {agent_name} ===")
    print(f"Source: {agent_path}")

    async for event in query(prompt=prompt, options=options):
        if is_assistant_item(event):
            for text in iter_text_fragments(event):
                print(f"Codex: {text}")
    print()


async def main() -> None:
    await run_filesystem_agent(
        "code-reviewer",
        "Review whether event hooks in this SDK can mutate tool execution.",
    )
    await run_filesystem_agent(
        "doc-writer",
        "Write a quick start paragraph for choosing a model in this SDK.",
    )


if __name__ == "__main__":
    anyio.run(main)
