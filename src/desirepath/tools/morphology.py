import momepy
import numpy as np
import osmnx as ox
from fastmcp import FastMCP

from desirepath.graph_store import GraphStore


def register(mcp: FastMCP, store: GraphStore) -> None:
    @mcp.tool
    def morphology(
        metrics: list[str] | None = None,
        graph_name: str | None = None,
    ) -> dict:
        """
        Compute morphological metrics for the street network.

        metrics: list of one or more metrics to compute. Omit for all defaults.
          'linearity':          edge straightness ratio (0 to 1; 1 = perfectly straight).
          'sinuosity':          inverse of linearity (>= 1.0; higher = more winding). Top 10 most sinuous edges included.
          'connectivity':       meshedness coefficient and average node degree. Meshedness near 1 = grid; near 0 = tree.
          'clustering':         squares clustering coefficient per node (how often neighbors form 4-cycles). High = grid-like.
          'intersection_types': global count and fraction of dead-end / 3-way / 4-way-plus intersections.

        Returns a dict with one key per requested metric.
        """
        if metrics is None:
            metrics = ["linearity", "sinuosity", "connectivity"]

        G = store.get(graph_name)
        result = {}

        need_edges = "linearity" in metrics or "sinuosity" in metrics
        need_undirected = "clustering" in metrics or "intersection_types" in metrics
        if need_undirected:
            UG = G.to_undirected()

        if need_edges:
            _, edges = ox.graph_to_gdfs(G)
            edges = edges.copy()
            lin = momepy.linearity(edges)

        if "linearity" in metrics:
            vals = lin.dropna()
            hist, bin_edges = np.histogram(vals, bins=10, range=(0, 1))
            result["linearity"] = {
                "mean": round(float(vals.mean()), 4),
                "median": round(float(vals.median()), 4),
                "std": round(float(vals.std()), 4),
                "histogram": {
                    f"{bin_edges[i]:.1f}-{bin_edges[i + 1]:.1f}": int(hist[i])
                    for i in range(len(hist))
                },
            }

        if "sinuosity" in metrics:
            sin = (1.0 / lin.replace(0, np.nan)).clip(lower=1.0)
            edges["sinuosity"] = sin
            vals = sin.dropna()
            top = (
                edges.loc[vals.index]
                .nlargest(10, "sinuosity")[["name", "highway", "sinuosity", "length"]]
                .copy()
            )
            top["sinuosity"] = top["sinuosity"].round(4)
            result["sinuosity"] = {
                "mean": round(float(vals.mean()), 4) if len(vals) else None,
                "median": round(float(vals.median()), 4) if len(vals) else None,
                "std": round(float(vals.std()), 4) if len(vals) else None,
                "most_sinuous": top.reset_index(drop=True).to_dict(orient="records"),
            }

        if "connectivity" in metrics:
            n = len(G.nodes)
            e = len(G.edges)
            meshedness = (e - n + 1) / (2 * n - 5) if (2 * n - 5) > 0 else None
            result["connectivity"] = {
                "node_count": n,
                "edge_count": e,
                "avg_node_degree": round(sum(dict(G.degree()).values()) / n, 4)
                if n > 0
                else 0,
                "meshedness_coefficient": round(meshedness, 4)
                if meshedness is not None
                else None,
            }

        if "clustering" in metrics:
            G_cl = momepy.clustering(UG, name="cluster")
            cl_vals = np.array(
                [float(G_cl.nodes[n].get("cluster", 0.0)) for n in G_cl.nodes]
            )
            result["clustering"] = {
                "mean": round(float(cl_vals.mean()), 4),
                "median": round(float(np.median(cl_vals)), 4),
                "std": round(float(cl_vals.std()), 4),
                "nonzero_fraction": round(float((cl_vals > 0).mean()), 4),
            }

        if "intersection_types" in metrics:
            counts: dict[str, int] = {
                "dead_end": 0,
                "three_way": 0,
                "four_way_plus": 0,
                "other": 0,
            }
            for _, deg in UG.degree():
                if deg == 1:
                    counts["dead_end"] += 1
                elif deg == 3:
                    counts["three_way"] += 1
                elif deg >= 4:
                    counts["four_way_plus"] += 1
                else:
                    counts["other"] += 1
            total = len(UG.nodes)
            result["intersection_types"] = {
                "total_nodes": total,
                **counts,
                "dead_end_fraction": round(counts["dead_end"] / total, 4)
                if total
                else 0,
                "three_way_fraction": round(counts["three_way"] / total, 4)
                if total
                else 0,
                "four_way_plus_fraction": round(counts["four_way_plus"] / total, 4)
                if total
                else 0,
            }

        return result
