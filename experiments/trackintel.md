# trackintel

**Feasibility: medium**

## What it adds

trackintel is a GPS mobility pipeline: raw coordinates to positionfixes, staypoints, locations, trips, and tours. It uses OSMnx for map-matching in its contextual enrichment module.

The question it answers: "Given GPS traces from people moving through this network, what are the most common trip paths, how long do people linger at which nodes, and how does observed mobility compare to shortest-path predictions?" This is empirical mobility analysis grounded in real movement data rather than network topology.

## Integration point

trackintel works with GeoDataFrames and connects to OSMnx for network-based enrichment. The GPS data flows through the pipeline and can be joined to the OSMnx graph by snapping trip segments to edges.

```python
import trackintel as ti
import geopandas as gpd

# Load GPS positionfixes
pf = ti.read_positionfixes_csv("gps_data.csv", index_col="id", crs="epsg:4326")

# Detect staypoints from the GPS stream
pf, sp = pf.as_positionfixes.generate_staypoints(
    method="sliding", dist_threshold=25, time_threshold=5
)

# Generate trips between staypoints
sp, tpls, trips = sp.as_staypoints.generate_trips(gap_threshold=15)

# Map-match triplegs to the OSMnx road network
# trackintel uses leuvenmapmatching or similar internally
tpls_enriched = tpls.as_triplegs.add_context(geo_col="geom", G=G_osm)
```

## New tool surface

`map_match_trips(gps_geojson, graph_name)` -- snap a GeoJSON FeatureCollection of GPS traces to the loaded graph; return matched edge sequences with timestamps and inferred travel modes.

## Blocking issues

1. **User-supplied GPS data.** The tool only produces value when the user has GPS movement data. This limits the audience to mobility researchers and transport planners with data collection infrastructure.
2. **Map-matching quality.** Map-matching quality degrades in dense urban areas, on parallel roads, and near graph boundaries. The results require validation for any quantitative analysis.
3. **Privacy.** GPS trip data is individually identifying. Any deployment handling real user data must address consent, aggregation, and retention.

## License

MIT. No license blocker.

## Effort to integrate

Medium. trackintel's pipeline is well-structured. The integration complexity is in the GPS data ingestion format and the output summarization (edge-level aggregation of matched trips). A working prototype is one week.

## Verdict

experiments/ until a clear GPS data intake path is defined. The tool is most useful paired with city2graph (which can provide GTFS transit context for mode inference). If the project adds a data-ingest pattern for user-supplied CSV/GeoJSON, promote trackintel alongside it.
