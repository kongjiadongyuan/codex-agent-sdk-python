#!/usr/bin/env python3
"""Example: resume a Codex session using CodexSDKClient."""

import anyio
from _common import quiet_stderr, stable_config_overrides

from codex_agent_sdk import CodexAgentOptions, CodexSDKClient


async def main() -> None:
    options = CodexAgentOptions(
        model="gpt-5-codex",
        sandbox="workspace-write",
        config_overrides=stable_config_overrides(),
        stderr=quiet_stderr,
    )
    async with CodexSDKClient(options) as client:
        print("First query")
        await client.query("Summarize this repo")
        async for event in client.receive_response():
            print(event)

        if client.last_session_id:
            print(f"Resuming session: {client.last_session_id}")
        else:
            print("No session id found in events; resume may not work.")

        await client.query("Now list key Python files")
        async for event in client.receive_response():
            print(event)


if __name__ == "__main__":
    anyio.run(main)
