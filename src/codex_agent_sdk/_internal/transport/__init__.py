"""Transport implementations for Codex SDK."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class Transport(ABC):
    """Abstract transport for Codex communication."""

    @abstractmethod
    async def connect(self) -> None:
        """Connect the transport and prepare for communication."""

    @abstractmethod
    async def write(self, data: str) -> None:
        """Write raw data to the transport."""

    @abstractmethod
    def read_messages(self) -> AsyncIterator[dict[str, Any]]:
        """Read and parse messages from the transport."""

    @abstractmethod
    async def close(self) -> None:
        """Close the transport connection and clean up resources."""

    @abstractmethod
    def is_ready(self) -> bool:
        """Check if transport is ready for communication."""

    @abstractmethod
    async def end_input(self) -> None:
        """End the input stream (close stdin for process transports)."""


__all__ = ["Transport"]
