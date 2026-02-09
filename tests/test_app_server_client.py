"""Tests for app-server client behavior."""

from __future__ import annotations

import pytest

from codex_agent_sdk._errors import ApprovalDecisionError, RequestTimeoutError
from codex_agent_sdk._internal.app_server_client import AppServerClient
from codex_agent_sdk.types import CodexAgentOptions, CodexTool


@pytest.mark.asyncio
async def test_send_request_times_out_and_cleans_state() -> None:
    client = AppServerClient(
        CodexAgentOptions(app_server_request_timeout_seconds=0.01)
    )

    async def noop_send(payload: dict[str, object]) -> None:
        _ = payload

    client._send = noop_send  # type: ignore[method-assign]

    with pytest.raises(RequestTimeoutError):
        await client._send_request("initialize", {})

    assert client._pending == {}
    assert client._pending_results == {}


@pytest.mark.asyncio
async def test_command_approval_normalizes_aliases() -> None:
    options = CodexAgentOptions(approval_callbacks={"command": lambda _: "approved"})
    client = AppServerClient(options)

    result = await client._handle_command_approval({"command": "ls"})
    assert result == {"decision": "accept"}


@pytest.mark.asyncio
async def test_command_approval_rejects_invalid_decision() -> None:
    options = CodexAgentOptions(approval_callbacks={"command": lambda _: "maybe"})
    client = AppServerClient(options)

    with pytest.raises(ApprovalDecisionError):
        await client._handle_command_approval({"command": "ls"})


@pytest.mark.asyncio
async def test_command_approval_defer_uses_policy_never() -> None:
    options = CodexAgentOptions(
        ask_for_approval="never",
        approval_callbacks={"command": lambda _: "defer"},
    )
    client = AppServerClient(options)

    result = await client._handle_command_approval({"command": "ls"})
    assert result == {"decision": "accept"}


@pytest.mark.asyncio
async def test_command_approval_defer_uses_policy_on_request() -> None:
    options = CodexAgentOptions(
        ask_for_approval="on-request",
        approval_callbacks={"command": lambda _: "defer"},
    )
    client = AppServerClient(options)

    result = await client._handle_command_approval({"command": "ls"})
    assert result == {"decision": "deny"}


@pytest.mark.asyncio
async def test_command_approval_without_callback_uses_policy_fallback() -> None:
    client = AppServerClient(CodexAgentOptions(ask_for_approval="on-failure"))

    result = await client._handle_command_approval({"command": "ls"})
    assert result == {"decision": "deny"}


@pytest.mark.asyncio
async def test_command_approval_none_result_uses_policy_fallback() -> None:
    options = CodexAgentOptions(
        ask_for_approval="never",
        approval_callbacks={"command": lambda _: None},
    )
    client = AppServerClient(options)

    result = await client._handle_command_approval({"command": "ls"})
    assert result == {"decision": "accept"}


@pytest.mark.asyncio
async def test_request_user_input_rejects_invalid_callback_output() -> None:
    options = CodexAgentOptions(request_user_input_callback=lambda _: 123)
    client = AppServerClient(options)

    with pytest.raises(TypeError):
        await client._handle_tool_user_input({"questionId": "q1"})


@pytest.mark.asyncio
async def test_mcp_rpc_method_names() -> None:
    client = AppServerClient(CodexAgentOptions())
    called: list[str] = []

    async def fake_start() -> None:
        return None

    async def fake_send_request(
        method: str, params: dict[str, object]
    ) -> dict[str, object]:
        called.append(method)
        _ = params
        return {}

    client.start = fake_start  # type: ignore[method-assign]
    client._send_request = fake_send_request  # type: ignore[method-assign]

    await client.mcp_status_list()
    await client.mcp_reload()

    assert called == ["mcpServerStatus/list", "config/mcpServer/reload"]


@pytest.mark.asyncio
async def test_run_query_turn_start_omits_sandbox_policy() -> None:
    client = AppServerClient(CodexAgentOptions(sandbox="workspace-write"))
    captured_turn_params: dict[str, object] = {}

    async def fake_start() -> None:
        return None

    async def fake_send_request(
        method: str, params: dict[str, object]
    ) -> dict[str, object]:
        if method == "thread/start":
            return {"thread": {"id": "thread_1"}}
        if method == "turn/start":
            captured_turn_params.update(params)
            await client._message_send.send({"__codex_agent_sdk_control__": "end"})
            return {}
        return {}

    client.start = fake_start  # type: ignore[method-assign]
    client._send_request = fake_send_request  # type: ignore[method-assign]

    events = [event async for event in client.run_query("hello")]
    assert events == []
    assert "sandboxPolicy" not in captured_turn_params


@pytest.mark.asyncio
async def test_serialize_dynamic_tools_normalizes_schema() -> None:
    async def handler(args: dict[str, object]) -> str:
        _ = args
        return "ok"

    tool = CodexTool(
        name="hello",
        description="hello",
        input_schema={"name": {"type": "string"}},
        handler=handler,
    )
    client = AppServerClient(CodexAgentOptions(dynamic_tools=[tool]))

    serialized = client._serialize_dynamic_tools()
    assert serialized is not None
    assert serialized[0]["inputSchema"]["type"] == "object"
    assert serialized[0]["inputSchema"]["properties"] == {"name": {"type": "string"}}


@pytest.mark.asyncio
async def test_close_ignores_cross_task_runtime_error() -> None:
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

    client = AppServerClient(CodexAgentOptions())
    client._tg = DummyTaskGroup()  # type: ignore[assignment]

    async def fake_transport_close() -> None:
        return None

    client.transport.close = fake_transport_close  # type: ignore[method-assign]
    await client.close()


@pytest.mark.asyncio
async def test_run_query_preserves_real_error_event_payload() -> None:
    client = AppServerClient(CodexAgentOptions())

    async def fake_start() -> None:
        return None

    async def fake_send_request(
        method: str, params: dict[str, object]
    ) -> dict[str, object]:
        _ = params
        if method == "thread/start":
            return {"thread": {"id": "thread_1"}}
        if method == "turn/start":
            await client._message_send.send({"type": "error", "message": "real"})
            await client._message_send.send({"__codex_agent_sdk_control__": "end"})
            return {}
        return {}

    client.start = fake_start  # type: ignore[method-assign]
    client._send_request = fake_send_request  # type: ignore[method-assign]

    events = [event async for event in client.run_query("hello")]
    assert events == [{"type": "error", "message": "real"}]


@pytest.mark.asyncio
async def test_legacy_approval_uses_same_decision_engine() -> None:
    options = CodexAgentOptions(approval_callbacks={"command": lambda _: "deny"})
    client = AppServerClient(options)

    result = await client._handle_legacy_approval("execCommandApproval", {"cmd": "ls"})
    assert result == {"decision": "denied"}


@pytest.mark.asyncio
async def test_legacy_approval_policy_fallback_for_allow() -> None:
    client = AppServerClient(CodexAgentOptions(ask_for_approval="never"))

    result = await client._handle_legacy_approval("applyPatchApproval", {"path": "a"})
    assert result == {"decision": "approved"}
