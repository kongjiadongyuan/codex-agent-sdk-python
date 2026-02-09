#!/usr/bin/env python3
"""Example: local budget guard pattern for Codex SDK.

Codex SDK does not currently expose a `max_budget_usd` option. This example
shows a practical guardrail that caps stream length by event count.
"""

from __future__ import annotations

import anyio
from _common import is_assistant_item, iter_text_fragments, stable_config_overrides

from codex_agent_sdk import CodexAgentOptions, HookAbort, query


class EventBudget:
    def __init__(self, max_events: int):
        self.max_events = max_events
        self.seen_events = 0

    def on_event(self, _event: object) -> None:
        self.seen_events += 1
        if self.seen_events > self.max_events:
            raise HookAbort(
                f"Event budget exceeded ({self.seen_events}/{self.max_events})"
            )


async def run_without_budget() -> None:
    print("=== Without Local Budget Guard ===")
    options = CodexAgentOptions(config_overrides=stable_config_overrides())
    async for event in query(prompt="What is 2 + 2?", options=options):
        if is_assistant_item(event):
            for text in iter_text_fragments(event):
                print(f"Codex: {text}")
    print()


async def run_with_budget(max_events: int) -> None:
    print(f"=== With Local Event Budget ({max_events}) ===")
    budget = EventBudget(max_events=max_events)
    options = CodexAgentOptions(
        event_hooks={"*": [budget.on_event]},
        config_overrides=stable_config_overrides(),
    )

    try:
        async for event in query(
            prompt="Read README.md and summarize it in detail.",
            options=options,
        ):
            if is_assistant_item(event):
                for text in iter_text_fragments(event):
                    print(f"Codex: {text}")
    except HookAbort as exc:
        print(f"Stopped by budget guard: {exc}")
    print()


async def main() -> None:
    await run_without_budget()
    await run_with_budget(max_events=25)


if __name__ == "__main__":
    anyio.run(main)
