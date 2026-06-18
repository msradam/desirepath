import osmnx as ox
from fastmcp import FastMCP

from desirepath.graph_store import GraphStore


def register(mcp: FastMCP, store: GraphStore) -> None:
    @mcp.tool
    def spatial_autocorrelation(
        attribute: str,
        graph_name: str = None,
    ) -> dict:
        """
        Compute Moran's I spatial autocorrelation for a numeric edge attribute.

        Tells you whether high values cluster together (positive I), disperse
        (negative I), or show no spatial pattern (near 0).

        attribute: any numeric edge attribute present in the graph
                   (check graph://{name}/edge-attributes for available names)

        Returns Moran's I statistic, p-value, z-score, and interpretation.

        Requires the 'spatial' optional extra: uv add "desirepath[spatial]"
        """
        try:
            import libpysal.weights as lw
            from esda.moran import Moran
        except ImportError:
            raise RuntimeError(
                "libpysal and esda are required for spatial autocorrelation. "
                'Install with: uv add "desirepath[spatial]"'
            )

        G = store.get(graph_name)
        _, edges = ox.graph_to_gdfs(G)

        if attribute not in edges.columns:
            available = [c for c in edges.columns if edges[c].dtype.kind in ("f", "i")]
            return {
                "error": f"Attribute '{attribute}' not found. Available numeric: {available}"
            }

        edges_clean = edges[edges[attribute].notna()].copy()
        if len(edges_clean) < 10:
            return {
                "error": "Too few non-null values for meaningful autocorrelation (need >= 10)"
            }

        edges_reset = edges_clean.reset_index(drop=True)
        try:
            w = lw.Queen.from_dataframe(edges_reset, silence_warnings=True)
        except Exception as e:
            return {"error": f"Could not build spatial weights: {e}"}

        if w.n == 0 or len(w.islands) == w.n:
            return {"error": "No spatial neighbors found: edges may not share vertices"}

        w.transform = "r"
        mi = Moran(edges_reset[attribute].values, w)

        if mi.I > 0.3 and mi.p_sim < 0.05:
            interpretation = (
                "strong positive clustering: high values neighbor high values"
            )
        elif mi.I < -0.3 and mi.p_sim < 0.05:
            interpretation = "strong dispersion: high values neighbor low values"
        elif mi.p_sim >= 0.05:
            interpretation = "no significant spatial pattern"
        else:
            interpretation = "weak spatial pattern"

        return {
            "attribute": attribute,
            "moran_i": round(float(mi.I), 4),
            "p_value": round(float(mi.p_sim), 4),
            "z_score": round(float(mi.z_norm), 4),
            "interpretation": interpretation,
            "n": int(len(edges_clean)),
        }

    @mcp.tool
    def network_constrained_clustering(
        lat: float,
        lng: float,
        radius_m: float = 500.0,
        graph_name: str = None,
    ) -> dict:
        """
        Snap a point to the network and compute local network properties
        within a radius using spaghetti. Returns local edge density,
        total street length, and node/edge counts within radius.

        lat, lng: center coordinate (lat first for this tool).
        radius_m: radius in meters for the local subgraph.

        Requires the 'spatial' optional extra: uv add "desirepath[spatial]"
        """
        try:
            import spaghetti
            import warnings
        except ImportError:
            raise RuntimeError(
                "spaghetti is required for network-constrained analysis. "
                'Install with: uv add "desirepath[spatial]"'
            )

        G = store.get(graph_name)
        _, edges = ox.graph_to_gdfs(G)

        center_node = ox.nearest_nodes(G, lng, lat)
        try:
            subgraph = ox.truncate.truncate_graph_dist(G, center_node, dist=radius_m)
        except Exception:
            return {
                "error": "Could not extract subgraph; try a larger radius_m or check graph connectivity"
            }

        if len(subgraph.nodes) == 0:
            return {"error": "No nodes found within radius"}

        sub_nodes, sub_edges = ox.graph_to_gdfs(subgraph)

        try:
            sub_edges_reset = sub_edges.reset_index(drop=True)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                ntw = spaghetti.Network(in_data=sub_edges_reset)
            network_n_nodes = getattr(ntw, "network_n_nodes", None)
        except Exception:
            network_n_nodes = None

        import math

        area_km2 = math.pi * (radius_m / 1000) ** 2

        return {
            "center": {"lat": lat, "lng": lng},
            "radius_m": radius_m,
            "local_node_count": int(len(sub_nodes)),
            "local_edge_count": int(len(sub_edges)),
            "local_edge_density_per_km2": round(len(sub_edges) / area_km2, 2),
            "local_total_length_m": round(float(sub_edges["length"].sum()), 1),
            "spaghetti_network_nodes": int(network_n_nodes)
            if network_n_nodes is not None
            else None,
        }
