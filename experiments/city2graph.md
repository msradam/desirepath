# city2graph

**Feasibility: high**

## What it does

city2graph converts GTFS transit feeds, Overture Maps building footprints, origin-destination matrices, and POI proximity data into NetworkX graphs. The output is a standard `nx.MultiDiGraph` or a heterogeneous graph compatible with PyTorch Geometric.

## Integration point

`c2g.from_gtfs(gtfs_path)` and `c2g.from_overture(overture_path)` both return NetworkX objects. `mount(G)` accepts any `nx.MultiDiGraph` unchanged. No glue code is needed for the basic case.

```python
import city2graph as c2g
from desirepath import mount

G = c2g.from_gtfs("gtfs.zip")
server = mount(G, name="transit")
server.run()
```

## New tool surface

- Transit isochrones: reachability by transit rather than driving, using the existing `isochrone` tool once the graph is loaded
- Multimodal routing: combine a transit graph with an OSMnx walk graph, then use `shortest_path` across both
- Building adjacency queries: Overture footprints as nodes, shared-wall relationships as edges

## Blocking issues

None for the NetworkX path. PyTorch Geometric is an optional city2graph dependency and is not required for desirepath's use case.

## License

MIT.

## Effort to integrate

Low. city2graph is a loader, not an analytical layer. The integration is:

1. `uv add city2graph` as a new optional extra `[transit]`
2. Add `load_graph_from_gtfs(path, name)` and `load_graph_from_overture(path, name)` to `tools/graph.py`
3. Both call the city2graph loader, then `store.add(name, G, source="city2graph", ...)`

No changes to existing tools, resources, or the CLI are required.

## Verdict

Promoted. `load_graph_from_gtfs` is now in `src/desirepath/tools/transit.py` and registered automatically when city2graph is installed. Install with `uv add "desirepath[transit]"`.
