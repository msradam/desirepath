import osmnx as ox
from fastmcp import FastMCP

from desirepath.graph_store import GraphStore


def register(mcp: FastMCP, store: GraphStore) -> None:
    def _update(G, graph_name):
        entry = store.get_entry(graph_name)
        entry.graph = G

    @mcp.tool
    def enrich_graph(
        speeds: bool = True,
        travel_times: bool = True,
        bearings: bool = False,
        grades: bool = False,
        graph_name: str | None = None,
    ) -> dict:
        """
        Enrich graph edges with computed attributes.

        speeds: impute speed_kph from OSM maxspeed tags and heuristics.
        travel_times: compute travel_time (seconds) from length and speed_kph.
          Requires speeds=True or speeds already present on edges.
        bearings: add compass bearing (degrees) to each edge.
        grades: add elevation grade (rise/run). Requires nodes to have 'elevation' attribute.

        Mutates the active graph in place. Returns count of edges updated per attribute.
        """
        G = store.get(graph_name)
        updated = {"speeds": 0, "travel_times": 0, "bearings": 0, "grades": 0}

        if speeds:
            G = ox.add_edge_speeds(G)
            updated["speeds"] = sum(
                1 for _, _, d in G.edges(data=True) if "speed_kph" in d
            )

        if travel_times:
            G = ox.add_edge_travel_times(G)
            updated["travel_times"] = sum(
                1 for _, _, d in G.edges(data=True) if "travel_time" in d
            )

        if bearings:
            G = ox.add_edge_bearings(G)
            updated["bearings"] = sum(
                1 for _, _, d in G.edges(data=True) if "bearing" in d
            )

        if grades:
            G = ox.add_edge_grades(G)
            updated["grades"] = sum(1 for _, _, d in G.edges(data=True) if "grade" in d)

        _update(G, graph_name)
        return updated
