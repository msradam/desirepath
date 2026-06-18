import asyncio

import osmnx as ox
from fastmcp import FastMCP

from desirepath.graph_store import GraphStore

_DEFAULT_TIMEOUT = 25.0
_DEFAULT_LIMIT = 100


def _gdf_to_records(gdf, limit: int = _DEFAULT_LIMIT) -> dict:
    records = []
    for idx, row in gdf.iterrows():
        if len(records) >= limit:
            break
        record = {}
        for col, val in row.items():
            if col == "geometry":
                record["geometry_wkt"] = val.wkt if val is not None else None
            elif hasattr(val, "item"):
                record[col] = val.item()
            else:
                record[col] = val
        record["osm_id"] = str(idx)
        records.append(record)
    truncated = len(gdf) > limit
    return {"features": records, "count": len(records), "truncated": truncated}


def register(mcp: FastMCP, store: GraphStore) -> None:
    @mcp.tool
    async def get_features(
        source: str,
        tags: dict,
        lng: float | None = None,
        lat: float | None = None,
        dist_m: float = 500.0,
        north: float | None = None,
        south: float | None = None,
        east: float | None = None,
        west: float | None = None,
        place: str | None = None,
        limit: int = _DEFAULT_LIMIT,
    ) -> dict:
        """
        Fetch OSM features matching tags from a point, bounding box, or named place.

        source: 'point' | 'bbox' | 'place'

        For source='point': provide lng, lat, dist_m. Coordinates in lng, lat order.
        For source='bbox': provide north, south, east, west.
        For source='place': provide place (geocodable name).

        tags examples: {"amenity": "school"}, {"shop": "supermarket"}, {"leisure": "park"}.
        Use specific tag values to avoid Overpass timeouts. Times out after 25 seconds.
        Returns up to limit features (default 100); check 'truncated' if True.
        """
        try:
            if source == "point":
                if lng is None or lat is None:
                    raise ValueError("source='point' requires lng and lat")
                gdf = await asyncio.wait_for(
                    asyncio.to_thread(
                        ox.features_from_point, (lat, lng), tags=tags, dist=dist_m
                    ),
                    timeout=_DEFAULT_TIMEOUT,
                )
            elif source == "bbox":
                if any(v is None for v in (north, south, east, west)):
                    raise ValueError("source='bbox' requires north, south, east, west")
                gdf = await asyncio.wait_for(
                    asyncio.to_thread(
                        ox.features_from_bbox,
                        bbox=(north, south, east, west),
                        tags=tags,
                    ),
                    timeout=_DEFAULT_TIMEOUT,
                )
            elif source == "place":
                if not place:
                    raise ValueError("source='place' requires a place argument")
                gdf = await asyncio.wait_for(
                    asyncio.to_thread(ox.features_from_place, place, tags=tags),
                    timeout=_DEFAULT_TIMEOUT,
                )
            else:
                raise ValueError(
                    f"source must be 'point', 'bbox', or 'place', got '{source}'"
                )
        except TimeoutError:
            raise RuntimeError(
                f"Overpass API timed out after {_DEFAULT_TIMEOUT}s. "
                "Use a more specific tag value, reduce dist_m, or use a smaller area."
            )
        return _gdf_to_records(gdf, limit)
