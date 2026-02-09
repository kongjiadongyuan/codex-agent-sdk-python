#!/usr/bin/env python3
"""Example of role-specific agents built on top of Codex SDK.

Codex does not currently expose Claude-style named agent registration in the
CLI protocol. This example shows a practical wrapper pattern that provides
similar developer ergonomics.
"""

from __future__ import annotations

from dataclasses import dataclass

import anyio
from _common import is_assistant_item, iter_text_fragments, stable_config_overrides

from codex_agent_sdk import CodexAgentOptions, query


@dataclass(frozen=True)
class LocalAgentDefinition:
    name: str
    description: str
    prompt: str
    model: str | None = None


async def run_agent(agent: LocalAgentDefinition, task: str) -> None:
    print(f"=== {agent.name} ===")
    print(f"Description: {agent.description}")

    options = CodexAgentOptions(
        model=agent.model or "gpt-5-codex",
        sandbox="workspace-write",
        ask_for_approval="on-request",
        config_overrides=stable_config_overrides(),
    )

    composed_prompt = (
        f"You are agent '{agent.name}'.\n"
        f"Agent instructions:\n{agent.prompt}\n\n"
        f"User request:\n{task}"
    )

    async for event in query(prompt=composed_prompt, options=options):
        if is_assistant_item(event):
            for text in iter_text_fragments(event):
                print(f"Codex: {text}")
    print()


async def main() -> None:
    code_reviewer = LocalAgentDefinition(
        name="code-reviewer",
        description="Review code for correctness and maintainability.",
        prompt=(
            "Analyze code for bugs, security issues, and maintainability risks. "
            "Give concise findings with severity and concrete fixes."
        ),
    )

    doc_writer = LocalAgentDefinition(
        name="doc-writer",
        description="Produce clear technical documentation.",
        prompt=(
            "Write practical documentation with examples, setup steps, and "
            "common troubleshooting notes."
        ),
    )

    await run_agent(
        code_reviewer,
        "Review the SDK event model and identify the most important caveat.",
    )
    await run_agent(
        doc_writer,
        "Explain how to use dynamic tools in this SDK with one short example.",
    )


if __name__ == "__main__":
    anyio.run(main)
