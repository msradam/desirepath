import momepy
import osmnx as ox
from fastmcp import FastMCP

from desirepath.graph_store import GraphStore


def register(mcp: FastMCP, store: GraphStore) -> None:
    @mcp.tool
    def compare_graphs(name_a: str, name_b: str) -> dict:
        """
        Compare two loaded graphs across network stats and morphology.

        Both graphs must already be loaded. Returns a side-by-side dict
        suitable for direct interpretation.
        """

        def summarize(G, name):
            import numpy as np

            stats = ox.stats.basic_stats(G)
            G = ox.add_edge_bearings(G)
            _, edges = ox.graph_to_gdfs(G)
            edges = edges.copy()
            try:
                lin_series = momepy.linearity(edges)
                lin = float(lin_series.mean())
                sin_series = (1.0 / lin_series.replace(0, np.nan)).clip(lower=1.0)
                sin = (
                    float(sin_series.dropna().mean())
                    if len(sin_series.dropna())
                    else None
                )
            except Exception:
                lin = sin = None
            n, e = len(G.nodes), len(G.edges)
            meshedness = (e - n + 1) / (2 * n - 5) if (2 * n - 5) > 0 else None
            return {
                "name": name,
                "nodes": n,
                "edges": e,
                "avg_streets_per_node": round(
                    float(stats.get("streets_per_node_avg", 0)), 3
                ),
                "intersection_count": int(stats.get("intersection_count", 0)),
                "edge_length_total_km": round(
                    float(stats.get("edge_length_total", 0)) / 1000, 2
                ),
                "edge_length_avg_m": round(float(stats.get("edge_length_avg", 0)), 1),
                "circuity_avg": round(float(stats.get("circuity_avg", 0)), 4),
                "orientation_entropy": round(
                    float(ox.bearing.orientation_entropy(G)), 4
                ),
                "avg_linearity": round(lin, 4) if lin is not None else None,
                "avg_sinuosity": round(sin, 4) if sin is not None else None,
                "meshedness": round(meshedness, 4) if meshedness is not None else None,
            }

        a = summarize(store.get(name_a), name_a)
        b = summarize(store.get(name_b), name_b)

        numeric_keys = [
            k
            for k in a
            if k != "name"
            and isinstance(a[k], (int, float))
            and a[k] is not None
            and b[k] is not None
        ]
        diff = {k: round(b[k] - a[k], 4) for k in numeric_keys}

        return {"graph_a": a, "graph_b": b, "diff_b_minus_a": diff}
