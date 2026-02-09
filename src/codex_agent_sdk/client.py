"""Codex SDK Client for interacting with Codex CLI."""

from __future__ import annotations

import inspect
import warnings
from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import replace
from typing import Any, cast

from ._errors import CLIConnectionError
from ._internal.app_server_client import AppServerClient
from ._internal.message_parser import default_final_event_predicate
from .query import query as query_fn
from .types import CodexAgentOptions, Message

_UNSET = object()

PromptInput = str | AsyncIterable[str] | AsyncIterable[dict[str, Any]] | None


class CodexSDKClient:
    """Client for one-shot and session-style Codex interactions.

    - One-shot: use `run(...)` for prompt-in, event-stream-out calls.
    - Session-style: `connect()` -> `query(...)` -> `receive_response()`.

    The client tracks the latest session/thread id from events and can resume
    follow-up calls automatically.
    """

    def __init__(self, options: CodexAgentOptions | None = None):
        if options is None:
            options = CodexAgentOptions()
        self.options = options
        self._last_session_id: str | None = None
        self._connected = False
        self._active_stream: AsyncIterator[Message] | None = None
        self._session_model: str | None = None
        self._connect_resume_session: str | None = None
        self._connect_resume_last = False
        self._connect_resume_all = False

    @property
    def last_session_id(self) -> str | None:
        return self._last_session_id

    def _update_session_id(self, event: Message) -> None:
        session_id = getattr(event, "session_id", None)
        if isinstance(session_id, str):
            self._last_session_id = session_id
            return

        raw = getattr(event, "raw", None)
        if raw is None:
            raw = getattr(event, "event", {})
        if isinstance(raw, dict):
            for key in [
                "session_id",
                "sessionId",
                "session",
                "conversation_id",
                "conversationId",
                "thread_id",
                "threadId",
            ]:
                value = raw.get(key)
                if isinstance(value, str):
                    self._last_session_id = value
                    return

    def _resolve_model(self, model: str | None) -> str | None:
        if model is not None:
            return model
        if self._session_model is not None:
            return self._session_model
        return self.options.model

    async def _close_stream(self, stream: AsyncIterator[Message] | None) -> None:
        if stream is None:
            return
        aclose = getattr(stream, "aclose", None)
        if callable(aclose):
            result = aclose()
            if inspect.isawaitable(result):
                await result

    async def connect(
        self,
        *,
        session_id: str | None = None,
        resume_last: bool = False,
        resume_all: bool = False,
        model: str | None = None,
    ) -> None:
        """Enter session-style mode.

        This method configures defaults for subsequent `query(...)` calls.
        It does not eagerly start a subprocess.
        """
        if session_id and (resume_last or resume_all):
            raise CLIConnectionError(
                "Provide either session_id or resume_last/resume_all, not both."
            )
        if resume_last and resume_all:
            raise CLIConnectionError("resume_last and resume_all cannot both be true.")

        self._connected = True
        self._session_model = model
        self._connect_resume_session = session_id
        self._connect_resume_last = resume_last
        self._connect_resume_all = resume_all

    async def disconnect(self) -> None:
        """Exit session-style mode and close any in-flight response stream."""
        await self._close_stream(self._active_stream)
        self._active_stream = None
        self._connected = False
        self._session_model = None
        self._connect_resume_session = None
        self._connect_resume_last = False
        self._connect_resume_all = False

    async def __aenter__(self) -> CodexSDKClient:
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        _ = exc_type
        _ = exc_val
        _ = exc_tb
        await self.disconnect()
        return False

    async def run(
        self,
        prompt: PromptInput,
        *,
        session_id: str | None = None,
        resume_last: bool | None = None,
        resume_all: bool | None = None,
        model: str | None = None,
    ) -> AsyncIterator[Message]:
        """Run a one-shot Codex query and stream events."""
        resolved_resume_last = bool(resume_last)
        resolved_resume_all = bool(resume_all)
        resolved_session_id = session_id

        if resolved_session_id and (resolved_resume_last or resolved_resume_all):
            raise CLIConnectionError(
                "Provide either session_id or resume_last/resume_all, not both."
            )
        if resolved_resume_last and resolved_resume_all:
            raise CLIConnectionError("resume_last and resume_all cannot both be true.")

        if (
            resolved_session_id is None
            and not resolved_resume_last
            and not resolved_resume_all
        ):
            resolved_session_id = self._last_session_id

        options = self.options
        if resolved_session_id or resolved_resume_last or resolved_resume_all:
            options = replace(
                options,
                resume_session=resolved_session_id,
                resume_last=resolved_resume_last,
                resume_all=resolved_resume_all,
            )

        resolved_model = self._resolve_model(model)
        if resolved_model is not None:
            options = replace(options, model=resolved_model)

        async for event in query_fn(prompt=prompt, options=options):
            self._update_session_id(event)
            yield event

    async def query(
        self,
        prompt: PromptInput,
        *,
        session_id: str | None = None,
        resume_last: bool | None = None,
        resume_all: bool | None = None,
        model: str | None = None,
    ) -> None:
        """Send a request in session-style mode.

        Call `receive_messages()` or `receive_response()` to consume events.
        """
        if not self._connected:
            raise CLIConnectionError("Not connected. Call connect() first.")
        if self._active_stream is not None:
            raise CLIConnectionError(
                "A previous response is still active. "
                "Consume it via receive_messages()/receive_response() first."
            )

        use_session_id = session_id
        use_resume_last = resume_last
        use_resume_all = resume_all

        if (
            use_session_id is None
            and use_resume_last is None
            and use_resume_all is None
        ):
            if self._last_session_id is None:
                use_session_id = self._connect_resume_session
                if use_session_id is None:
                    use_resume_last = self._connect_resume_last
                    use_resume_all = self._connect_resume_all

        self._active_stream = self.run(
            prompt=prompt,
            session_id=use_session_id,
            resume_last=use_resume_last,
            resume_all=use_resume_all,
            model=model,
        )

    async def receive_messages(self) -> AsyncIterator[Message]:
        """Receive all events for the active session-style request."""
        if not self._connected:
            raise CLIConnectionError("Not connected. Call connect() first.")
        if self._active_stream is None:
            raise CLIConnectionError(
                "No active request. Call query(...) before receive_messages()."
            )

        stream = self._active_stream
        self._active_stream = None
        try:
            async for event in stream:
                yield event
        finally:
            await self._close_stream(stream)

    async def receive_response(
        self,
        prompt: PromptInput | object = _UNSET,
        *,
        session_id: str | None = None,
        resume_last: bool | None = None,
        resume_all: bool | None = None,
        model: str | None = None,
    ) -> AsyncIterator[Message]:
        """Receive events until a final event is observed.

        Preferred usage (Claude-style):
            - `await client.query("...")`
            - `async for event in client.receive_response(): ...`

        Backward-compatible usage:
            - `async for event in client.receive_response(prompt="..."): ...`
        """
        predicate = self.options.final_event_predicate or default_final_event_predicate

        use_legacy_call = (
            prompt is not _UNSET
            or session_id is not None
            or resume_last is not None
            or resume_all is not None
            or model is not None
        )

        if use_legacy_call:
            warnings.warn(
                "receive_response(prompt=...) is deprecated. "
                "Use connect() + query(...) + receive_response() or run(...).",
                DeprecationWarning,
                stacklevel=2,
            )
            compat_prompt = cast(PromptInput, None if prompt is _UNSET else prompt)
            stream: AsyncIterator[Message] = self.run(
                prompt=compat_prompt,
                session_id=session_id,
                resume_last=resume_last,
                resume_all=resume_all,
                model=model,
            )
        else:
            stream = self.receive_messages()

        try:
            async for event in stream:
                yield event
                if predicate(event):
                    break
        finally:
            await self._close_stream(stream)

    async def interrupt(self) -> None:
        """Best-effort interruption by closing the active response stream."""
        if not self._connected:
            raise CLIConnectionError("Not connected. Call connect() first.")
        await self._close_stream(self._active_stream)
        self._active_stream = None

    async def set_model(self, model: str | None = None) -> None:
        """Set session default model for subsequent `query(...)` calls."""
        if not self._connected:
            raise CLIConnectionError("Not connected. Call connect() first.")
        self._session_model = model

    async def mcp_status_list(self) -> dict[str, Any]:
        """List MCP server statuses via the Codex app-server."""
        client = AppServerClient(self.options)
        await client.start()
        try:
            return await client.mcp_status_list()
        finally:
            await client.close()

    async def mcp_reload(self) -> dict[str, Any]:
        """Reload MCP server configuration via the Codex app-server."""
        client = AppServerClient(self.options)
        await client.start()
        try:
            return await client.mcp_reload()
        finally:
            await client.close()
