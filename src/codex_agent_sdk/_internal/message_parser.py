"""Message parser for Codex SDK responses."""

from typing import Any

from .._errors import MessageParseError
from ..types import CodexEvent, CodexMessage, Message

FINAL_TYPES = {
    "result",
    "final",
    "done",
    "completed",
    "response.completed",
    "response.done",
    "response.final",
    "turn.completed",
}

FINAL_STATUSES = {
    "completed",
    "done",
    "finished",
    "succeeded",
    "success",
    "failed",
    "error",
    "cancelled",
}

ERROR_TYPES = {
    "error",
    "response.error",
}

ITEM_MESSAGE_TYPES = {
    "agent_message",
    "assistant_message",
    "assistant_message_delta",
    "assistant_message_chunk",
    "assistant_message_final",
    "reasoning",
    "thinking",
    "user_message",
}

ITEM_TOOL_TYPES = {
    "command_execution",
    "commandExecution",
    "tool_call",
    "toolCall",
    "tool_result",
    "toolResult",
    "fileChange",
    "mcpToolCall",
    "webSearch",
    "imageView",
    "collabAgentToolCall",
}

LOG_TOKENS = ("log", "stdout", "stderr", "console")


def _extract_session_id(raw: dict[str, Any]) -> str | None:
    for key in (
        "session_id",
        "sessionId",
        "session",
        "conversation_id",
        "conversationId",
        "thread_id",
        "threadId",
    ):
        value = raw.get(key)
        if isinstance(value, str):
            return value
    return None


def _extract_text(content: Any) -> str | None:
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        if "text" in content and isinstance(content["text"], str):
            return content["text"]
        if "content" in content:
            return _extract_text(content["content"])
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            text = _extract_text(item)
            if text:
                parts.append(text)
        return "".join(parts) if parts else None
    return None


def _get_raw_type(raw: dict[str, Any]) -> str | None:
    raw_type = raw.get("type") or raw.get("event") or raw.get("kind")
    return raw_type if isinstance(raw_type, str) else None


def _is_log_type(raw_type: str | None) -> bool:
    if not raw_type:
        return False
    return any(token in raw_type for token in LOG_TOKENS)


def parse_message(data: dict[str, Any]) -> Message:
    """Parse a raw JSON event into a best-effort structured Message object."""
    if not isinstance(data, dict):
        raise MessageParseError(
            f"Invalid message data type (expected dict, got {type(data).__name__})",
            data if isinstance(data, dict) else None,
        )

    raw_type = _get_raw_type(data)
    status = data.get("status") if isinstance(data.get("status"), str) else None
    session_id = _extract_session_id(data)

    # Error detection
    if raw_type in ERROR_TYPES or status in {"error", "failed"} or "error" in data:
        error_value = data.get("error")
        error: str | None
        if isinstance(error_value, str):
            error = error_value
        elif isinstance(error_value, dict):
            error = error_value.get("message") or str(error_value)
        else:
            error = data.get("error_message") or data.get("errorMessage") or None
        return CodexMessage(
            kind="error",
            raw=data,
            event_type=raw_type,
            error=error if isinstance(error, str) else None,
            status=status or raw_type,
            session_id=session_id,
        )

    # Thread/turn detection
    if raw_type and raw_type.startswith("thread."):
        return CodexEvent(
            kind="thread",
            event=data,
            event_type=raw_type,
            status=status,
            session_id=session_id,
        )

    if raw_type and raw_type.startswith("turn."):
        return CodexEvent(
            kind="turn",
            event=data,
            event_type=raw_type,
            status=status,
            session_id=session_id,
        )

    # Log-like events
    if _is_log_type(raw_type):
        return CodexMessage(
            kind="log",
            raw=data,
            event_type=raw_type,
            text=_extract_text(
                data.get("message")
                or data.get("text")
                or data.get("content")
                or data.get("log")
            ),
            status=status or raw_type,
            session_id=session_id,
        )

    # Codex item.* events
    if raw_type in {"item.completed", "item.started"} and isinstance(
        data.get("item"), dict
    ):
        item = data["item"]
        item_type = item.get("type") or item.get("itemType")
        item_status = (
            item.get("status") if isinstance(item.get("status"), str) else None
        )
        role = item.get("role") if isinstance(item.get("role"), str) else None

        if item_type in ITEM_MESSAGE_TYPES or "text" in item or "content" in item:
            inferred_role = role
            if inferred_role is None and item_type in {
                "agent_message",
                "assistant_message",
                "assistant_message_delta",
                "assistant_message_chunk",
                "assistant_message_final",
                "reasoning",
                "thinking",
            }:
                inferred_role = "assistant"
            if inferred_role is None and item_type == "user_message":
                inferred_role = "user"
            return CodexMessage(
                kind="item",
                raw=data,
                event_type=raw_type,
                item_type=item_type if isinstance(item_type, str) else None,
                role=inferred_role,
                text=_extract_text(item.get("text") or item.get("content")),
                status=item_status or status or raw_type,
                session_id=session_id,
            )

        if item_type in ITEM_TOOL_TYPES or (
            isinstance(item_type, str) and "tool" in item_type
        ):
            tool_name = item.get("name")
            if not isinstance(tool_name, str):
                tool_name = item_type if isinstance(item_type, str) else None
            tool_input = item.get("input")
            if not isinstance(tool_input, dict):
                tool_input = {
                    k: v
                    for k, v in {
                        "command": item.get("command"),
                        "args": item.get("args"),
                    }.items()
                    if v is not None
                } or None
            tool_output = (
                item.get("output")
                or item.get("result")
                or item.get("aggregated_output")
                or item.get("stdout")
            )
            return CodexMessage(
                kind="tool",
                raw=data,
                event_type=raw_type,
                item_type=item_type if isinstance(item_type, str) else None,
                tool_name=tool_name,
                tool_input=tool_input if isinstance(tool_input, dict) else None,
                tool_output=tool_output,
                status=item_status or status or raw_type,
                session_id=session_id,
            )

        return CodexEvent(
            kind="item",
            event=data,
            event_type=raw_type,
            item_type=item_type if isinstance(item_type, str) else None,
            status=item_status or status or raw_type,
            session_id=session_id,
        )

    # Tool detection (best-effort)
    tool_name = None
    tool_input = None
    tool_output = None
    if raw_type and "tool" in raw_type:
        tool_name = data.get("tool_name") or data.get("toolName") or data.get("name")
    tool_block = data.get("tool")
    if isinstance(tool_block, dict):
        tool_name = tool_name or tool_block.get("name")
        tool_input = tool_block.get("input") or tool_block.get("arguments")
        tool_output = tool_block.get("output") or tool_block.get("result")

    if tool_name is None:
        tool_name = data.get("tool_name") or data.get("toolName")
    if tool_input is None:
        tool_input = (
            data.get("tool_input")
            or data.get("toolInput")
            or data.get("input")
            or data.get("arguments")
            or data.get("params")
        )
    if tool_output is None:
        tool_output = data.get("tool_output") or data.get("toolOutput") or data.get(
            "output"
        ) or data.get("result")

    if tool_name or tool_input or tool_output:
        return CodexMessage(
            kind="tool",
            raw=data,
            event_type=raw_type,
            tool_name=tool_name if isinstance(tool_name, str) else None,
            tool_input=tool_input if isinstance(tool_input, dict) else None,
            tool_output=tool_output,
            status=status or raw_type,
            session_id=session_id,
        )

    # Message detection
    role = data.get("role")
    content = data.get("content")
    if isinstance(data.get("message"), dict):
        message_block = data["message"]
        role = role or message_block.get("role")
        content = content or message_block.get("content")

    if isinstance(role, str):
        return CodexMessage(
            kind="item",
            raw=data,
            event_type=raw_type,
            role=role,
            text=_extract_text(content),
            status=status or raw_type,
            session_id=session_id,
        )

    # Delta detection
    if (raw_type and "delta" in raw_type) or "delta" in data:
        delta = data.get("delta") if data.get("delta") is not None else data.get("text")
        return CodexMessage(
            kind="item",
            raw=data,
            event_type=raw_type,
            item_type="delta",
            text=_extract_text(delta),
            status=status or raw_type,
            session_id=session_id,
        )

    # Result / completion detection
    if raw_type in FINAL_TYPES or data.get("final") is True:
        return CodexEvent(
            kind="turn",
            event=data,
            event_type=raw_type,
            status=status or raw_type,
            session_id=session_id,
        )

    if raw_type is None and status in FINAL_STATUSES:
        return CodexEvent(
            kind="turn",
            event=data,
            event_type=raw_type,
            status=status,
            session_id=session_id,
        )

    return CodexEvent(
        kind="raw",
        event=data,
        event_type=raw_type,
        status=status,
        session_id=session_id,
    )


def default_final_event_predicate(message: Message) -> bool:
    """Default predicate to stop streaming when a final event is observed."""
    if isinstance(message, CodexMessage):
        if message.kind == "error":
            return True
        raw = message.raw
    else:
        raw = message.event

    raw_type = _get_raw_type(raw)
    status = raw.get("status") if isinstance(raw.get("status"), str) else None

    if raw_type in FINAL_TYPES or raw.get("final") is True:
        return True

    if raw_type and raw_type.startswith("turn."):
        if raw_type.endswith("completed") or status in FINAL_STATUSES:
            return True

    if raw_type and raw_type.startswith(("item.", "thread.")):
        return False

    if status in FINAL_STATUSES and raw_type is None:
        return True

    return False
