#!/usr/bin/env python3
"""Examples for instruction prompt configuration in Codex SDK.

Codex equivalents:
- `developer_instructions` (inline)
- `model_instructions_file` (file path)
"""

from __future__ import annotations

from pathlib import Path

import anyio
from _common import is_assistant_item, iter_text_fragments, stable_config_overrides

from codex_agent_sdk import CodexAgentOptions, query


async def run_case(title: str, options: CodexAgentOptions) -> None:
    print(f"=== {title} ===")
    async for event in query(prompt="What is 2 + 2?", options=options):
        if is_assistant_item(event):
            for text in iter_text_fragments(event):
                print(f"Codex: {text}")
    print()


async def main() -> None:
    await run_case(
        "No Extra Instructions",
        CodexAgentOptions(config_overrides=stable_config_overrides()),
    )

    await run_case(
        "Inline developer_instructions",
        CodexAgentOptions(
            config_overrides=stable_config_overrides(
                {
                    "developer_instructions": (
                        "Respond like a pirate and keep the answer short."
                    )
                }
            )
        ),
    )

    preset_file = Path(__file__).parent / "prompts" / "preset_style.md"
    await run_case(
        "model_instructions_file",
        CodexAgentOptions(
            config_overrides=stable_config_overrides(
                {"model_instructions_file": str(preset_file)}
            )
        ),
    )

    await run_case(
        "model_instructions_file + extra",
        CodexAgentOptions(
            config_overrides=stable_config_overrides(
                {
                    "model_instructions_file": str(preset_file),
                    "developer_instructions": "Always include one fun fact.",
                }
            )
        ),
    )


if __name__ == "__main__":
    anyio.run(main)
