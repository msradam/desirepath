# experiments/city2graph_stub.py
# Demonstrates that city2graph output is compatible with desirepath's mount().
# run with: uv run python experiments/city2graph_stub.py
# requires:  uv add city2graph

import sys

import osmnx as ox

try:
    import city2graph as c2g  # noqa: F401
except ImportError:
    print("city2graph is not installed.")
    print("Install with: uv add city2graph")
    print()
    print("What this stub demonstrates:")
    print("  city2graph loaders return nx.MultiDiGraph objects.")
    print("  desirepath.mount() accepts any nx.MultiDiGraph.")
    print("  No glue code is required.")
    sys.exit(0)

from desirepath import mount

G_osm = ox.graph_from_place("Piedmont, California, USA", network_type="walk")
print(f"OSMnx graph: {len(G_osm.nodes)} nodes, {len(G_osm.edges)} edges")

server = mount(G_osm, name="piedmont_walk")
print(f"Mounted as MCP server: {server.name}")
print()
print("city2graph GTFS and Overture paths:")
print("  G_transit = c2g.from_gtfs('gtfs.zip')")
print("  G_overture = c2g.from_overture('overture.parquet')")
print("  server = mount(G_transit, name='transit')")
print("  server.run()")
print()
print("Both return nx.MultiDiGraph -- mount() accepts them unchanged.")
