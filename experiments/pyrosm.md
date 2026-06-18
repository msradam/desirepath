# pyrosm

**Feasibility: high**

## What it adds

pyrosm parses pre-downloaded OSM `.osm.pbf` files into OSMnx-compatible `nx.MultiDiGraph` objects. It fills the one gap that `load_graph(source='place')` cannot: loading large metropolitan networks (NYC, London, Paris) without querying the Overpass API.

Overpass imposes rate limits and has a ~50MB response cap. A pre-downloaded PBF file for Greater London is ~1.5GB and can be loaded in under a minute with pyrosm. There is no practical way to load this via Overpass.

## Integration point

`pyrosm.OSM(filepath).to_graph(nodes, edges, graph_type="networkx", osmnx_compatible=True)` returns a graph with `x`, `y`, `osmid`, `length`, `highway`, and `geometry` attributes -- the same contract as an OSMnx-produced graph. `mount(G)` works unchanged.

```python
import pyrosm
import osmnx as ox
from desirepath import mount

osm = pyrosm.OSM("london.osm.pbf")
nodes, edges = osm.get_network(network_type="driving", nodes=True)
G = osm.to_graph(nodes, edges, graph_type="networkx", osmnx_compatible=True)
G = ox.add_edge_speeds(G)
G = ox.add_edge_travel_times(G)

server = mount(G, name="london_drive")
server.run()
```

PBF files are available from [Geofabrik](https://download.geofabrik.de/) for free.

## Integration path in load_graph

The cleanest integration is `load_graph(source='pbf', path='london.osm.pbf', name='london')`. This adds one branch to the existing `load_graph` discriminated union and requires pyrosm as a `[loaders]` optional extra:

```python
elif source == "pbf":
    try:
        import pyrosm
    except ImportError:
        raise RuntimeError(
            "pyrosm is required for source='pbf'. "
            "Install with: uv add 'desirepath[loaders]'"
        )
    osm = pyrosm.OSM(path)
    nodes_gdf, edges_gdf = osm.get_network(network_type=network_type, nodes=True)
    G = osm.to_graph(nodes_gdf, edges_gdf, graph_type="networkx", osmnx_compatible=True)
    description = path
```

No new tool is required. No new test fixture is required (PBF files are not committed to source control; a small PBF can be downloaded in CI if needed).

## Blocking issues

None technical. pyrosm is MIT-licensed and actively maintained (v0.9.0, June 2026). The only prerequisite is that the user downloads a PBF file before loading -- pyrosm does not download data itself.

## Optional dependency

Add to `pyproject.toml`:
```toml
[project.optional-dependencies]
loaders = ["pyrosm>=0.9"]
all     = ["pandana>=0.7", "libpysal>=4.14.1", "esda>=2.9.0", "spaghetti>=1.7.6", "pyrosm>=0.9"]
```

And update `doctor` to check for pyrosm with `uv add "desirepath[loaders]"` install hint.

## Verdict

Promote immediately. One afternoon of work: add `source='pbf'` branch in `load_graph`, add `[loaders]` extra to `pyproject.toml`, update `doctor`.
