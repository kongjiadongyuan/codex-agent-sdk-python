"""Query function for one-shot interactions with Codex CLI."""

import os
from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import replace
from typing import Any

from ._internal.client import InternalClient
from ._internal.transport import Transport
from .types import CodexAgentOptions, Message


async def query(
    *,
    prompt: str | AsyncIterable[str] | AsyncIterable[dict[str, Any]] | None,
    options: CodexAgentOptions | None = None,
    transport: Transport | None = None,
    model: str | None = None,
) -> AsyncIterator[Message]:
    """Query Codex CLI for a one-shot interaction.

    Args:
        prompt: Prompt text, or an async iterable of text chunks (stdin mode).
        options: Optional configuration (defaults to CodexAgentOptions() if None).
        transport: Optional transport implementation.
        model: Optional model override for this call.

    Yields:
        Codex events (raw JSON event wrapper).
    """
    if options is None:
        options = CodexAgentOptions()

    if model is not None:
        options = replace(options, model=model)

    os.environ["CODEX_SDK_ENTRYPOINT"] = "sdk-py"

    client = InternalClient()

    async for message in client.process_query(
        prompt=prompt, options=options, transport=transport
    ):
        yield message
