#!/usr/bin/env python3
"""Example of using event hooks with Codex Agent SDK.

Compared to Claude Code hook events, Codex SDK hooks are coarse and event-stream
focused (`*`, `item`, `tool`, `turn`, `error`, `log`, `thread`, `raw`).
"""

from __future__ import annotations

import anyio
from _common import event_label, stable_config_overrides

from codex_agent_sdk import CodexAgentOptions, HookAbort, query


def log_all_events(event: object) -> None:
    print(f"[hook:*] {event_label(event)}")


async def log_tool_events(event: object) -> None:
    print(f"[hook:tool] {event_label(event)}")


def stop_on_error(event: object) -> None:
    if getattr(event, "kind", None) == "error":
        raise HookAbort("Stop stream when an error event appears")


async def main() -> None:
    options = CodexAgentOptions(
        event_hooks={
            "*": [log_all_events],
            "tool": [log_tool_events],
            "error": [stop_on_error],
        },
        sandbox="workspace-write",
        ask_for_approval="on-request",
        config_overrides=stable_config_overrides(),
    )

    async for _event in query(
        prompt="List the top-level files in this repository.",
        options=options,
    ):
        pass


if __name__ == "__main__":
    anyio.run(main)
