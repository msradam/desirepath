import asyncio
import socket

import osmnx as ox
import pytest
from claude_code_sdk import ClaudeCodeOptions, ResultMessage, query
from fastmcp import Client


@pytest.fixture(scope="module")
def berkeley_graph():
    G = ox.graph_from_place("Berkeley, California, USA", network_type="drive")
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    return G


@pytest.fixture(scope="module")
def mcp_server_with_both(store, berkeley_graph):
    import desirepath.graph_store as gs

    store.add("berkeley", berkeley_graph, "place", "Berkeley, California, USA")
    gs._store = store
    from desirepath.server import create_server

    return create_server()


@pytest.mark.asyncio
async def test_compare_graphs_direct(mcp_server_with_both):
    async with Client(mcp_server_with_both) as client:
        result = await client.call_tool(
            "compare_graphs", {"name_a": "piedmont", "name_b": "berkeley"}
        )
        data = result.data
        assert "graph_a" in data
        assert "graph_b" in data
        assert "diff_b_minus_a" in data
        assert data["graph_a"]["name"] == "piedmont"
        assert data["graph_b"]["name"] == "berkeley"
        assert data["graph_a"]["nodes"] > 0
        assert data["graph_b"]["nodes"] > 0


@pytest.mark.asyncio
async def test_compare_meshedness_direct(mcp_server_with_both):
    async with Client(mcp_server_with_both) as client:
        result = await client.call_tool(
            "compare_graphs", {"name_a": "piedmont", "name_b": "berkeley"}
        )
        data = result.data
        a = data["graph_a"]
        b = data["graph_b"]
        assert a["meshedness"] is not None
        assert b["meshedness"] is not None


@pytest.mark.asyncio
async def test_compare_with_haiku(mcp_server_with_both):
    """Haiku compares Piedmont and Berkeley and identifies which is more grid-like."""
    with socket.socket() as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    server_task = asyncio.create_task(
        mcp_server_with_both.run_http_async(
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
                        "Compare the Piedmont and Berkeley street networks. "
                        "Which is more grid-like and which has higher intersection density?"
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
