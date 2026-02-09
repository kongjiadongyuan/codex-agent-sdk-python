#!/usr/bin/env python3
"""Example: approval callbacks in app-server mode.

This is the closest Codex equivalent to Claude's `can_use_tool` permission
callback. Callbacks are invoked only when Codex asks for approvals.
"""

from __future__ import annotations

import anyio
from _common import (
    event_label,
    is_assistant_item,
    iter_text_fragments,
    stable_config_overrides,
)

from codex_agent_sdk import CodexAgentOptions, CodexSDKClient


def approve_command(payload: dict[str, object]) -> str:
    command = payload.get("command")
    if isinstance(command, str) and "rm -rf" in command:
        print(f"[approval:command] deny -> {command}")
        return "deny"
    print(f"[approval:command] accept -> {command}")
    return "accept"


def approve_file_change(payload: dict[str, object]) -> str:
    target = payload.get("path") or payload.get("filePath")
    if isinstance(target, str) and target.startswith("/etc/"):
        print(f"[approval:file_change] deny -> {target}")
        return "deny"
    print(f"[approval:file_change] accept -> {target}")
    return "accept"


async def main() -> None:
    options = CodexAgentOptions(
        use_app_server=True,
        sandbox="workspace-write",
        ask_for_approval="on-request",
        config_overrides=stable_config_overrides(),
        approval_callbacks={
            "command": approve_command,
            "file_change": approve_file_change,
        },
    )

    async with CodexSDKClient(options) as client:
        prompt = (
            "Create ./permission_demo.txt with one line saying hello, "
            "then print the file."
        )
        print(f"User: {prompt}")

        await client.query(prompt)
        async for event in client.receive_response():
            print(f"[event] {event_label(event)}")
            if is_assistant_item(event):
                for text in iter_text_fragments(event):
                    print(f"Codex: {text}")


if __name__ == "__main__":
    anyio.run(main)
