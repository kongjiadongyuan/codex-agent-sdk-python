#!/usr/bin/env python3
"""Comprehensive streaming examples for CodexSDKClient."""

from __future__ import annotations

import sys

import anyio
from _common import (
    event_label,
    is_assistant_item,
    iter_text_fragments,
    quiet_stderr,
    stable_config_overrides,
)

from codex_agent_sdk import CLIConnectionError, CodexAgentOptions, CodexSDKClient


async def basic_streaming() -> None:
    print("=== basic_streaming ===")
    async with CodexSDKClient(
        CodexAgentOptions(
            model="gpt-5-codex",
            config_overrides=stable_config_overrides(),
            stderr=quiet_stderr,
        )
    ) as client:
        await client.query("What is 2 + 2?")
        async for event in client.receive_response():
            if is_assistant_item(event):
                for text in iter_text_fragments(event):
                    print(f"Codex: {text}")
    print()


async def multi_turn_conversation() -> None:
    print("=== multi_turn_conversation ===")
    async with CodexSDKClient(
        CodexAgentOptions(
            model="gpt-5-codex",
            config_overrides=stable_config_overrides(),
            stderr=quiet_stderr,
        )
    ) as client:
        await client.query("What is 15 + 27?")
        async for event in client.receive_response():
            if is_assistant_item(event):
                for text in iter_text_fragments(event):
                    print(f"Codex: {text}")

        await client.query("Now multiply that by 2")
        async for event in client.receive_response():
            if is_assistant_item(event):
                for text in iter_text_fragments(event):
                    print(f"Codex: {text}")

        print(f"last_session_id={client.last_session_id}")
    print()


async def manual_message_handling() -> None:
    print("=== manual_message_handling ===")
    async with CodexSDKClient(
        CodexAgentOptions(
            config_overrides=stable_config_overrides(),
            stderr=quiet_stderr,
        )
    ) as client:
        await client.query("List three backend languages and one use case each")
        async for event in client.receive_messages():
            print(f"[event] {event_label(event)}")
            if is_assistant_item(event):
                for text in iter_text_fragments(event):
                    print(f"Codex: {text}")
    print()


async def async_iterable_prompt() -> None:
    print("=== async_iterable_prompt ===")

    async def prompt_chunks():
        yield "I have two questions. "
        yield "First: what is 25 * 4? "
        yield "Second: what is 100 / 5?"

    async with CodexSDKClient(
        CodexAgentOptions(
            config_overrides=stable_config_overrides(),
            stderr=quiet_stderr,
        )
    ) as client:
        await client.query(prompt_chunks())
        async for event in client.receive_response():
            if is_assistant_item(event):
                for text in iter_text_fragments(event):
                    print(f"Codex: {text}")
    print()


async def model_override() -> None:
    print("=== model_override ===")
    async with CodexSDKClient(
        CodexAgentOptions(
            model="gpt-5-codex",
            config_overrides=stable_config_overrides(),
            stderr=quiet_stderr,
        )
    ) as client:
        await client.query(
            "Give one sentence explaining the observer pattern.",
            model="gpt-5-codex",
        )
        async for event in client.receive_response():
            if is_assistant_item(event):
                for text in iter_text_fragments(event):
                    print(f"Codex: {text}")
    print()


async def error_handling() -> None:
    print("=== error_handling ===")
    bad = CodexSDKClient(
        CodexAgentOptions(cwd="/path/that/does/not/exist", stderr=quiet_stderr)
    )
    try:
        await bad.connect()
        await bad.query("hello")
        async for _event in bad.receive_response():
            pass
    except CLIConnectionError as exc:
        print(f"Caught expected connection error: {exc}")
    finally:
        await bad.disconnect()
    print()


async def run_example(name: str) -> None:
    examples = {
        "basic_streaming": basic_streaming,
        "multi_turn_conversation": multi_turn_conversation,
        "manual_message_handling": manual_message_handling,
        "async_iterable_prompt": async_iterable_prompt,
        "model_override": model_override,
        "error_handling": error_handling,
    }

    if name == "all":
        for func in examples.values():
            await func()
        return

    if name not in examples:
        available = ", ".join(["all", *examples.keys()])
        raise SystemExit(f"Unknown example '{name}'. Available: {available}")

    await examples[name]()


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python examples/streaming_mode.py <example_name>")
        print("Example names: all, basic_streaming, multi_turn_conversation,")
        print("  manual_message_handling, async_iterable_prompt,")
        print("  model_override, error_handling")
        return

    await run_example(sys.argv[1])


if __name__ == "__main__":
    anyio.run(main)
