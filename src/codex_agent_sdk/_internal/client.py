"""Internal client implementation."""

import inspect
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any

from .._errors import HookAbort
from ..types import CodexAgentOptions, EventHook, Message
from .app_server_client import AppServerClient
from .message_parser import parse_message
from .query import Query
from .transport import Transport
from .transport.subprocess_cli import SubprocessCLITransport


class InternalClient:
    """Internal client implementation."""

    async def _run_hooks(self, hooks: list[EventHook], message: Message) -> None:
        for hook in hooks:
            result = hook(message)
            if inspect.isawaitable(result):
                await result

    async def process_query(
        self,
        prompt: str | AsyncIterable[str] | AsyncIterable[dict[str, Any]] | None,
        options: CodexAgentOptions,
        transport: Transport | None = None,
    ) -> AsyncIterator[Message]:
        """Process a query through transport and Query."""
        use_app_server = options.use_app_server or bool(options.dynamic_tools)

        if use_app_server:
            if prompt is None or not isinstance(prompt, str):
                raise ValueError(
                    "App-server mode currently requires a string prompt."
                )
            if options.resume_last or options.resume_all:
                raise ValueError(
                    "App-server resume_last/resume_all is not supported; "
                    "provide resume_session instead."
                )
            client = AppServerClient(options)
            parser = options.event_parser or parse_message
            hooks = options.event_hooks or {}

            try:
                async for data in client.run_query(prompt):
                    message = parser(data)
                    hook_list = hooks.get("*", [])
                    if hook_list:
                        await self._run_hooks(hook_list, message)

                    if hasattr(message, "kind") and isinstance(message.kind, str):
                        typed_hooks = hooks.get(message.kind, [])
                        if typed_hooks:
                            await self._run_hooks(typed_hooks, message)

                    yield message
            except HookAbort:
                return
            finally:
                await client.close()
            return

        if transport is not None:
            chosen_transport = transport
        else:
            chosen_transport = SubprocessCLITransport(prompt=prompt, options=options)

        await chosen_transport.connect()

        query = Query(transport=chosen_transport)

        parser = options.event_parser or parse_message
        hooks = options.event_hooks or {}

        try:
            await query.start()

            if isinstance(prompt, AsyncIterable) and query._tg:
                query._tg.start_soon(query.stream_input, prompt)

            async for data in query.receive_messages():
                message = parser(data)
                hook_list = hooks.get("*", [])
                if hook_list:
                    await self._run_hooks(hook_list, message)

                if hasattr(message, "kind") and isinstance(message.kind, str):
                    typed_hooks = hooks.get(message.kind, [])
                    if typed_hooks:
                        await self._run_hooks(typed_hooks, message)

                yield message

        except HookAbort:
            return
        finally:
            await query.close()
