import osmnx as ox
from fastmcp import FastMCP

from desirepath.graph_store import GraphStore


def register(mcp: FastMCP, store: GraphStore) -> None:
    @mcp.tool
    def accessibility_to_pois(
        tags: dict,
        max_distance_m: float = 1000.0,
        num_pois: int = 5,
        graph_name: str = None,
    ) -> dict:
        """
        Compute network distance from every node to the nearest N POIs matching
        the given OSM tags. Uses pandana contraction hierarchies; fast even on
        large graphs.

        tags: OSM tag dict, e.g. {"amenity": "school"} or {"amenity": ["school", "hospital"]}
        max_distance_m: search cutoff in meters
        num_pois: how many nearest POIs to find per node (1 to 5)

        Returns mean, median, and p90 network distance across all nodes,
        plus POI count and count of nodes with no POI in range.
        Coordinates in lng, lat order.

        Requires the 'access' optional extra: uv add "desirepath[access]"
        """
        try:
            import pandana
        except ImportError:
            raise RuntimeError(
                "pandana is required for accessibility tools. "
                'Install with: uv add "desirepath[access]"'
            )
        import numpy as np

        G = store.get(graph_name)
        nodes, edges = ox.graph_to_gdfs(G)

        edges_reset = edges.reset_index()
        net = pandana.Network(
            nodes["x"],
            nodes["y"],
            edges_reset["u"],
            edges_reset["v"],
            edges_reset[["length"]],
            twoway=False,
        )

        bbox_north = float(nodes["y"].max())
        bbox_south = float(nodes["y"].min())
        bbox_east = float(nodes["x"].max())
        bbox_west = float(nodes["x"].min())

        try:
            poi_gdf = ox.features_from_bbox(
                bbox=(bbox_north, bbox_south, bbox_east, bbox_west), tags=tags
            )
        except Exception as e:
            return {"error": f"Overpass query failed: {e}"}

        if poi_gdf.empty:
            return {"error": f"No POIs found for tags {tags} in graph extent"}

        poi_gdf = poi_gdf[poi_gdf.geometry.notna()].copy()
        if poi_gdf.empty:
            return {"error": f"No POIs with valid geometry found for tags {tags}"}

        poi_gdf["x"] = poi_gdf.geometry.representative_point().x
        poi_gdf["y"] = poi_gdf.geometry.representative_point().y

        num_pois = max(1, min(num_pois, 5))
        net.set_pois(
            category="query",
            maxdist=max_distance_m,
            maxitems=num_pois,
            x_col=poi_gdf["x"],
            y_col=poi_gdf["y"],
        )
        result = net.nearest_pois(max_distance_m, "query", num_pois=num_pois)

        col = result[1]
        reachable = col[col < max_distance_m]
        unreachable = int((col >= max_distance_m).sum())

        return {
            "poi_count": len(poi_gdf),
            "tags": tags,
            "max_distance_m": max_distance_m,
            "nodes_with_poi_in_range": int(len(reachable)),
            "nodes_without_poi_in_range": unreachable,
            "distance_to_nearest_m": {
                "mean": round(float(reachable.mean()), 1) if len(reachable) else None,
                "median": round(float(reachable.median()), 1)
                if len(reachable)
                else None,
                "p90": round(float(np.percentile(reachable, 90)), 1)
                if len(reachable)
                else None,
            },
        }
