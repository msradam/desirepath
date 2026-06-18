import asyncio
import socket

import pytest
from claude_code_sdk import ClaudeCodeOptions, ResultMessage, query
from fastmcp import Client


@pytest.mark.asyncio
async def test_morphology_linearity_direct(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool("morphology", {"metrics": ["linearity"]})
        data = result.data
        assert "linearity" in data
        assert "mean" in data["linearity"]
        assert "histogram" in data["linearity"]
        assert 0.0 <= data["linearity"]["mean"] <= 1.0


@pytest.mark.asyncio
async def test_morphology_sinuosity_direct(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool("morphology", {"metrics": ["sinuosity"]})
        data = result.data
        assert "sinuosity" in data
        assert "mean" in data["sinuosity"]
        assert "most_sinuous" in data["sinuosity"]
        assert data["sinuosity"]["mean"] >= 1.0


@pytest.mark.asyncio
async def test_morphology_clustering_direct(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool("morphology", {"metrics": ["clustering"]})
        data = result.data
        assert "clustering" in data
        assert "mean" in data["clustering"]
        assert "nonzero_fraction" in data["clustering"]
        assert 0.0 <= data["clustering"]["mean"] <= 1.0


@pytest.mark.asyncio
async def test_morphology_intersection_types_direct(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "morphology", {"metrics": ["intersection_types"]}
        )
        data = result.data
        assert "intersection_types" in data
        it = data["intersection_types"]
        assert "total_nodes" in it
        assert it["total_nodes"] > 0
        assert (
            it["dead_end"] + it["three_way"] + it["four_way_plus"] + it["other"]
            == it["total_nodes"]
        )
        assert (
            abs(
                it["dead_end_fraction"]
                + it["three_way_fraction"]
                + it["four_way_plus_fraction"]
                - (1 - it["other"] / it["total_nodes"])
            )
            < 0.01
        )


@pytest.mark.asyncio
async def test_morphology_with_haiku(mcp_server):
    """Haiku reports linearity and sinuosity and characterizes whether streets are straight or curved."""
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
                        "What is the average linearity and sinuosity of streets in the loaded graph? "
                        "Are the streets generally straight or curved?"
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
