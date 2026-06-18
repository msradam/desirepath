# urbanaccess

**Feasibility: medium-low**

## What it adds

urbanaccess combines OSM pedestrian networks with GTFS transit data into a single pandana-compatible multimodal graph. It answers "how far can you get by walking and transit combined" -- a question that nothing else in the current desirepath stack answers.

## Why it is interesting

The existing `accessibility_to_pois` tool uses pandana over the drive or walk network only. urbanaccess would extend that to transit-augmented networks, enabling transit-weighted isochrones and accessibility scores that reflect real multimodal travel.

## Integration point

urbanaccess requires a GTFS file supplied by the user. It is not self-contained like OSMnx.

```python
import urbanaccess as ua

loaded_feeds = ua.gtfs.load.gtfsfeed_to_df(gtfsfeed_path="gtfs.zip", ...)
ua.gtfs.network.create_transit_net(gtfsfeeds_df=loaded_feeds, ...)
ua.osm.load.ua_network_from_bbox(...)
ua.network.integrate_network(...)
```

## Blocking issues

1. **User data dependency.** GTFS files vary widely in quality, schema version, and coverage. The integration cannot be self-contained.
2. **Maintenance.** urbanaccess last released in 2021. The library is not actively maintained and may have compatibility issues with current pandas and geopandas versions.
3. **Superseded by city2graph.** city2graph provides a cleaner GTFS parsing path with active maintenance and a simpler API. The urbanaccess use case is covered by the city2graph transit path.

## Verdict

Deprioritize in favor of the city2graph transit path. Revisit only if city2graph's GTFS support proves insufficient.
