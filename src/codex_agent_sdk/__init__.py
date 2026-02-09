"""Codex Agent SDK for Python."""

from typing import Any, Callable

from ._errors import (
    ApprovalDecisionError,
    CLIConnectionError,
    CLIJSONDecodeError,
    CLINotFoundError,
    CodexSDKError,
    HookAbort,
    MessageParseError,
    ProcessError,
    ProtocolStreamError,
    RequestTimeoutError,
)
from ._internal.message_parser import default_final_event_predicate
from ._internal.tool_schema import normalize_tool_input_schema
from ._internal.transport import Transport
from ._version import __version__
from .client import CodexSDKClient
from .mcp import mcp_reload, mcp_status_list
from .query import query
from .types import (
    ApprovalDecision,
    ApprovalPolicy,
    CodexAgentOptions,
    CodexEvent,
    CodexMessage,
    CodexTool,
    ColorMode,
    EventHook,
    EventHooks,
    EventKind,
    EventParser,
    FinalEventPredicate,
    Message,
    SandboxMode,
)

__all__ = [
    "query",
    "__version__",
    "Transport",
    "CodexSDKClient",
    "mcp_status_list",
    "mcp_reload",
    "CodexAgentOptions",
    "CodexEvent",
    "CodexMessage",
    "CodexTool",
    "Message",
    "SandboxMode",
    "ApprovalPolicy",
    "ApprovalDecision",
    "ColorMode",
    "EventHook",
    "EventHooks",
    "EventKind",
    "EventParser",
    "FinalEventPredicate",
    "default_final_event_predicate",
    "CodexSDKError",
    "CLIConnectionError",
    "CLINotFoundError",
    "ProcessError",
    "CLIJSONDecodeError",
    "MessageParseError",
    "HookAbort",
    "RequestTimeoutError",
    "ProtocolStreamError",
    "ApprovalDecisionError",
    "tool",
]


def tool(
    name: str, description: str, input_schema: dict[str, Any]
) -> Callable[[Callable[[dict[str, Any]], Any]], CodexTool]:
    """Decorator for defining dynamic tools for Codex app-server."""

    def decorator(handler: Callable[[dict[str, Any]], Any]) -> CodexTool:
        normalized_schema = normalize_tool_input_schema(input_schema)

        async def async_handler(args: dict[str, Any]) -> Any:
            result = handler(args)
            if hasattr(result, "__await__"):
                return await result  # type: ignore[misc]
            return result

        return CodexTool(
            name=name,
            description=description,
            input_schema=normalized_schema,
            handler=async_handler,
        )

    return decorator
