import networkx as nx
from fastmcp import FastMCP

from desirepath.graph_store import get_store
from desirepath.tools import (
    compare,
    enrichment,
    features,
    graph,
    morphology,
    routing,
    stats,
)
from desirepath.tools import map as map_tools
from desirepath.resources import graph as graph_resources
from desirepath.resources import map_app as map_app_resources


def create_server(name: str = "desirepath") -> FastMCP:
    mcp = FastMCP(name, list_page_size=100)
    store = get_store()
    graph.register(mcp, store)
    routing.register(mcp, store)
    stats.register(mcp, store)
    morphology.register(mcp, store)
    features.register(mcp, store)
    enrichment.register(mcp, store)
    compare.register(mcp, store)
    map_tools.register(mcp, store)
    graph_resources.register(mcp, store)
    map_app_resources.register(mcp)

    try:
        import pandana  # noqa: F401

        from desirepath.tools import access

        access.register(mcp, store)
    except ImportError:
        pass

    try:
        import libpysal  # noqa: F401

        from desirepath.tools import spatial_stats

        spatial_stats.register(mcp, store)
    except ImportError:
        pass

    try:
        import city2graph  # noqa: F401

        from desirepath.tools import transit

        transit.register(mcp, store)
    except ImportError:
        pass

    return mcp


def mount(G: nx.MultiDiGraph, name: str = "graph") -> FastMCP:
    """Mount a pre-built NetworkX MultiDiGraph as an MCP server."""
    store = get_store()
    store.add(name, G, source="mount", description=f"Mounted graph: {name}")
    return create_server(name=f"desirepath:{name}")
