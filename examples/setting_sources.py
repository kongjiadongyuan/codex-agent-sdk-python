#!/usr/bin/env python3
"""Example: config-layer strategy (Codex equivalent to setting_sources).

Claude has `setting_sources` to choose user/project/local settings.
Codex uses profile/project config layering. In SDK usage, a practical approach
is to compose explicit config override layers in Python.
"""

from __future__ import annotations

from typing import Any

import anyio
from _common import is_assistant_item, iter_text_fragments, stable_config_overrides

from codex_agent_sdk import CodexAgentOptions, query

ConfigLayer = dict[str, Any]



def merge_layers(*layers: ConfigLayer) -> ConfigLayer:
    merged: ConfigLayer = {}
    for layer in layers:
        merged.update(layer)
    return merged


async def run_case(name: str, config_overrides: ConfigLayer) -> None:
    print(f"=== {name} ===")
    print(f"config_overrides={config_overrides}")

    options = CodexAgentOptions(
        sandbox="workspace-write",
        ask_for_approval="on-request",
        config_overrides=stable_config_overrides(config_overrides),
    )

    async for event in query(
        prompt="Briefly describe your current behavior constraints.",
        options=options,
    ):
        if is_assistant_item(event):
            for text in iter_text_fragments(event):
                print(f"Codex: {text}")
    print()


async def main() -> None:
    default_layer: ConfigLayer = {}

    user_like_layer: ConfigLayer = {
        "developer_instructions": "Answer concisely and focus on practical steps."
    }

    project_like_layer: ConfigLayer = {
        "model_verbosity": "low",
        "web_search": "disabled",
    }

    await run_case("Default (no layers)", merge_layers(default_layer))
    await run_case("User-only layer", merge_layers(user_like_layer))
    await run_case(
        "User + Project layer",
        merge_layers(user_like_layer, project_like_layer),
    )


if __name__ == "__main__":
    anyio.run(main)
