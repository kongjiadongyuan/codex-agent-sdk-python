"""Error types for Codex SDK."""

from typing import Any


class CodexSDKError(Exception):
    """Base exception for all Codex SDK errors."""


class CLIConnectionError(CodexSDKError):
    """Raised when unable to connect to Codex CLI."""


class RequestTimeoutError(CLIConnectionError):
    """Raised when waiting for a Codex app-server request times out."""

    def __init__(self, method: str, timeout_seconds: float):
        super().__init__(
            f"Timed out waiting for app-server response for {method!r} after "
            f"{timeout_seconds:.2f}s."
        )
        self.method = method
        self.timeout_seconds = timeout_seconds


class ProtocolStreamError(CodexSDKError):
    """Raised when the SDK stream/control protocol encounters an error."""

    def __init__(
        self,
        message: str,
        *,
        method: str | None = None,
        payload: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.method = method
        self.payload = payload


class ApprovalDecisionError(CodexSDKError):
    """Raised when an approval callback returns an invalid decision."""


class CLINotFoundError(CLIConnectionError):
    """Raised when Codex CLI is not found or not installed."""

    def __init__(
        self, message: str = "Codex CLI not found", cli_path: str | None = None
    ):
        if cli_path:
            message = f"{message}: {cli_path}"
        super().__init__(message)


class ProcessError(CodexSDKError):
    """Raised when the CLI process fails."""

    def __init__(
        self, message: str, exit_code: int | None = None, stderr: str | None = None
    ):
        self.exit_code = exit_code
        self.stderr = stderr

        if exit_code is not None:
            message = f"{message} (exit code: {exit_code})"
        if stderr:
            message = f"{message}\nError output: {stderr}"

        super().__init__(message)


class CLIJSONDecodeError(CodexSDKError):
    """Raised when unable to decode JSON from CLI output."""

    def __init__(self, line: str, original_error: Exception):
        self.line = line
        self.original_error = original_error
        super().__init__(f"Failed to decode JSON: {line[:100]}...")


class MessageParseError(CodexSDKError):
    """Raised when unable to parse a message from CLI output."""

    def __init__(self, message: str, data: dict[str, Any] | None = None):
        self.data = data
        super().__init__(message)


class HookAbort(CodexSDKError):
    """Raised by hooks to abort streaming early."""

    def __init__(self, reason: str = "Hook aborted streaming"):
        super().__init__(reason)
