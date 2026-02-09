"""App-server client implementation for Codex SDK."""

import json
import logging
from collections.abc import AsyncIterator
from contextlib import suppress
from pathlib import Path
from typing import Any, cast

import anyio

from .._errors import (
    ApprovalDecisionError,
    CLIConnectionError,
    ProtocolStreamError,
    RequestTimeoutError,
)
from ..types import ApprovalDecision, CodexAgentOptions, CodexTool
from .tool_schema import normalize_tool_input_schema
from .transport.app_server import AppServerTransport

logger = logging.getLogger(__name__)
_CONTROL_KEY = "__codex_agent_sdk_control__"

_APPROVAL_DECISION_MAP = {
    "allow": "accept",
    "accept": "accept",
    "approve": "accept",
    "approved": "accept",
    "yes": "accept",
    "y": "accept",
    "deny": "deny",
    "denied": "deny",
    "reject": "deny",
    "rejected": "deny",
    "block": "deny",
    "no": "deny",
    "n": "deny",
    "defer": "defer",
    "default": "defer",
    "fallback": "defer",
    "ask": "defer",
}


class AppServerClient:
    def __init__(self, options: CodexAgentOptions):
        self.options = options
        self.transport = AppServerTransport(options)
        self._message_send, self._message_receive = anyio.create_memory_object_stream[
            dict[str, Any]
        ](max_buffer_size=200)
        self._tg: anyio.abc.TaskGroup | None = None
        self._closed = False
        self._request_counter = 0
        self._pending: dict[str, anyio.Event] = {}
        self._pending_results: dict[str, dict[str, Any] | Exception] = {}
        self._tool_map: dict[str, CodexTool] = {
            t.name: t for t in options.dynamic_tools
        }
        self._started = False

    def _request_timeout(self) -> float | None:
        timeout = self.options.app_server_request_timeout_seconds
        if timeout is None:
            return None
        if timeout <= 0:
            return None
        return timeout

    def _fail_pending_requests(self, error: Exception) -> None:
        self._pending_results.update(
            {request_id: error for request_id in self._pending}
        )
        for event in self._pending.values():
            event.set()

    async def _send(self, payload: dict[str, Any]) -> None:
        await self.transport.write(json.dumps(payload) + "\n")

    async def _send_request(
        self, method: str, params: dict[str, Any] | None
    ) -> dict[str, Any]:
        self._request_counter += 1
        request_id = f"req_{self._request_counter}"
        event = anyio.Event()
        self._pending[request_id] = event
        payload: dict[str, Any] = {"id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        await self._send(payload)

        timeout = self._request_timeout()
        try:
            if timeout is None:
                await event.wait()
            else:
                with anyio.fail_after(timeout):
                    await event.wait()
        except TimeoutError as error:
            self._pending.pop(request_id, None)
            self._pending_results.pop(request_id, None)
            timeout_seconds = timeout if timeout is not None else 0.0
            raise RequestTimeoutError(
                method=method, timeout_seconds=timeout_seconds
            ) from error

        result = self._pending_results.pop(request_id)
        self._pending.pop(request_id, None)
        if isinstance(result, Exception):
            raise result
        return result

    async def _send_notification(
        self, method: str, params: dict[str, Any] | None = None
    ) -> None:
        payload: dict[str, Any] = {"method": method}
        if params is not None:
            payload["params"] = params
        await self._send(payload)

    async def start(self) -> None:
        if self._started:
            return
        await self.transport.connect()
        self._tg = anyio.create_task_group()
        await self._tg.__aenter__()
        self._tg.start_soon(self._read_loop)

        # initialize
        init_params = {
            "clientInfo": {
                "name": "codex-agent-sdk",
                "version": "0.1.0",
            },
            "capabilities": {
                "experimentalApi": True,
            },
        }
        await self._send_request("initialize", init_params)
        await self._send_notification("initialized")
        self._started = True

    async def _read_loop(self) -> None:
        try:
            async for message in self.transport.read_messages():
                if self._closed:
                    break

                # Response to our request
                if "id" in message and ("result" in message or "error" in message):
                    request_id = str(message.get("id"))
                    if request_id not in self._pending:
                        logger.debug("Ignoring unexpected response id: %s", request_id)
                        continue
                    if "error" in message:
                        error_payload = message.get("error")
                        self._pending_results[request_id] = ProtocolStreamError(
                            "App-server returned an error response.",
                            method=message.get("method")
                            if isinstance(message.get("method"), str)
                            else None,
                            payload=error_payload
                            if isinstance(error_payload, dict)
                            else None,
                        )
                    else:
                        self._pending_results[request_id] = message.get("result", {})
                    self._pending[request_id].set()
                    continue

                # Server requests
                if "method" in message and "id" in message:
                    if self._tg:
                        self._tg.start_soon(self._handle_server_request, message)
                    continue

                # Server notifications
                if "method" in message:
                    normalized = self._normalize_notification(message)
                    await self._message_send.send(normalized)
                    continue

                # Fallback
                await self._message_send.send(message)

        except anyio.get_cancelled_exc_class():
            raise
        except Exception as e:
            self._fail_pending_requests(e)
            await self._message_send.send({_CONTROL_KEY: "error", "error": str(e)})
        finally:
            if self._pending:
                self._fail_pending_requests(
                    CLIConnectionError("App-server connection closed before response.")
                )
            await self._message_send.send({_CONTROL_KEY: "end"})

    def _normalize_approval_decision(
        self, raw: str, *, callback_name: str
    ) -> ApprovalDecision:
        normalized = _APPROVAL_DECISION_MAP.get(raw.strip().lower())
        if normalized is None:
            raise ApprovalDecisionError(
                f"{callback_name} must return one of "
                f"{sorted(_APPROVAL_DECISION_MAP)}; got {raw!r}."
            )
        if normalized == "accept":
            return "allow"
        if normalized == "deny":
            return "deny"
        return "defer"

    def _fallback_decision_from_policy(self) -> ApprovalDecision:
        policy = self.options.ask_for_approval
        if policy == "never":
            return "allow"
        if policy in {"untrusted", "on-failure", "on-request"}:
            return "deny"
        return "deny"

    def _normalize_notification(self, message: dict[str, Any]) -> dict[str, Any]:
        method = message.get("method")
        params = message.get("params")
        if isinstance(method, str) and isinstance(params, dict):
            event_type = method.replace("/", ".")
            normalized = {"type": event_type, **params}
            return normalized
        return message

    async def _handle_server_request(self, message: dict[str, Any]) -> None:
        request_id = str(message.get("id"))
        method = message.get("method")
        params_obj = message.get("params")
        if isinstance(params_obj, dict):
            params = cast(dict[str, Any], params_obj)
        else:
            params = {}

        try:
            if method == "item/tool/call":
                result = await self._handle_dynamic_tool_call(params)
                await self._send({"id": request_id, "result": result})
                return

            if method == "item/tool/requestUserInput":
                result = await self._handle_tool_user_input(params)
                await self._send({"id": request_id, "result": result})
                return

            if method == "item/commandExecution/requestApproval":
                result = await self._handle_command_approval(params)
                await self._send({"id": request_id, "result": result})
                return

            if method == "item/fileChange/requestApproval":
                result = await self._handle_file_change_approval(params)
                await self._send({"id": request_id, "result": result})
                return

            # Legacy approval methods
            if method in {"execCommandApproval", "applyPatchApproval"}:
                result = await self._handle_legacy_approval(method, params)
                await self._send({"id": request_id, "result": result})
                return

            await self._send(
                {
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method {method} not supported",
                    },
                }
            )

        except Exception as e:
            await self._send(
                {
                    "id": request_id,
                    "error": {"code": -32603, "message": str(e)},
                }
            )

    async def _handle_dynamic_tool_call(self, params: dict[str, Any]) -> dict[str, Any]:
        tool_name = params.get("tool")
        args = params.get("arguments")
        if not isinstance(tool_name, str):
            raise CLIConnectionError("Dynamic tool call missing tool name")

        tool = self._tool_map.get(tool_name)
        if not tool:
            return {"success": False, "output": f"Unknown tool: {tool_name}"}

        try:
            if not isinstance(args, dict):
                args = {}
            result = await tool.handler(args)
            output = self._normalize_tool_output(result)
            return {"success": True, "output": output}
        except Exception as e:
            return {"success": False, "output": str(e)}

    async def _handle_tool_user_input(self, params: dict[str, Any]) -> dict[str, Any]:
        callback = (
            self.options.request_user_input_callback or self.options.provide_tool_input
        )
        if callback:
            answer = callback(params)
            if hasattr(answer, "__await__"):
                answer = await answer  # type: ignore[misc]
            if isinstance(answer, dict):
                return {"answers": answer}
            if isinstance(answer, str):
                question_id = params.get("questionId") or "question"
                return {"answers": {question_id: {"answers": [answer]}}}
            raise TypeError(
                "request_user_input_callback must return str or dict, "
                f"got {type(answer).__name__}."
            )
        return {"answers": {}}

    async def _handle_command_approval(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        resolved = await self._resolve_approval_decision(
            kind="command",
            params=params,
            callback_name="command approval callback",
        )
        if isinstance(resolved, dict):
            return resolved
        decision = "accept" if resolved == "allow" else "deny"
        return {"decision": decision}

    async def _handle_file_change_approval(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        resolved = await self._resolve_approval_decision(
            kind="file_change",
            params=params,
            callback_name="file change approval callback",
        )
        if isinstance(resolved, dict):
            return resolved
        decision = "accept" if resolved == "allow" else "deny"
        return {"decision": decision}

    async def _handle_legacy_approval(
        self, method: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        kind = "command" if method == "execCommandApproval" else "file_change"
        callback_name = f"{method} approval callback"
        resolved = await self._resolve_approval_decision(
            kind=kind,
            params=params,
            callback_name=callback_name,
        )
        if isinstance(resolved, dict):
            return resolved
        decision = "approved" if resolved == "allow" else "denied"
        return {"decision": decision}

    async def _resolve_approval_decision(
        self, *, kind: str, params: dict[str, Any], callback_name: str
    ) -> ApprovalDecision | dict[str, Any]:
        callback = None
        if kind == "command":
            callback = self.options.approval_callbacks.get("command")
            if callback is None:
                callback = self.options.approval_callbacks.get("command_execution")
            if callback is None:
                callback = self.options.approve_command
        elif kind == "file_change":
            callback = self.options.approval_callbacks.get("file_change")
            if callback is None:
                callback = self.options.approval_callbacks.get("fileChange")
            if callback is None:
                callback = self.options.approve_file_change

        if callback is None:
            return self._fallback_decision_from_policy()

        result = callback(params)
        if hasattr(result, "__await__"):
            result = await result  # type: ignore[misc]

        if isinstance(result, dict):
            return result
        if result is None:
            return self._fallback_decision_from_policy()
        if isinstance(result, str):
            decision = self._normalize_approval_decision(
                result,
                callback_name=callback_name,
            )
            if decision == "defer":
                return self._fallback_decision_from_policy()
            return decision

        raise ApprovalDecisionError(
            f"{callback_name} must return str, dict, or None; "
            f"got {type(result).__name__}."
        )

    def _normalize_tool_output(self, result: Any) -> str:
        if isinstance(result, str):
            return result
        if isinstance(result, dict) and "content" in result:
            parts: list[str] = []
            content = result.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text")
                        if isinstance(text, str):
                            parts.append(text)
            if parts:
                return "\n".join(parts)
        return json.dumps(result, ensure_ascii=False)

    async def run_query(self, prompt: str) -> AsyncIterator[dict[str, Any]]:
        await self.start()

        # Start thread
        thread_params: dict[str, Any] = {
            "approvalPolicy": self.options.ask_for_approval,
            "cwd": str(self.options.cwd) if self.options.cwd else None,
            "model": self.options.model,
            "modelProvider": None,
            "sandbox": self.options.sandbox,
            "dynamicTools": self._serialize_dynamic_tools(),
            "config": self.options.config_overrides or None,
        }
        # Remove nulls for cleanliness
        thread_params = {k: v for k, v in thread_params.items() if v is not None}

        if self.options.resume_session:
            thread_params["threadId"] = self.options.resume_session
            thread_result = await self._send_request("thread/resume", thread_params)
        else:
            thread_result = await self._send_request("thread/start", thread_params)

        thread_id = None
        if isinstance(thread_result, dict):
            thread = thread_result.get("thread")
            if isinstance(thread, dict):
                thread_id = thread.get("id")

        if not thread_id:
            raise CLIConnectionError("Failed to obtain thread id from app-server")

        # Start turn
        output_schema = self._load_output_schema()
        turn_params: dict[str, Any] = {
            "threadId": thread_id,
            "input": [
                {
                    "type": "text",
                    "text": prompt,
                    "text_elements": [],
                }
            ],
            "approvalPolicy": self.options.ask_for_approval,
            "cwd": str(self.options.cwd) if self.options.cwd else None,
            "model": self.options.model,
            "outputSchema": output_schema,
        }
        turn_params = {k: v for k, v in turn_params.items() if v is not None}
        await self._send_request("turn/start", turn_params)

        async for message in self._message_receive:
            if message.get(_CONTROL_KEY) == "end":
                break
            if message.get(_CONTROL_KEY) == "error":
                error_text = message.get("error", "Unknown error")
                raise ProtocolStreamError(
                    f"App-server stream failed: {error_text}",
                )
            yield message

    def _serialize_dynamic_tools(self) -> list[dict[str, Any]] | None:
        if not self.options.dynamic_tools:
            return None
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": normalize_tool_input_schema(tool.input_schema),
            }
            for tool in self.options.dynamic_tools
        ]

    def _load_output_schema(self) -> Any | None:
        schema = self.options.output_schema
        if schema is None:
            return None
        if isinstance(schema, (str, Path)):
            try:
                path = Path(schema)
                if path.exists():
                    return json.loads(path.read_text())
            except Exception:
                return schema
        return schema

    async def close(self) -> None:
        self._closed = True
        if self._pending:
            self._fail_pending_requests(
                CLIConnectionError("App-server client closed with pending requests.")
            )
        if self._tg:
            self._tg.cancel_scope.cancel()
            with suppress(anyio.get_cancelled_exc_class(), RuntimeError):
                await self._tg.__aexit__(None, None, None)
            self._tg = None
        await self.transport.close()
        self._started = False

    async def mcp_status_list(self) -> dict[str, Any]:
        await self.start()
        return await self._send_request("mcpServerStatus/list", {})

    async def mcp_reload(self) -> dict[str, Any]:
        await self.start()
        return await self._send_request("config/mcpServer/reload", {})
