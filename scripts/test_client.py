"""Smoke test: connect to the running OffPeak MCP server like an agent would.

Start the server first (python -m offpeak.server), then in a second terminal:
    python scripts/test_client.py
"""

import asyncio
import json
import os

from fastmcp import Client

URL = os.getenv("OFFPEAK_URL", "http://127.0.0.1:8000/mcp")


async def main() -> None:
    async with Client(URL) as client:
        info = client.server_info
        if info:
            print(f"Connected to {info.name} v{info.version}")
        print(f"MCP protocol version: {client.protocol_version}\n")

        tools = await client.list_tools()
        print("Tools:", ", ".join(t.name for t in tools), "\n")

        result = await client.call_tool("get_live_price", {})
        print(json.dumps(result.data, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
