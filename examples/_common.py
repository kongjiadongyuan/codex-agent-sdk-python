"""Shared helpers for Codex SDK examples."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from typing import Any

from codex_agent_sdk.types import CodexEvent, CodexMessage, Message

ASSISTANT_ITEM_TYPES = {
    "agent_message",
    "assistant_message",
    "assistant_message_delta",
    "assistant_message_chunk",
    "assistant_message_final",
    "reasoning",
    "thinking",
}


def stable_config_overrides(
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Optional example-only overrides controlled by env vars.

    Defaults to no extra overrides. Set
    `CODEX_SDK_EXAMPLE_FORCE_MEDIUM_REASONING=1` to add
    `model_reasoning_effort="medium"` to the returned dictionary.
    """
    merged: dict[str, Any] = dict(extra or {})
    if os.getenv("CODEX_SDK_EXAMPLE_FORCE_MEDIUM_REASONING", "").lower() in {
        "1",
        "true",
        "yes",
    }:
        merged.setdefault("model_reasoning_effort", "medium")
    return merged


def quiet_stderr(_line: str) -> None:
    """Optional stderr filter for examples.

    By default, stderr lines are forwarded to stderr for full visibility.
    Set `CODEX_SDK_EXAMPLE_QUIET_STDERR=1` to suppress them.
    """
    if os.getenv("CODEX_SDK_EXAMPLE_QUIET_STDERR", "").lower() in {
        "1",
        "true",
        "yes",
    }:
        return None
    print(_line, file=sys.stderr)



def event_label(message: Message) -> str:
    kind = getattr(message, "kind", "unknown")
    event_type = getattr(message, "event_type", None)
    if event_type:
        return f"{kind}:{event_type}"
    return str(kind)



def iter_text_fragments(message: Message) -> Iterable[str]:
    """Yield best-effort text fragments from an SDK message."""
    if isinstance(message, CodexMessage):
        if message.text:
            yield message.text
            return
        raw = message.raw
    elif isinstance(message, CodexEvent):
        raw = message.event
    else:
        return

    if not isinstance(raw, dict):
        return

    text = raw.get("text")
    if isinstance(text, str):
        yield text

    item = raw.get("item")
    if isinstance(item, dict):
        item_text = item.get("text")
        if isinstance(item_text, str):
            yield item_text



def is_assistant_item(message: Message) -> bool:
    if not isinstance(message, CodexMessage):
        return False
    if message.kind != "item":
        return False
    if message.role == "assistant":
        return True
    return message.item_type in ASSISTANT_ITEM_TYPES
