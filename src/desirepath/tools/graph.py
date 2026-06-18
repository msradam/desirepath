import asyncio
import math

import osmnx as ox
from fastmcp import Context, FastMCP

from desirepath.graph_store import GraphStore


def register(mcp: FastMCP, store: GraphStore) -> None:
    @mcp.tool
    async def load_graph(
        source: str,
        name: str = "graph",
        place: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
        dist_m: int = 1000,
        path: str | None = None,
        network_type: str = "drive",
        add_speeds: bool = True,
        add_travel_times: bool = True,
        ctx: Context = None,
    ) -> dict:
        """
        Load a street network graph from a place name, coordinate, or GraphML file.

        source: 'place' | 'point' | 'file' | 'pbf'

        For source='place': provide place (geocodable name, e.g. 'Piedmont, California, USA').
          Requires Nominatim to return a polygon. Use 'point' for neighborhoods.
        For source='point': provide lat, lng, dist_m (radius in meters, default 1000).
        For source='file': provide path to a .graphml file saved with save_graph.
        For source='pbf': provide path to a .osm.pbf file from Geofabrik or similar.
          Best for city-scale networks where Overpass would time out. Requires pyrosm
          (uv add "desirepath[loaders]").

        add_speeds / add_travel_times: enrich edges on load (default true; skipped for
          file/pbf if attributes are already present).
        """
        if source == "place":
            if not place:
                raise ValueError("source='place' requires a place argument")
            if ctx:
                await ctx.info(
                    f"Geocoding and downloading {network_type} network for '{place}'..."
                )
                await ctx.report_progress(0, 4)
            G = await asyncio.to_thread(
                ox.graph_from_place, place, network_type=network_type
            )
            description = place

        elif source == "point":
            if lat is None or lng is None:
                raise ValueError("source='point' requires lat and lng arguments")
            if ctx:
                await ctx.info(
                    f"Downloading {network_type} network at ({lat}, {lng}), dist={dist_m}m..."
                )
                await ctx.report_progress(0, 4)
            G = await asyncio.to_thread(
                ox.graph_from_point, (lat, lng), dist=dist_m, network_type=network_type
            )
            description = f"({lat}, {lng}) dist={dist_m}m"

        elif source == "file":
            if not path:
                raise ValueError("source='file' requires a path argument")
            if ctx:
                await ctx.info(f"Loading graph from {path}...")
                await ctx.report_progress(0, 3)
            G = await asyncio.to_thread(ox.load_graphml, path)
            description = path
            add_speeds = add_speeds and not any(
                "speed_kph" in d for _, _, d in G.edges(data=True)
            )
            add_travel_times = add_travel_times and not any(
                "travel_time" in d for _, _, d in G.edges(data=True)
            )

        elif source == "pbf":
            if not path:
                raise ValueError("source='pbf' requires a path argument")
            try:
                import pyrosm
            except ImportError:
                raise RuntimeError(
                    "pyrosm is required for source='pbf'. "
                    "Install with: uv add 'desirepath[loaders]'"
                )
            if ctx:
                await ctx.info(f"Parsing PBF file {path} ({network_type} network)...")
                await ctx.report_progress(0, 3)
            osm = pyrosm.OSM(path)
            nodes_gdf, edges_gdf = await asyncio.to_thread(
                osm.get_network, network_type=network_type, nodes=True
            )
            G = await asyncio.to_thread(
                osm.to_graph,
                nodes_gdf,
                edges_gdf,
                graph_type="networkx",
                osmnx_compatible=True,
            )
            description = path
            add_speeds = add_speeds and not any(
                "speed_kph" in d for _, _, d in G.edges(data=True)
            )
            add_travel_times = add_travel_times and not any(
                "travel_time" in d for _, _, d in G.edges(data=True)
            )

        else:
            raise ValueError(
                f"source must be 'place', 'point', 'file', or 'pbf', got '{source}'"
            )

        if ctx:
            await ctx.info(f"Loaded {len(G.nodes)} nodes, {len(G.edges)} edges.")
            await ctx.report_progress(1, 4)

        if add_speeds:
            if ctx:
                await ctx.info("Imputing edge speeds...")
                await ctx.report_progress(2, 4)
            G = await asyncio.to_thread(ox.add_edge_speeds, G)

        if add_travel_times:
            if ctx:
                await ctx.info("Computing travel times...")
                await ctx.report_progress(3, 4)
            G = await asyncio.to_thread(ox.add_edge_travel_times, G)

        store.add(name, G, source=source, description=description)
        if ctx:
            await ctx.report_progress(4, 4)

        return {
            "status": "loaded",
            "name": name,
            "source": source,
            "node_count": len(G.nodes),
            "edge_count": len(G.edges),
            "network_type": G.graph.get("network_type", network_type),
        }

    @mcp.tool
    async def save_graph(
        path: str,
        graph_name: str = None,
        ctx: Context = None,
    ) -> dict:
        """
        Save a graph to a GraphML file for fast reloading.

        path: destination file path (created or overwritten).
        graph_name: graph to save (default: active graph).

        Use after a slow city-scale download to avoid re-downloading.
        """
        G = store.get(graph_name)
        active = graph_name or store.active_name
        if ctx:
            await ctx.info(f"Saving '{active}' ({len(G.nodes)} nodes) to {path}...")
        await asyncio.to_thread(ox.save_graphml, G, path)
        return {"status": "saved", "name": active, "path": path}

    @mcp.tool
    def set_active_graph(name: str) -> dict:
        """
        Switch the active graph by name.

        All tools operate on the active graph by default.
        Use the graph://graphs resource to see available names.
        """
        store.set_active(name)
        G = store.get(name)
        return {
            "active": name,
            "node_count": len(G.nodes),
            "edge_count": len(G.edges),
        }

    @mcp.tool
    def drop_graph(name: str) -> dict:
        """
        Remove a named graph from memory.

        If the dropped graph was active, the active graph switches to the
        next available graph (or None if none remain).
        """
        node_count = len(store.get(name).nodes)
        store.drop(name)
        return {
            "dropped": name,
            "nodes_freed": node_count,
            "active": store.active_name,
        }

    @mcp.tool
    async def subgraph(
        source_name: str,
        target_name: str,
        north: float | None = None,
        south: float | None = None,
        east: float | None = None,
        west: float | None = None,
        lat: float | None = None,
        lng: float | None = None,
        dist_m: float | None = None,
        ctx: Context = None,
    ) -> dict:
        """
        Extract a geographic subgraph from a source graph.

        Provide either a bounding box (north, south, east, west) or a center point
        (lat, lng) with dist_m radius. Point mode converts dist_m to a bbox using
        the haversine approximation.

        source_name: name of the loaded graph to extract from.
        target_name: name to store the resulting subgraph under.
        """
        G = store.get(source_name)

        if (
            north is not None
            and south is not None
            and east is not None
            and west is not None
        ):
            bbox = (north, south, east, west)
        elif lat is not None and lng is not None and dist_m is not None:
            dist_deg_lat = dist_m / 111320
            dist_deg_lng = dist_m / (111320 * math.cos(math.radians(lat)))
            north = lat + dist_deg_lat
            south = lat - dist_deg_lat
            east = lng + dist_deg_lng
            west = lng - dist_deg_lng
            bbox = (north, south, east, west)
        else:
            raise ValueError(
                "Provide either (north, south, east, west) or (lat, lng, dist_m)"
            )

        if ctx:
            await ctx.info(
                f"Extracting subgraph from '{source_name}' ({len(G.nodes)} nodes)..."
            )
            await ctx.report_progress(0, 2)

        G_sub = await asyncio.to_thread(
            ox.truncate.truncate_graph_bbox,
            G,
            bbox=bbox,
        )
        store.add(
            target_name,
            G_sub,
            source="subgraph",
            description=f"subgraph from {source_name}",
        )

        if ctx:
            await ctx.report_progress(2, 2)

        return {
            "status": "extracted",
            "source": source_name,
            "target": target_name,
            "node_count": len(G_sub.nodes),
            "edge_count": len(G_sub.edges),
            "bbox": {"north": north, "south": south, "east": east, "west": west},
        }
