#!/usr/bin/env python3
"""Example: consume partial message events from Codex JSON stream."""

from __future__ import annotations

import anyio
from _common import (
    event_label,
    is_assistant_item,
    iter_text_fragments,
    stable_config_overrides,
)

from codex_agent_sdk import CodexAgentOptions, query


async def main() -> None:
    options = CodexAgentOptions(
        model="gpt-5-codex",
        include_json_events=True,
        sandbox="workspace-write",
        ask_for_approval="on-request",
        config_overrides=stable_config_overrides(),
    )

    print("Prompt: Explain the difference between TCP and UDP in 3 short bullets.")
    print("=" * 60)

    event_count = 0
    text_fragments = 0

    async for event in query(
        prompt="Explain TCP vs UDP in 3 short bullet points.",
        options=options,
    ):
        event_count += 1
        print(f"[event] {event_label(event)}")

        if is_assistant_item(event):
            for text in iter_text_fragments(event):
                text_fragments += 1
                print(f"[partial] {text}")

    print("=" * 60)
    print(f"Total events: {event_count}")
    print(f"Assistant text fragments: {text_fragments}")


if __name__ == "__main__":
    anyio.run(main)
