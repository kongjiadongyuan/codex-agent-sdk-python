"""Type definitions for Codex SDK."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

SandboxMode = Literal["read-only", "workspace-write", "danger-full-access"]
ApprovalPolicy = Literal["untrusted", "on-failure", "on-request", "never"]
ApprovalDecision = Literal["allow", "deny", "defer"]
ColorMode = Literal["always", "never", "auto"]
EventKind = Literal["thread", "turn", "item", "tool", "log", "error", "raw"]


class ToolHandler(Protocol):
    async def __call__(self, args: dict[str, Any]) -> Any: ...


@dataclass
class CodexTool:
    """Dynamic tool exposed to Codex via app-server protocol."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler


@dataclass
class CodexEvent:
    """Coarse-grained event wrapper for Codex JSON events."""

    kind: EventKind
    event: dict[str, Any]
    event_type: str | None = None
    status: str | None = None
    session_id: str | None = None
    item_type: str | None = None

    @property
    def raw(self) -> dict[str, Any]:
        return self.event


@dataclass
class CodexMessage:
    """Best-effort structured view of a Codex JSON event."""

    kind: EventKind
    raw: dict[str, Any]
    event_type: str | None = None
    item_type: str | None = None
    role: str | None = None
    text: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_output: Any | None = None
    status: str | None = None
    error: str | None = None
    session_id: str | None = None


Message = CodexMessage | CodexEvent

EventHook = Callable[[Message], Awaitable[None] | None]
EventHooks = dict[str, list[EventHook]]
EventParser = Callable[[dict[str, Any]], Message]
FinalEventPredicate = Callable[[Message], bool]
ApprovalCallbackResult = str | dict[str, Any] | None
ApprovalCallback = Callable[
    [dict[str, Any]], Awaitable[ApprovalCallbackResult] | ApprovalCallbackResult
]


@dataclass
class CodexAgentOptions:
    """Options for running Codex CLI via the SDK."""

    # CLI path
    cli_path: str | Path | None = None

    # Model/provider selection
    # Default model for all calls; per-call `model=` overrides this value.
    model: str | None = None
    oss: bool = False

    # Execution safety
    sandbox: SandboxMode | None = None
    ask_for_approval: ApprovalPolicy | None = None
    full_auto: bool = False
    yolo: bool = False

    # Config/profile
    profile: str | None = None
    config_overrides: dict[str, Any] = field(default_factory=dict)
    config_kv: list[str] = field(default_factory=list)

    # Workspace
    cwd: str | Path | None = None
    add_dirs: list[str | Path] = field(default_factory=list)
    skip_git_repo_check: bool = False

    # Prompt extras
    images: list[str | Path] = field(default_factory=list)
    search: bool = False

    # Output control
    include_json_events: bool = True
    output_schema: dict[str, Any] | str | Path | None = None
    output_last_message: str | Path | None = None
    color: ColorMode | None = None

    # Resume options for `codex exec resume`
    resume_session: str | None = None
    resume_last: bool = False
    resume_all: bool = False

    # Environment
    inherit_env: bool = True
    env_allowlist: list[str] = field(default_factory=list)
    env_denylist: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)

    # stderr callback
    stderr: Callable[[str], None] | None = None

    # Event parsing + hooks
    event_parser: EventParser | None = None
    event_hooks: EventHooks = field(default_factory=dict)
    final_event_predicate: FinalEventPredicate | None = None

    # App-server mode
    use_app_server: bool = False
    dynamic_tools: list[CodexTool] = field(default_factory=list)

    # Approval callbacks (app-server)
    # Prefer `approval_callbacks={"command": ..., "file_change": ...}`.
    approve_command: ApprovalCallback | None = None
    approve_file_change: ApprovalCallback | None = None
    provide_tool_input: Callable[[dict[str, Any]], str] | None = None
    approval_callbacks: dict[str, ApprovalCallback] = field(default_factory=dict)
    request_user_input_callback: Callable[[dict[str, Any]], Any] | None = None

    # Advanced
    # Timeout for app-server JSON-RPC requests; `None` disables timeout.
    app_server_request_timeout_seconds: float | None = 30.0
    max_buffer_size: int | None = None
    extra_args: dict[str, str | None] = field(default_factory=dict)
