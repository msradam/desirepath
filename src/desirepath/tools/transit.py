import asyncio

from fastmcp import Context, FastMCP

from desirepath.graph_store import GraphStore


def register(mcp: FastMCP, store: GraphStore) -> None:
    @mcp.tool
    async def load_graph_from_gtfs(
        path: str,
        name: str = "transit",
        agency_id: str | None = None,
        ctx: Context | None = None,
    ) -> dict:
        """
        Load a transit network graph from a GTFS zip file.

        Requires city2graph (uv add "desirepath[transit]").
        path: absolute path to a GTFS .zip file.
        name: graph name for multi-graph sessions.
        agency_id: filter to a specific transit agency (loads all agencies if omitted).

        Returns a MultiDiGraph where nodes are stops and edges are direct-service
        connections. All desirepath graph tools work on the resulting graph.
        """
        try:
            import city2graph as c2g
        except ImportError:
            raise RuntimeError(
                "city2graph is required for load_graph_from_gtfs. "
                "Install with: uv add 'desirepath[transit]'"
            )

        if ctx:
            await ctx.info(f"Parsing GTFS feed from {path}...")
            await ctx.report_progress(0, 2)

        kwargs = {}
        if agency_id is not None:
            kwargs["agency_id"] = agency_id

        G = await asyncio.to_thread(c2g.from_gtfs, path, **kwargs)

        store.add(name, G, source="gtfs", description=path)

        if ctx:
            await ctx.report_progress(2, 2)

        return {
            "status": "loaded",
            "name": name,
            "source": "gtfs",
            "node_count": len(G.nodes),
            "edge_count": len(G.edges),
        }
