"""Tests for top-level query API behavior."""

from __future__ import annotations

import importlib
from collections.abc import AsyncIterator
from typing import Any

import pytest

from codex_agent_sdk.types import CodexAgentOptions, CodexEvent

query_module = importlib.import_module("codex_agent_sdk.query")


@pytest.mark.asyncio
async def test_query_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_process_query(
        self: object,
        prompt: str | None,
        options: CodexAgentOptions,
        transport: object | None = None,
    ) -> AsyncIterator[CodexEvent]:
        _ = self
        _ = prompt
        _ = transport
        captured["model"] = options.model
        yield CodexEvent(kind="turn", event={"type": "turn.completed"})

    monkeypatch.setattr(
        query_module.InternalClient, "process_query", fake_process_query
    )

    options = CodexAgentOptions(model="base-model")
    events = [
        event
        async for event in query_module.query(
            prompt="ping",
            options=options,
            model="override-model",
        )
    ]
    assert len(events) == 1
    assert captured["model"] == "override-model"
