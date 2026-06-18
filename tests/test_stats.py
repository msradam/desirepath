import asyncio
import json
import socket

import pytest
from claude_code_sdk import ClaudeCodeOptions, ResultMessage, query
from fastmcp import Client


@pytest.mark.asyncio
async def test_stats_resource_direct(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.read_resource("graph://piedmont/stats")
        data = json.loads(result[0].text)
        assert "n" in data
        assert data["n"] > 0
        assert "orientation_entropy" in data
        assert data["orientation_entropy"] > 0
        assert "dead_end_count" in data


@pytest.mark.asyncio
async def test_street_hierarchy_resource_direct(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.read_resource("graph://piedmont/street-hierarchy")
        data = json.loads(result[0].text)
        assert isinstance(data, dict)
        assert len(data) > 0


@pytest.mark.asyncio
async def test_stats_with_haiku(mcp_server):
    """Haiku reports basic stats and orientation entropy for the Piedmont network."""
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
                        "What are the key statistics for this Piedmont, California street network? "
                        "Report the node count, average street length, and orientation entropy."
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
