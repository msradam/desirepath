# Desirepath

Urban street network analysis as an MCP server and CLI.

An LLM or CLI tool can ask: route between two points, find missing links, measure circuity, compute isochrones, compare cities, render interactive maps. Desirepath is a typed MCP interface over [OSMnx](https://github.com/gboeing/osmnx) and [Momepy](https://github.com/martinfleis/momepy), with 20 tools and 9 resources.

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/yourname/desirepath
cd desirepath
uv sync
```

## Quickstart

```bash
# Check environment
uv run desirepath doctor

# Network stats for any place
uv run desirepath stats "Piedmont, California, USA"

# Compare two cities
uv run desirepath compare "Amsterdam, Netherlands" "Houston, Texas, USA"

# Start the MCP server
uv run desirepath serve --place "Amsterdam, Netherlands" --name amsterdam
```

Sample `stats` output:
```json
{
  "n": 388,
  "m": 916,
  "edge_length_avg": 106.4,
  "streets_per_node_avg": 2.887,
  "circuity_avg": 1.065
}
```

## Connect to Claude

**Claude Code**: add to `.mcp.json` at the project root:
```json
{
  "mcpServers": {
    "desirepath": {
      "command": "uv",
      "args": ["run", "desirepath", "serve"],
      "cwd": "/path/to/desirepath",
      "type": "stdio"
    }
  }
}
```

**Claude Desktop**: add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "desirepath": {
      "command": "uv",
      "args": [
        "run", "--project", "/path/to/desirepath",
        "desirepath", "serve",
        "--graphml", "/path/to/my_city.graphml",
        "--name", "my_city"
      ]
    }
  }
}
```

Claude Desktop's sandbox blocks Overpass at runtime. Download a graph first with `desirepath serve --place ...`, call `save_graph` to write it to disk, then use `--graphml` on subsequent starts.

**MCPJam Inspector**: renders `map_graph`, `map_route`, and `map_isochrone` as inline Leaflet maps:
```bash
npx @mcpjam/inspector@latest --config mcpjam.json --server desirepath
```

## Tools

All routing coordinates are in **lng, lat order**.

### Graph

| Tool | What it does |
|------|-------------|
| `load_graph` | Load from place name, lat/lng radius, GraphML file, or .osm.pbf |
| `save_graph` | Write graph to GraphML for fast reload |
| `set_active_graph` | Switch which graph other tools operate on |
| `drop_graph` | Remove a graph from memory |
| `subgraph` | Extract a bbox or radius subgraph from a loaded graph |

### Routing

| Tool | What it does |
|------|-------------|
| `find_nearest` | Snap a coordinate to the nearest node or edge |
| `route` | Shortest path by distance or travel time; k>1 returns alternatives |
| `isochrone` | Reachable area within a travel-time budget |

### Stats

| Tool | What it does |
|------|-------------|
| `betweenness_centrality` | Top 10 nodes by flow centrality (O(VE); call subgraph first on large networks) |
| `articulation_points` | Nodes whose removal disconnects the graph |
| `missing_links` | Euclidean-close node pairs with high network detour ratios |
| `network_resilience` | Component size after sequential removal of top-centrality nodes |
| `circuity_distribution` | Per-edge circuity histogram; top 10 most circuitous segments |

Basic stats, orientation entropy, street hierarchy, and degree distribution are resources, not tools. Read them at `graph://{name}/stats` and `graph://{name}/street-hierarchy` without a tool call.

### Morphology

`morphology(metrics=[...])` computes any combination of:

- `linearity`: edge straightness (0 to 1)
- `sinuosity`: inverse of linearity; top 10 most winding streets
- `connectivity`: meshedness coefficient; near 1 = grid, near 0 = tree
- `clustering`: squares clustering coefficient (how grid-like at the local scale)
- `intersection_types`: dead-end / 3-way / 4-way-plus fractions

### Features

`get_features(source, tags)` fetches OSM features from Overpass by point, bbox, or place name. Times out after 25 seconds; use specific tag values.

### Enrichment

`enrich_graph(speeds, travel_times, bearings, grades)` adds computed attributes to graph edges in a single call.

### Map

| Tool | What it does |
|------|-------------|
| `map_graph` | Interactive Leaflet map of the network |
| `map_route` | Network map with a route overlay |
| `map_isochrone` | Network map with a reachable-area overlay |

Renders inline in MCPJam Inspector. Saves HTML to `~/Downloads/` on other hosts.

### Compare

`compare_graphs` produces a side-by-side JSON summary of two loaded graphs.

### Optional tools

| Extra | Install | Tools added |
|-------|---------|-------------|
| `[loaders]` | `uv add "desirepath[loaders]"` | `load_graph(source='pbf')` for large .osm.pbf files |
| `[access]` | `uv add "desirepath[access]"` | `accessibility_to_pois`: pandana-based POI distance for every node |
| `[spatial]` | `uv add "desirepath[spatial]"` | `spatial_autocorrelation` (Moran's I), `network_constrained_clustering` |
| `[transit]` | `uv add "desirepath[transit]"` | `load_graph_from_gtfs`: GTFS feed to transit stop graph |
| `[all]` | `uv add "desirepath[all]"` | all of the above |

Optional tools register automatically when their dependency is installed. Run `uv run desirepath doctor` to see what is present.

## Resources

Resources are read directly by the agent without a tool call.

| URI | Content |
|-----|---------|
| `graph://graphs` | All loaded graphs with counts |
| `graph://metadata` | Active graph: counts, bbox, CRS, attributes |
| `graph://{name}/metadata` | Same for a named graph |
| `graph://{name}/stats` | Basic stats, orientation entropy, dead-end count |
| `graph://{name}/street-hierarchy` | Edge counts and lengths by highway tag |
| `graph://{name}/nodes/{node_id}` | Single node attributes |
| `graph://{name}/edges/{u}/{v}/{key}` | Single edge attributes (geometry excluded) |
| `graph://{name}/edge-attributes` | List of edge attribute names |
| `graph://{name}/edge-attributes/{attr}` | Unique values for an attribute |

## Programmatic use

```python
import osmnx as ox
from desirepath import mount

G = ox.graph_from_place("Piedmont, California, USA", network_type="drive")
G = ox.add_edge_speeds(G)
G = ox.add_edge_travel_times(G)

server = mount(G, name="piedmont")
server.run()
```

`mount(G)` accepts any `nx.MultiDiGraph` and returns a FastMCP server. Use `server.run_http_async()` for HTTP transport.

## Attribution

Street network data is from [OpenStreetMap](https://www.openstreetmap.org/copyright) © OpenStreetMap contributors, available under the [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/). Any derivative use of this data must include this attribution and comply with the ODbL.

Graph construction uses [OSMnx](https://github.com/gboeing/osmnx) by Geoff Boeing, available under the MIT license. If you use OSMnx in research, cite: Boeing, G. (2017). OSMnx: New methods for acquiring, constructing, analyzing, and visualizing complex street networks. *Computers, Environment and Urban Systems*, 65, 126-139. https://doi.org/10.1016/j.compenvurbsys.2017.05.004

- Urban morphology: [Momepy](https://github.com/martinfleis/momepy) by Martin Fleischmann
- Spatial statistics: [PySAL](https://pysal.org)
