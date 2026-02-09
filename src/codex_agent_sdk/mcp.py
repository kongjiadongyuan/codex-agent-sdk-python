"""MCP helper calls for the Codex app-server."""

from typing import Any

from ._internal.app_server_client import AppServerClient
from .types import CodexAgentOptions


async def mcp_status_list(options: CodexAgentOptions | None = None) -> dict[str, Any]:
    """List MCP server statuses via Codex app-server."""
    if options is None:
        options = CodexAgentOptions()
    client = AppServerClient(options)
    await client.start()
    try:
        return await client.mcp_status_list()
    finally:
        await client.close()


async def mcp_reload(options: CodexAgentOptions | None = None) -> dict[str, Any]:
    """Reload MCP server configuration via Codex app-server."""
    if options is None:
        options = CodexAgentOptions()
    client = AppServerClient(options)
    await client.start()
    try:
        return await client.mcp_reload()
    finally:
        await client.close()
