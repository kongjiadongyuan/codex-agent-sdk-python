#!/usr/bin/env python3
"""Example demonstrating stderr callback for Codex CLI debug output."""

from __future__ import annotations

import anyio
from _common import stable_config_overrides

from codex_agent_sdk import CodexAgentOptions, query


async def main() -> None:
    stderr_lines: list[str] = []

    def on_stderr(line: str) -> None:
        stderr_lines.append(line)
        if "error" in line.lower():
            print(f"[stderr:error] {line}")

    options = CodexAgentOptions(
        stderr=on_stderr,
        sandbox="workspace-write",
        ask_for_approval="on-request",
        config_overrides=stable_config_overrides(),
    )

    async for _event in query(prompt="What is 2 + 2?", options=options):
        pass

    print(f"Captured stderr lines: {len(stderr_lines)}")
    if stderr_lines:
        print(f"First line: {stderr_lines[0]}")


if __name__ == "__main__":
    anyio.run(main)
