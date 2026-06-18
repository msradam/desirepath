# cityseer

**Feasibility: medium**

## What it adds

cityseer provides pedestrian-scale moving-window centrality: harmonic closeness and segment betweenness computed within a configurable walking threshold, with direction-of-approach weighting and spatial impedance. It also computes land-use mixed-use scores by combining POI density with network centrality.

This is different from the `betweenness_centrality` tool in desirepath, which uses standard graph-theoretic centrality on the full network. cityseer computes local, threshold-bounded measures that reflect how walkable a location feels, not just how central it is in the graph.

## Integration point

`cityseer.tools.graphs.nx_to_cityseer_graph(G)` converts directly from a NetworkX `MultiDiGraph`. The conversion is one call.

```python
from cityseer.tools import graphs, metrics

G_cs = graphs.nx_to_cityseer_graph(G_osm)
nodes_gdf, edges_gdf = graphs.network_structure_from_nx(G_cs, crs=4326)
nodes_gdf, edges_gdf = metrics.segment_centrality(
    nodes_gdf, edges_gdf, distances=[400, 800]
)
```

## New tool surface

- `pedestrian_centrality(lat, lng, radius_m)`: harmonic closeness and segment betweenness within a walking threshold at each node
- `mixed_use_score(lat, lng, radius_m, poi_gdf)`: land-use diversity score combining OSM POI data with local centrality

## Blocking issues

**AGPLv3 license.** Any networked service built on desirepath that incorporates cityseer must open source its code under AGPL. This is a hard blocker for any commercial or proprietary use case. Resolve the license question before promoting.

No technical blockers. The conversion is straightforward and the Rust-backed core scales well to city-sized networks.

## Effort to integrate

Medium. The conversion is one call, but cityseer's output data structures (sparse arrays, custom GeoDataFrames) need wrapping into the flat dicts that desirepath tools return.

## Verdict

Hold pending license decision. If the project commits to AGPL or restricts cityseer to a clearly-labeled optional extra with an AGPL notice, promote in the next iteration.
