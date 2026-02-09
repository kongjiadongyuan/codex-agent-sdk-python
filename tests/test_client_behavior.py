"""Tests for public and internal client behavior."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

import codex_agent_sdk.client as client_module
from codex_agent_sdk._errors import CLIConnectionError, HookAbort, ProtocolStreamError
from codex_agent_sdk._internal.client import InternalClient
from codex_agent_sdk._internal.query import Query
from codex_agent_sdk._internal.transport import Transport
from codex_agent_sdk.client import CodexSDKClient
from codex_agent_sdk.types import CodexAgentOptions, CodexEvent, CodexMessage, Message


class FakeTransport(Transport):
    def __init__(self, messages: list[dict[str, Any]]):
        self.messages = messages
        self.connected = False
        self.closed = False

    async def connect(self) -> None:
        self.connected = True

    async def write(self, data: str) -> None:
        _ = data

    async def close(self) -> None:
        self.closed = True
        self.connected = False

    def is_ready(self) -> bool:
        return self.connected and not self.closed

    async def end_input(self) -> None:
        return None

    async def read_messages(self) -> AsyncIterator[dict[str, Any]]:
        for message in self.messages:
            yield message


@pytest.mark.asyncio
async def test_client_run_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_query(
        *,
        prompt: str | None,
        options: CodexAgentOptions | None = None,
        transport: Transport | None = None,
        model: str | None = None,
    ) -> AsyncIterator[Message]:
        captured["prompt"] = prompt
        captured["model"] = options.model if options else None
        _ = transport
        _ = model
        yield CodexEvent(kind="turn", event={"type": "turn.completed"})

    monkeypatch.setattr(client_module, "query_fn", fake_query)

    client = CodexSDKClient(CodexAgentOptions(model="base-model"))
    events = [
        event
        async for event in client.run(prompt="hello", model="override-model")
    ]
    assert len(events) == 1
    assert captured["prompt"] == "hello"
    assert captured["model"] == "override-model"


@pytest.mark.asyncio
async def test_client_query_requires_connect() -> None:
    client = CodexSDKClient()
    with pytest.raises(CLIConnectionError):
        await client.query("hello")


@pytest.mark.asyncio
async def test_session_query_then_receive_response() -> None:
    class StubClient(CodexSDKClient):
        async def run(
            self,
            prompt: str | None,
            *,
            session_id: str | None = None,
            resume_last: bool | None = None,
            resume_all: bool | None = None,
            model: str | None = None,
        ) -> AsyncIterator[Message]:
            _ = prompt
            _ = session_id
            _ = resume_last
            _ = resume_all
            _ = model
            yield CodexEvent(kind="turn", event={"type": "turn.started"})
            yield CodexEvent(kind="turn", event={"type": "turn.completed"})
            yield CodexEvent(kind="turn", event={"type": "turn.started"})

    client = StubClient()
    await client.connect()
    await client.query("hello")

    events = [event async for event in client.receive_response()]
    await client.disconnect()

    assert len(events) == 2
    assert events[0].event.get("type") == "turn.started"
    assert events[1].event.get("type") == "turn.completed"


@pytest.mark.asyncio
async def test_session_query_rejects_when_previous_response_active() -> None:
    class StubClient(CodexSDKClient):
        async def run(
            self,
            prompt: str | None,
            *,
            session_id: str | None = None,
            resume_last: bool | None = None,
            resume_all: bool | None = None,
            model: str | None = None,
        ) -> AsyncIterator[Message]:
            _ = prompt
            _ = session_id
            _ = resume_last
            _ = resume_all
            _ = model
            yield CodexEvent(kind="turn", event={"type": "turn.started"})
            yield CodexEvent(kind="turn", event={"type": "turn.completed"})

    client = StubClient()
    await client.connect()
    await client.query("first")
    with pytest.raises(CLIConnectionError):
        await client.query("second")
    await client.disconnect()


@pytest.mark.asyncio
async def test_set_model_requires_connect() -> None:
    client = CodexSDKClient()
    with pytest.raises(CLIConnectionError):
        await client.set_model("gpt-5-codex")


@pytest.mark.asyncio
async def test_set_model_affects_followup_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_query(
        *,
        prompt: str | None,
        options: CodexAgentOptions | None = None,
        transport: Transport | None = None,
        model: str | None = None,
    ) -> AsyncIterator[Message]:
        _ = prompt
        _ = transport
        _ = model
        captured["model"] = options.model if options else None
        yield CodexEvent(kind="turn", event={"type": "turn.completed"})

    monkeypatch.setattr(client_module, "query_fn", fake_query)

    client = CodexSDKClient(CodexAgentOptions(model="base-model"))
    await client.connect()
    await client.set_model("session-model")
    _ = [event async for event in client.run("hello")]
    await client.disconnect()

    assert captured["model"] == "session-model"


@pytest.mark.asyncio
async def test_internal_client_hook_dispatch_order() -> None:
    calls: list[str] = []

    async def all_hook(message: Message) -> None:
        _ = message
        calls.append("*")

    async def item_hook(message: Message) -> None:
        _ = message
        calls.append("item")

    options = CodexAgentOptions(
        event_hooks={"*": [all_hook], "item": [item_hook]},
        event_parser=lambda data: CodexMessage(kind="item", raw=data),
    )
    transport = FakeTransport(
        [{"type": "item.completed", "item": {"type": "agent_message"}}]
    )

    client = InternalClient()
    messages = [
        message
        async for message in client.process_query(
            prompt="test", options=options, transport=transport
        )
    ]

    assert len(messages) == 1
    assert calls == ["*", "item"]


@pytest.mark.asyncio
async def test_internal_client_hook_abort_stops_stream() -> None:
    def abort_hook(message: Message) -> None:
        _ = message
        raise HookAbort("stop")

    options = CodexAgentOptions(
        event_hooks={"*": [abort_hook]},
        event_parser=lambda data: CodexMessage(kind="item", raw=data),
    )
    transport = FakeTransport(
        [{"type": "item.completed", "item": {"type": "agent_message"}}]
    )

    client = InternalClient()
    messages = [
        message
        async for message in client.process_query(
            prompt="test", options=options, transport=transport
        )
    ]

    assert messages == []
    assert transport.closed is True


@pytest.mark.asyncio
async def test_query_close_ignores_cross_task_runtime_error() -> None:
    class DummyCancelScope:
        def cancel(self) -> None:
            return None

    class DummyTaskGroup:
        cancel_scope = DummyCancelScope()

        async def __aexit__(
            self, exc_type: object, exc: object, tb: object
        ) -> None:
            _ = exc_type
            _ = exc
            _ = tb
            raise RuntimeError(
                "Attempted to exit cancel scope in a different task than "
                "it was entered in"
            )

    transport = FakeTransport([])
    query = Query(transport)
    query._tg = DummyTaskGroup()  # type: ignore[assignment]
    await query.close()


@pytest.mark.asyncio
async def test_query_preserves_real_error_event_payload() -> None:
    transport = FakeTransport([{"type": "error", "error": {"message": "boom"}}])
    await transport.connect()

    query = Query(transport)
    await query.start()
    messages = [message async for message in query.receive_messages()]

    assert messages == [{"type": "error", "error": {"message": "boom"}}]
    await query.close()


@pytest.mark.asyncio
async def test_query_control_error_raises_protocol_stream_error() -> None:
    transport = FakeTransport([])
    await transport.connect()

    query = Query(transport)
    await query._message_send.send(
        {
            "__codex_agent_sdk_control__": "error",
            "error": "transport exploded",
        }
    )
    await query._message_send.send({"__codex_agent_sdk_control__": "end"})

    with pytest.raises(ProtocolStreamError):
        _ = [message async for message in query.receive_messages()]


@pytest.mark.asyncio
async def test_legacy_receive_response_warns_and_closes_stream() -> None:
    class StubClient(CodexSDKClient):
        def __init__(self) -> None:
            super().__init__()
            self.closed = False

        async def run(
            self,
            prompt: str | None,
            *,
            session_id: str | None = None,
            resume_last: bool | None = None,
            resume_all: bool | None = None,
            model: str | None = None,
        ) -> AsyncIterator[Message]:
            _ = prompt
            _ = session_id
            _ = resume_last
            _ = resume_all
            _ = model
            try:
                yield CodexEvent(kind="turn", event={"type": "turn.completed"})
                yield CodexEvent(kind="turn", event={"type": "turn.started"})
            finally:
                self.closed = True

    client = StubClient()
    with pytest.warns(DeprecationWarning):
        events = [event async for event in client.receive_response(prompt="hello")]

    assert len(events) == 1
    assert client.closed is True
