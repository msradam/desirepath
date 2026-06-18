from collections import defaultdict

import numpy as np
import osmnx as ox
from fastmcp import FastMCP

from desirepath.graph_store import GraphStore, GraphEntry


def _serialize(v):
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    if isinstance(v, set):
        return sorted(list(v))
    return v


def _metadata_for(entry: GraphEntry) -> dict:
    G = entry.graph
    nodes, _ = ox.graph_to_gdfs(G)
    return {
        "name": entry.name,
        "source": entry.source,
        "description": entry.description,
        "node_count": len(G.nodes),
        "edge_count": len(G.edges),
        "crs": str(G.graph.get("crs", "EPSG:4326")),
        "network_type": G.graph.get("network_type", "unknown"),
        "bbox": {
            "north": float(nodes.geometry.y.max()),
            "south": float(nodes.geometry.y.min()),
            "east": float(nodes.geometry.x.max()),
            "west": float(nodes.geometry.x.min()),
        },
        "node_attributes": sorted({k for n, d in G.nodes(data=True) for k in d}),
        "edge_attributes": sorted(
            {k for u, v, d in G.edges(data=True) for k in d if k != "geometry"}
        ),
        "has_speeds": any("speed_kph" in d for _, _, d in G.edges(data=True)),
        "has_travel_times": any("travel_time" in d for _, _, d in G.edges(data=True)),
        "has_bearings": any("bearing" in d for _, _, d in G.edges(data=True)),
        "has_grades": any("grade" in d for _, _, d in G.edges(data=True)),
    }


def register(mcp: FastMCP, store: GraphStore) -> None:
    @mcp.resource("graph://graphs")
    def list_graphs() -> list:
        """List all loaded graphs with node/edge counts and which is active."""
        return store.list()

    @mcp.resource("graph://metadata")
    def active_metadata() -> dict:
        """Metadata for the currently active graph."""
        return _metadata_for(store.get_entry())

    @mcp.resource("graph://{name}/metadata")
    def named_metadata(name: str) -> dict:
        """Metadata for a named graph: counts, CRS, bbox, available attributes."""
        return _metadata_for(store.get_entry(name))

    @mcp.resource("graph://{name}/nodes/{node_id}")
    def node(name: str, node_id: int) -> dict:
        """Data for a single node by OSM node id."""
        G = store.get(name)
        if node_id not in G.nodes:
            raise ValueError(f"Node {node_id} not in graph '{name}'")
        return {
            "node_id": node_id,
            **{k: _serialize(v) for k, v in G.nodes[node_id].items()},
        }

    @mcp.resource("graph://{name}/edges/{u}/{v}/{key}")
    def edge(name: str, u: int, v: int, key: int = 0) -> dict:
        """Data for a single edge by (u, v, key). Geometry excluded."""
        G = store.get(name)
        if not G.has_edge(u, v, key):
            raise ValueError(f"Edge ({u},{v},{key}) not in graph '{name}'")
        data = {k: _serialize(v) for k, v in G[u][v][key].items() if k != "geometry"}
        return {"u": u, "v": v, "key": key, **data}

    @mcp.resource("graph://{name}/edge-attributes")
    def edge_attributes(name: str) -> list:
        """List available edge attribute names in a named graph."""
        G = store.get(name)
        return sorted(
            {k for u, v, d in G.edges(data=True) for k in d if k != "geometry"}
        )

    @mcp.resource("graph://{name}/edge-attributes/{attribute}")
    def edge_attribute_values(name: str, attribute: str) -> list:
        """Unique values for a named edge attribute -- instant, no network call."""
        G = store.get(name)
        vals = {d.get(attribute) for u, v, d in G.edges(data=True) if attribute in d}
        return sorted([_serialize(v) for v in vals if v is not None], key=str)

    @mcp.resource("graph://{name}/stats")
    def graph_stats(name: str) -> dict:
        """
        Basic statistics for a named graph: node/edge counts, lengths, densities,
        degree distribution, dead-end count, and orientation entropy.
        All values precomputed from the graph in memory -- no network call.
        """
        entry = store.get_entry(name)
        G = entry.graph

        raw = ox.stats.basic_stats(G)
        out = {}
        for k, v in raw.items():
            if hasattr(v, "item"):
                out[k] = v.item()
            elif isinstance(v, dict):
                out[k] = {
                    str(kk): vv.item() if hasattr(vv, "item") else vv
                    for kk, vv in v.items()
                }
            else:
                out[k] = v

        sample = list(G.edges(data=True))[:1]
        if not sample or "bearing" not in sample[0][2]:
            G = ox.add_edge_bearings(G)
            entry.graph = G
        out["orientation_entropy"] = float(ox.bearing.orientation_entropy(G))

        UG = G.to_undirected()
        out["dead_end_count"] = len([n for n, d in UG.degree() if d == 1])

        return out

    @mcp.resource("graph://{name}/street-hierarchy")
    def street_hierarchy(name: str) -> dict:
        """
        Edge counts and total lengths by highway tag, ordered from motorway to track.
        """
        G = store.get(name)
        counts: dict[str, int] = defaultdict(int)
        lengths: dict[str, float] = defaultdict(float)
        for _, _, data in G.edges(data=True):
            hw = data.get("highway", "unknown")
            if isinstance(hw, list):
                hw = hw[0]
            counts[hw] += 1
            lengths[hw] += data.get("length", 0)

        order = [
            "motorway",
            "motorway_link",
            "trunk",
            "trunk_link",
            "primary",
            "primary_link",
            "secondary",
            "secondary_link",
            "tertiary",
            "tertiary_link",
            "residential",
            "living_street",
            "unclassified",
            "service",
            "footway",
            "cycleway",
            "path",
            "track",
            "unknown",
        ]
        result = {}
        for hw in order:
            if hw in counts:
                result[hw] = {
                    "edge_count": counts[hw],
                    "total_length_m": round(lengths[hw], 1),
                }
        for hw in sorted(counts):
            if hw not in result:
                result[hw] = {
                    "edge_count": counts[hw],
                    "total_length_m": round(lengths[hw], 1),
                }
        return result
