import networkx as nx
import osmnx as ox
from fastmcp import FastMCP

from desirepath.graph_store import GraphStore


def register(mcp: FastMCP, store: GraphStore) -> None:
    @mcp.tool
    def find_nearest(
        entity: str,
        lng: float,
        lat: float,
        graph_name: str | None = None,
    ) -> dict:
        """
        Find the nearest node or edge to a coordinate (lng, lat order).

        entity: 'node' returns the nearest node id and attributes.
                'edge' returns (u, v, key) and edge attributes (geometry excluded).
        """
        G = store.get(graph_name)
        if entity == "node":
            node_id = ox.nearest_nodes(G, lng, lat)
            return {"node_id": int(node_id), "data": dict(G.nodes[node_id])}
        elif entity == "edge":
            u, v, key = ox.nearest_edges(G, lng, lat)
            data = dict(G[u][v][key])
            data.pop("geometry", None)
            return {"u": int(u), "v": int(v), "key": int(key), "data": data}
        else:
            raise ValueError(f"entity must be 'node' or 'edge', got '{entity}'")

    @mcp.tool
    def route(
        orig_lng: float,
        orig_lat: float,
        dest_lng: float,
        dest_lat: float,
        weight: str = "length",
        k: int = 1,
        graph_name: str | None = None,
    ) -> dict | list:
        """
        Compute the shortest route between two points. Coordinates in lng, lat order.

        weight: 'length' minimizes meters; 'travel_time' minimizes seconds
          (requires enrich_graph with travel_times=True first).
        k: 1 returns a single path dict; k > 1 returns a list of k alternatives.

        Each path dict has 'path' (node id sequence), 'node_count', 'length_m', 'travel_time_s'.
        """
        G = store.get(graph_name)
        orig = ox.nearest_nodes(G, orig_lng, orig_lat)
        dest = ox.nearest_nodes(G, dest_lng, dest_lat)

        def _path_dict(path):
            length = sum(
                G[u][v][0].get("length", 0) for u, v in zip(path[:-1], path[1:])
            )
            travel_time = sum(
                G[u][v][0].get("travel_time", 0) for u, v in zip(path[:-1], path[1:])
            )
            return {
                "path": [int(n) for n in path],
                "node_count": len(path),
                "length_m": round(length, 1),
                "travel_time_s": round(travel_time, 1) if travel_time else None,
            }

        if k == 1:
            path = ox.shortest_path(G, orig, dest, weight=weight)
            if path is None:
                return {
                    "path": None,
                    "node_count": 0,
                    "length_m": None,
                    "travel_time_s": None,
                }
            return _path_dict(path)
        else:
            paths = list(ox.k_shortest_paths(G, orig, dest, k, weight=weight))
            return [_path_dict(p) for p in paths]

    @mcp.tool
    def isochrone(
        lat: float,
        lng: float,
        trip_time_s: float,
        graph_name: str | None = None,
    ) -> dict:
        """
        Compute reachable area from a point within a given travel time.

        lat, lng: center coordinate (lat first for this tool).
        trip_time_s: maximum travel time in seconds.
        Requires travel_time attribute on edges. Call enrich_graph with travel_times=True first,
        otherwise this returns an error.

        Returns reachable node count, convex hull as GeoJSON polygon, and reachable node IDs.
        """
        from shapely.geometry import MultiPoint, mapping

        G = store.get(graph_name)
        sample = next(iter(G.edges(data=True)), None)
        if sample is None or "travel_time" not in sample[2]:
            raise ValueError(
                "Graph edges are missing 'travel_time'. "
                "Call enrich_graph with travel_times=True before running isochrone."
            )
        center = ox.nearest_nodes(G, lng, lat)
        reachable = nx.single_source_dijkstra_path_length(
            G, center, cutoff=trip_time_s, weight="travel_time"
        )
        node_ids = [int(n) for n in reachable]
        coords = [
            (G.nodes[n]["x"], G.nodes[n]["y"])
            for n in reachable
            if "x" in G.nodes[n] and "y" in G.nodes[n]
        ]
        hull = None
        if len(coords) >= 3:
            hull = mapping(MultiPoint(coords).convex_hull)
        return {
            "center_node": int(center),
            "trip_time_s": trip_time_s,
            "reachable_node_count": len(node_ids),
            "reachable_node_ids": node_ids,
            "convex_hull": hull,
        }
