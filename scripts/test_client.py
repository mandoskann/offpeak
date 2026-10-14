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

        calls = [
            ("get_live_price", {}),
            ("get_price_forecast", {"hours": 24}),
            ("find_cheapest_time", {"duration_hours": 4, "finish_by_hour": 7, "can_split": True, "energy_kwh": 40}),
            ("find_cheapest_time", {"duration_hours": 2}),
        ]
        for name, args in calls:
            result = await client.call_tool(name, args)
            print(f"{name}({args})")
            print("  ->", result.data.get("spoken"), "\n")

        if os.getenv("VERBOSE"):
            full = await client.call_tool("find_cheapest_time", calls[2][1])
            print(json.dumps(full.data, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
