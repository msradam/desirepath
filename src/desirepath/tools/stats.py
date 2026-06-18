import asyncio

import networkx as nx
import osmnx as ox
from fastmcp import Context, FastMCP

from desirepath.graph_store import GraphStore

_ELICIT_THRESHOLD = 1000


def _serialize_stats(result: dict) -> dict:
    out = {}
    for k, v in result.items():
        if hasattr(v, "item"):
            out[k] = v.item()
        elif isinstance(v, dict):
            out[k] = {
                str(kk): vv.item() if hasattr(vv, "item") else vv
                for kk, vv in v.items()
            }
        else:
            out[k] = v
    return out


def register(mcp: FastMCP, store: GraphStore) -> None:
    @mcp.tool
    async def betweenness_centrality(
        graph_name: str = None,
        weight: str = "length",
        normalized: bool = True,
        ctx: Context = None,
    ) -> dict:
        """
        Betweenness centrality for all nodes. O(VE); call subgraph first on city-scale data.

        weight: 'length' weights by meters (default); None uses hop count.
        Returns top 10 nodes by score with coordinates and street count.
        """
        G = store.get(graph_name)

        if ctx and len(G.nodes) > _ELICIT_THRESHOLD:
            try:
                answer = await ctx.elicit(
                    message=(
                        f"Graph has {len(G.nodes)} nodes. Betweenness centrality is O(VE) "
                        f"and may take several minutes. Use subgraph to narrow the area first, "
                        f"or proceed anyway?"
                    ),
                    response_type=bool,
                )
                if answer.action != "accept" or not answer.data:
                    return {
                        "status": "cancelled",
                        "reason": "O(VE) computation skipped. Call subgraph to extract a smaller area first.",
                    }
            except Exception:
                pass

        UG = G.to_undirected()
        centrality = await asyncio.to_thread(
            nx.betweenness_centrality, UG, weight=weight, normalized=normalized
        )
        top = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:10]
        results = []
        for node_id, score in top:
            data = G.nodes.get(node_id, {})
            results.append(
                {
                    "node_id": int(node_id),
                    "centrality": round(float(score), 6),
                    "lat": float(data.get("y", 0)),
                    "lng": float(data.get("x", 0)),
                    "street_count": int(data.get("street_count", 0)),
                }
            )
        return {"top_nodes": results, "weight": weight, "normalized": normalized}

    @mcp.tool
    def articulation_points(graph_name: str = None) -> dict:
        """
        Find articulation points: nodes whose removal disconnects the graph.

        Returns count and a sample of up to 10 with coordinates.
        Uses the undirected projection.
        """
        G = store.get(graph_name)
        UG = G.to_undirected()
        aps = list(nx.articulation_points(UG))
        sample = [
            {
                "node_id": int(n),
                "lat": float(G.nodes[n].get("y", 0)),
                "lng": float(G.nodes[n].get("x", 0)),
            }
            for n in aps[:10]
        ]
        return {"articulation_point_count": len(aps), "sample": sample}

    @mcp.tool
    def missing_links(graph_name: str = None, top_n: int = 10) -> dict:
        """
        Find node pairs that are Euclidean-close but network-far -- missing link candidates.

        Flags pairs where (Euclidean distance / network distance) < 0.3.
        Caps at 500 nodes; call subgraph first to focus on a specific area.
        top_n: number of top candidates to return (default 10).
        """
        import math

        import numpy as np
        from scipy.spatial import KDTree

        G = store.get(graph_name)
        n_total = len(G.nodes)

        G_proj = ox.project_graph(G)
        node_ids = list(G_proj.nodes())

        if len(node_ids) > 500:
            rng = np.random.default_rng(42)
            node_ids = rng.choice(node_ids, size=500, replace=False).tolist()

        coords = np.array(
            [[G_proj.nodes[n]["x"], G_proj.nodes[n]["y"]] for n in node_ids]
        )
        tree = KDTree(coords)
        _, indices = tree.query(coords, k=6)

        candidates = []
        seen = set()
        for i, nbr_idxs in enumerate(indices):
            n1 = node_ids[i]
            for j_idx in nbr_idxs[1:]:
                n2 = node_ids[j_idx]
                pair = (min(int(n1), int(n2)), max(int(n1), int(n2)))
                if pair in seen:
                    continue
                seen.add(pair)
                x1, y1 = G_proj.nodes[n1]["x"], G_proj.nodes[n1]["y"]
                x2, y2 = G_proj.nodes[n2]["x"], G_proj.nodes[n2]["y"]
                eucl_d = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                if eucl_d == 0:
                    continue
                try:
                    net_d = nx.shortest_path_length(G, n1, n2, weight="length")
                except nx.NetworkXNoPath:
                    continue
                if net_d > 0:
                    ratio = eucl_d / net_d
                    if ratio < 0.3:
                        candidates.append(
                            {
                                "node_a": int(n1),
                                "node_b": int(n2),
                                "euclidean_m": round(float(eucl_d), 1),
                                "network_m": round(float(net_d), 1),
                                "ratio": round(ratio, 4),
                                "lat_a": float(G.nodes[n1].get("y", 0)),
                                "lng_a": float(G.nodes[n1].get("x", 0)),
                                "lat_b": float(G.nodes[n2].get("y", 0)),
                                "lng_b": float(G.nodes[n2].get("x", 0)),
                            }
                        )

        candidates.sort(key=lambda x: x["ratio"])
        return {
            "missing_link_candidates": candidates[:top_n],
            "total_candidates_found": len(candidates),
            "nodes_analyzed": len(node_ids),
            "total_nodes": n_total,
            "note": "Ratio = Euclidean distance / network distance. Lower values are stronger candidates.",
        }

    @mcp.tool
    async def network_resilience(graph_name: str = None, ctx: Context = None) -> dict:
        """
        Simulate targeted removal of the top 5 betweenness-centrality nodes
        one at a time and report how the largest connected component changes.

        O(VE) for betweenness centrality. Use on subgraphs for large networks.
        """
        G = store.get(graph_name)

        if ctx and len(G.nodes) > _ELICIT_THRESHOLD:
            try:
                answer = await ctx.elicit(
                    message=(
                        f"Graph has {len(G.nodes)} nodes. Network resilience requires O(VE) "
                        f"betweenness computation and may take several minutes. Proceed?"
                    ),
                    response_type=bool,
                )
                if answer.action != "accept" or not answer.data:
                    return {
                        "status": "cancelled",
                        "reason": "O(VE) computation skipped. Call subgraph to extract a smaller area first.",
                    }
            except Exception:
                pass

        UG = G.to_undirected()

        centrality = await asyncio.to_thread(
            nx.betweenness_centrality, UG, weight="length", normalized=True
        )
        top5 = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:5]

        components = list(nx.connected_components(UG))
        initial_size = len(max(components, key=len)) if components else 0

        G_sim = UG.copy()
        sequence = []
        for node_id, score in top5:
            if node_id in G_sim:
                G_sim.remove_node(node_id)
            comps = list(nx.connected_components(G_sim))
            largest = len(max(comps, key=len)) if comps else 0
            pct = round(largest / initial_size * 100, 1) if initial_size > 0 else 0.0
            sequence.append(
                {
                    "removed_node": int(node_id),
                    "centrality": round(float(score), 6),
                    "largest_component_size": largest,
                    "pct_remaining": pct,
                }
            )

        return {
            "initial_largest_component": initial_size,
            "total_nodes": len(G.nodes),
            "sequence": sequence,
        }

    @mcp.tool
    def circuity_distribution(graph_name: str = None) -> dict:
        """
        Per-edge ratio of network edge length to straight-line distance between endpoints.

        Extends circuity_avg from the stats resource with the full distribution.
        Values near 1.0 are straight edges; higher values indicate detours.
        Returns histogram, p90, max, and the 10 most circuitous edges.
        """
        import math

        import numpy as np

        G = store.get(graph_name)
        ratios = []
        edge_records = []

        for u, v, data in G.edges(data=True):
            length = data.get("length")
            if not length or length == 0:
                continue
            x1 = G.nodes[u].get("x")
            y1 = G.nodes[u].get("y")
            x2 = G.nodes[v].get("x")
            y2 = G.nodes[v].get("y")
            if None in (x1, y1, x2, y2):
                continue
            lat_mid = (y1 + y2) / 2
            dx = (x2 - x1) * 111320 * math.cos(math.radians(lat_mid))
            dy = (y2 - y1) * 111320
            straight_m = math.sqrt(dx**2 + dy**2)
            if straight_m < 1.0:
                continue
            ratio = length / straight_m
            ratios.append(ratio)
            edge_records.append(
                {
                    "u": int(u),
                    "v": int(v),
                    "ratio": ratio,
                    "length_m": round(float(length), 1),
                    "name": data.get("name"),
                    "highway": data.get("highway"),
                }
            )

        if not ratios:
            return {"error": "No edges with valid geometry found"}

        arr = np.array(ratios)
        hist, bin_edges = np.histogram(arr, bins=10)
        top10 = sorted(edge_records, key=lambda x: x["ratio"], reverse=True)[:10]
        for item in top10:
            item["ratio"] = round(item["ratio"], 4)

        return {
            "mean": round(float(arr.mean()), 4),
            "median": round(float(np.median(arr)), 4),
            "p90": round(float(np.percentile(arr, 90)), 4),
            "max": round(float(arr.max()), 4),
            "histogram": {
                f"{bin_edges[i]:.2f}-{bin_edges[i + 1]:.2f}": int(hist[i])
                for i in range(len(hist))
            },
            "most_circuitous": top10,
        }
