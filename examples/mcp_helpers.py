import anyio

from codex_agent_sdk import CodexSDKClient


async def main():
    client = CodexSDKClient()
    print(await client.mcp_status_list())
    print(await client.mcp_reload())


anyio.run(main)
