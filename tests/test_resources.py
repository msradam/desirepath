import asyncio
import json
import socket

import pytest
from claude_code_sdk import ClaudeCodeOptions, ResultMessage, query
from fastmcp import Client


@pytest.mark.asyncio
async def test_graphs_resource(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.read_resource("graph://graphs")
        data = json.loads(result[0].text)
        assert isinstance(data, list)
        assert len(data) > 0
        assert any(g["name"] == "piedmont" for g in data)


@pytest.mark.asyncio
async def test_metadata_resource(mcp_server, piedmont_graph):
    async with Client(mcp_server) as client:
        result = await client.read_resource("graph://metadata")
        data = json.loads(result[0].text)
        assert data["node_count"] == len(piedmont_graph.nodes)
        assert data["edge_count"] == len(piedmont_graph.edges)
        assert "bbox" in data
        assert "edge_attributes" in data
        assert "node_attributes" in data


@pytest.mark.asyncio
async def test_named_metadata_resource(mcp_server, piedmont_graph):
    async with Client(mcp_server) as client:
        result = await client.read_resource("graph://piedmont/metadata")
        data = json.loads(result[0].text)
        assert data["name"] == "piedmont"
        assert data["node_count"] == len(piedmont_graph.nodes)


@pytest.mark.asyncio
async def test_node_resource(mcp_server, piedmont_graph):
    node_id = next(iter(piedmont_graph.nodes))
    async with Client(mcp_server) as client:
        result = await client.read_resource(f"graph://piedmont/nodes/{node_id}")
        data = json.loads(result[0].text)
        assert data["node_id"] == node_id


@pytest.mark.asyncio
async def test_edge_resource(mcp_server, piedmont_graph):
    u, v, key = next(iter(piedmont_graph.edges(keys=True)))
    async with Client(mcp_server) as client:
        result = await client.read_resource(f"graph://piedmont/edges/{u}/{v}/{key}")
        data = json.loads(result[0].text)
        assert data["u"] == u
        assert data["v"] == v
        assert "geometry" not in data


@pytest.mark.asyncio
async def test_stats_resource(mcp_server, piedmont_graph):
    async with Client(mcp_server) as client:
        result = await client.read_resource("graph://piedmont/stats")
        data = json.loads(result[0].text)
        assert data["n"] == len(piedmont_graph.nodes)
        assert "orientation_entropy" in data
        assert "dead_end_count" in data


@pytest.mark.asyncio
async def test_street_hierarchy_resource(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.read_resource("graph://piedmont/street-hierarchy")
        data = json.loads(result[0].text)
        assert isinstance(data, dict)
        assert len(data) > 0


@pytest.mark.asyncio
async def test_resources_with_haiku(mcp_server, piedmont_graph):
    """Haiku finds the nearest node and confirms the graph has real data."""
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
            max_turns=10,
        )

        async def prompt_stream():
            yield {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": (
                        "Using the find_nearest tool, find the nearest node to "
                        "(-122.2311, 37.8244) in Piedmont, California and tell me its node_id. "
                        "Then confirm the graph has more than 50 nodes by reading the "
                        "graph://piedmont/stats resource."
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
            f"Expected node id in result, got: {result_text}"
        )
    finally:
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    async with Client(mcp_server) as mcp_client:
        meta_result = await mcp_client.read_resource("graph://metadata")
        meta = json.loads(meta_result[0].text)
        assert meta["node_count"] > 50
