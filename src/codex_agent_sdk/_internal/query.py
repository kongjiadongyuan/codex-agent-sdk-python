"""Query class for handling Codex exec output."""

import json
import logging
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import suppress
from typing import Any

import anyio

from .._errors import ProtocolStreamError
from .transport import Transport

logger = logging.getLogger(__name__)
_CONTROL_KEY = "__codex_agent_sdk_control__"


class Query:
    """Handles message streaming on top of Transport."""

    def __init__(self, transport: Transport):
        self.transport = transport
        self._message_send, self._message_receive = anyio.create_memory_object_stream[
            dict[str, Any]
        ](max_buffer_size=100)
        self._tg: anyio.abc.TaskGroup | None = None
        self._closed = False

    async def start(self) -> None:
        """Start reading messages from transport."""
        if self._tg is None:
            self._tg = anyio.create_task_group()
            await self._tg.__aenter__()
            self._tg.start_soon(self._read_messages)

    async def _read_messages(self) -> None:
        """Read messages from transport and route them."""
        try:
            async for message in self.transport.read_messages():
                if self._closed:
                    break
                await self._message_send.send(message)
        except anyio.get_cancelled_exc_class():
            logger.debug("Read task cancelled")
            raise
        except Exception as e:
            logger.error(f"Fatal error in message reader: {e}")
            await self._message_send.send({_CONTROL_KEY: "error", "error": str(e)})
        finally:
            await self._message_send.send({_CONTROL_KEY: "end"})

    async def stream_input(
        self, stream: AsyncIterable[str] | AsyncIterable[dict[str, Any]]
    ) -> None:
        """Stream input chunks to transport."""
        try:
            async for message in stream:
                if self._closed:
                    break
                if isinstance(message, dict):
                    await self.transport.write(json.dumps(message))
                else:
                    await self.transport.write(str(message))
            await self.transport.end_input()
        except Exception as e:
            logger.debug(f"Error streaming input: {e}")

    async def receive_messages(self) -> AsyncIterator[dict[str, Any]]:
        """Receive SDK messages (not control messages)."""
        async for message in self._message_receive:
            if message.get(_CONTROL_KEY) == "end":
                break
            if message.get(_CONTROL_KEY) == "error":
                error_text = message.get("error", "Unknown error")
                raise ProtocolStreamError(f"Query stream failed: {error_text}")
            yield message

    async def close(self) -> None:
        """Close the query and transport."""
        self._closed = True
        if self._tg:
            self._tg.cancel_scope.cancel()
            with suppress(anyio.get_cancelled_exc_class(), RuntimeError):
                await self._tg.__aexit__(None, None, None)
            self._tg = None
        await self.transport.close()

    def __aiter__(self) -> AsyncIterator[dict[str, Any]]:
        return self.receive_messages()
