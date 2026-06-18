# aequilibrae

**Feasibility: medium**

## What it adds

aequilibrae is the only production-quality Python library for traffic assignment: it computes the equilibrium flow on each road segment given an origin-destination demand matrix and a congestion function. The result is a link-flow vector -- edge-level traffic volumes under realistic demand -- which is something no static network metric can produce.

It also handles GTFS import, optimal-strategies transit assignment, and OMX demand matrix support.

## The question it answers

"Given that 10,000 trips per hour originate from Zone A and are destined for Zone B, what is the equilibrium vehicle count on each road segment?" This is the core calculation of transport planning and cannot be approximated by betweenness centrality or random walk.

## Integration point

aequilibrae stores its network in SQLite/SpatiaLite, not in NetworkX. The integration requires a round-trip: extract node/edge GeoDataFrames from the OSMnx graph, build an aequilibrae `Project`, run assignment, extract link flows, write them back as edge attributes.

```python
import aequilibrae as aeq
import osmnx as ox

# Export OSMnx graph to aequilibrae project
nodes_gdf, edges_gdf = ox.graph_to_gdfs(G)

project = aeq.Project()
project.new("piedmont.sqlite")
project.network.create_from_osm(place_name="Piedmont, California, USA")

# Build graph and assignment
graph = project.network.build_graph()
graph.set_graph("free_flow_time")
graph.set_skimming(["free_flow_time", "distance"])

assignment = aeq.TrafficAssignment()
# ... set OD matrix, volume-delay function ...
assignment.execute()

# Extract link flows back to the OSMnx edge index
```

The OSMnx round-trip is workable but not a one-liner. The edge ID mapping between OSMnx (u, v, key) and aequilibrae link IDs requires care.

## New tool surface

`traffic_assignment(od_matrix, graph_name)` -- run user-equilibrium assignment given an OD matrix (as a dict or path to an OMX file); return edge-level flow volumes as a new graph attribute; expose via `graph://{name}/edge-attributes/flow`.

## Blocking issues

1. **OD matrix is user-supplied.** aequilibrae cannot produce travel demand from OSM data alone. The user must supply an origin-destination matrix, which is typically a product of a separate four-step travel demand model. This limits the tool to users who already have OD data.
2. **SQLite round-trip.** The network format conversion is not trivial and may lose OSMnx-specific attributes. The edge ID mapping needs careful handling.
3. **License.** aequilibrae uses a custom "extremely permissive" license. Verify compatibility before redistribution.

## Effort to integrate

High. The conversion and OD matrix interface alone are significant. The payoff is unique capability that nothing else in the Python ecosystem provides at this quality level.

## Verdict

experiments/ indefinitely until a clean OSMnx-to-aequilibrae conversion path is established. The right approach may be to use aequilibrae's built-in OSM downloader rather than converting an existing OSMnx graph, which would bypass the round-trip problem but break the desirepath contract.
