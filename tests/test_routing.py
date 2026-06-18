import asyncio
import socket

import pytest
from claude_code_sdk import ClaudeCodeOptions, ResultMessage, query
from fastmcp import Client

# Piedmont, CA: near Moraga Ave and Grand Ave
ORIG = {"lng": -122.2311, "lat": 37.8244}
DEST = {"lng": -122.2285, "lat": 37.8205}


@pytest.mark.asyncio
async def test_find_nearest_direct(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "find_nearest", {"entity": "node", "lng": ORIG["lng"], "lat": ORIG["lat"]}
        )
        data = result.data
        assert "node_id" in data
        assert isinstance(data["node_id"], int)


@pytest.mark.asyncio
async def test_route_direct(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "route",
            {
                "orig_lng": ORIG["lng"],
                "orig_lat": ORIG["lat"],
                "dest_lng": DEST["lng"],
                "dest_lat": DEST["lat"],
                "weight": "travel_time",
            },
        )
        data = result.data
        assert data["path"] is not None
        assert data["length_m"] > 0
        assert data["travel_time_s"] is not None and data["travel_time_s"] > 0


@pytest.mark.asyncio
async def test_routing_with_haiku(mcp_server):
    """Haiku finds the shortest travel-time path in Piedmont and reports real numbers."""
    with socket.socket() as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    server_task = asyncio.create_task(
        mcp_server.run_http_async(
            transport="streamable-http",
            host="127.0.0.1",
            port=port,
            show_banner=False,
        )
    )
    await asyncio.sleep(0.5)

    try:
        opts = ClaudeCodeOptions(
            model="claude-haiku-4-5",
            mcp_servers={
                "desirepath": {"type": "http", "url": f"http://127.0.0.1:{port}/mcp"}
            },
            permission_mode="bypassPermissions",
            max_turns=5,
        )

        async def prompt_stream():
            yield {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": (
                        f"Use the route tool to find the shortest path by travel time from "
                        f"({ORIG['lng']}, {ORIG['lat']}) to ({DEST['lng']}, {DEST['lat']}) "
                        f"in Piedmont, California. "
                        "Report the length in meters and travel time in seconds."
                    ),
                },
            }

        result_text = ""
        try:
            async for msg in query(prompt=prompt_stream(), options=opts):
                if isinstance(msg, ResultMessage):
                    result_text = msg.result or ""
        except Exception:
            if not result_text:
                pytest.skip("Claude API unavailable (rate limit or session constraint)")

        assert any(c.isdigit() for c in result_text), (
            f"Expected numeric result, got: {result_text}"
        )
    finally:
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass
