import json
from pathlib import Path

import networkx as nx
import osmnx as ox
from fastmcp import Context, FastMCP
from fastmcp.apps import AppConfig, UI_EXTENSION_ID

from desirepath.graph_store import GraphStore

_SAVE_DIR = Path.home() / "Downloads"
_MAP_APP = AppConfig(resource_uri="ui://desirepath/map")

_TILE_URL = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"


def _edge_lines(edges_gdf, simplify: float = 0.0001) -> list:
    result = []
    for geom in edges_gdf.geometry:
        s = geom.simplify(simplify)
        result.append([[round(y, 4), round(x, 4)] for x, y in s.coords])
    return result


def _map_bounds(edges_gdf) -> tuple:
    b = edges_gdf.total_bounds  # [minx, miny, maxx, maxy]
    sw = [round(b[1], 4), round(b[0], 4)]
    ne = [round(b[3], 4), round(b[2], 4)]
    center = [round((b[1] + b[3]) / 2, 4), round((b[0] + b[2]) / 2, 4)]
    return sw, ne, center


def _fallback_html(
    edges: list, overlay: dict | None, sw: list, ne: list, center: list
) -> str:
    edges_js = json.dumps(edges, separators=(",", ":"))
    body = (
        f'var m=L.map("map").setView([{center[0]},{center[1]}],15);'
        f'L.tileLayer("{_TILE_URL}",{{attribution:"(c)OSM (c)CARTO",maxZoom:19}}).addTo(m);'
    )
    if overlay and overlay.get("type") == "route":
        body += (
            f'{edges_js}.forEach(c=>L.polyline(c,{{color:"#bbb",weight:1,opacity:.5}}).addTo(m));'
            f'L.polyline({json.dumps(overlay["route"], separators=(",", ":"))},{{color:"#e00",weight:4,opacity:.9}}).addTo(m);'
            f'L.circleMarker({overlay["orig"]},{{radius:8,color:"#080",fillColor:"#2c2",fillOpacity:1}}).bindTooltip("Origin").addTo(m);'
            f'L.circleMarker({overlay["dest"]},{{radius:8,color:"#800",fillColor:"#e33",fillOpacity:1}}).bindTooltip("Destination").addTo(m);'
        )
    elif overlay and overlay.get("type") == "isochrone":
        body += f'{edges_js}.forEach(c=>L.polyline(c,{{color:"#ccc",weight:1,opacity:.5}}).addTo(m));'
        if overlay.get("hull"):
            body += f'L.geoJSON({json.dumps(overlay["hull"], separators=(",", ":"))},{{style:{{color:"#2255aa",fillOpacity:.15,weight:2}}}}).addTo(m);'
        body += f'{json.dumps(overlay["nodes"], separators=(",", ":"))}.forEach(pt=>L.circleMarker(pt,{{radius:4,color:"#2255aa",fillOpacity:.7}}).addTo(m));'
    else:
        body += f'{edges_js}.forEach(c=>L.polyline(c,{{color:"#555",weight:2,opacity:.7}}).addTo(m));'
    body += f"m.fitBounds([[{sw[0]},{sw[1]}],[{ne[0]},{ne[1]}]]);"
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>'
        '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
        "<style>body{margin:0}#map{width:100%;height:100vh}</style>"
        f'</head><body><div id="map"></div><script>{body}</script></body></html>'
    )


def register(mcp: FastMCP, store: GraphStore) -> None:
    @mcp.tool(app=_MAP_APP)
    def map_graph(graph_name: str = None, ctx: Context = None) -> str:
        """
        Render the street network as an interactive Leaflet map.

        When the host supports MCP Apps (MCPJam Inspector), the map appears
        inline as a live iframe. On other hosts, returns standalone HTML saved
        to ~/Downloads/desirepath_map.html.
        """
        G = store.get(graph_name)
        _, edges_gdf = ox.graph_to_gdfs(G)
        sw, ne, center = _map_bounds(edges_gdf)
        edges = _edge_lines(edges_gdf)

        if ctx and ctx.client_supports_extension(UI_EXTENSION_ID):
            return json.dumps(
                {
                    "type": "graph",
                    "edges": edges,
                    "bounds": [sw, ne],
                    "center": center,
                    "node_count": len(G.nodes),
                    "edge_count": len(G.edges),
                },
                separators=(",", ":"),
            )

        html = _fallback_html(edges, None, sw, ne, center)
        out_path = _SAVE_DIR / "desirepath_map.html"
        out_path.write_text(html, encoding="utf-8")
        return html

    @mcp.tool(app=_MAP_APP)
    def map_route(
        orig_lng: float,
        orig_lat: float,
        dest_lng: float,
        dest_lat: float,
        weight: str = "length",
        graph_name: str = None,
        ctx: Context = None,
    ) -> str:
        """
        Render the shortest path as an interactive Leaflet map.

        Coordinates in lng, lat order. Finds nearest network nodes, computes the
        shortest path by the given weight, and renders it inline (MCP Apps) or saves
        to ~/Downloads/desirepath_route_map.html (fallback).
        weight: 'length' (meters) or 'travel_time' (seconds, requires enriched graph).
        """
        from shapely.geometry import LineString
        from shapely.ops import linemerge

        G = store.get(graph_name)
        orig_node = ox.nearest_nodes(G, orig_lng, orig_lat)
        dest_node = ox.nearest_nodes(G, dest_lng, dest_lat)
        route = ox.shortest_path(G, orig_node, dest_node, weight=weight)
        if route is None:
            raise ValueError(f"No {weight} path between the given coordinates.")

        _, edges_gdf = ox.graph_to_gdfs(G)
        sw, ne, center = _map_bounds(edges_gdf)
        edges = _edge_lines(edges_gdf)

        geoms, length_m = [], 0.0
        for u, v in zip(route[:-1], route[1:]):
            data = G[u][v][0]
            length_m += data.get("length", 0)
            geoms.append(
                data["geometry"]
                if "geometry" in data
                else LineString(
                    [
                        (G.nodes[u]["x"], G.nodes[u]["y"]),
                        (G.nodes[v]["x"], G.nodes[v]["y"]),
                    ]
                )
            )
        route_coords = [[round(y, 4), round(x, 4)] for x, y in linemerge(geoms).coords]
        orig_pt = [round(G.nodes[orig_node]["y"], 4), round(G.nodes[orig_node]["x"], 4)]
        dest_pt = [round(G.nodes[dest_node]["y"], 4), round(G.nodes[dest_node]["x"], 4)]

        if ctx and ctx.client_supports_extension(UI_EXTENSION_ID):
            return json.dumps(
                {
                    "type": "route",
                    "edges": edges,
                    "route": route_coords,
                    "orig": orig_pt,
                    "dest": dest_pt,
                    "bounds": [sw, ne],
                    "center": center,
                    "length_m": round(length_m, 1),
                },
                separators=(",", ":"),
            )

        overlay = {
            "type": "route",
            "route": route_coords,
            "orig": orig_pt,
            "dest": dest_pt,
        }
        html = _fallback_html(edges, overlay, sw, ne, center)
        out_path = _SAVE_DIR / "desirepath_route_map.html"
        out_path.write_text(html, encoding="utf-8")
        return html

    @mcp.tool(app=_MAP_APP)
    def map_isochrone(
        lat: float,
        lng: float,
        trip_time_s: float,
        graph_name: str = None,
        ctx: Context = None,
    ) -> str:
        """
        Render an isochrone as an interactive Leaflet map.

        lat, lng: center coordinate (lat first for this tool).
        trip_time_s: maximum travel time in seconds.
        Requires travel_time on edges; call add_edge_travel_times first.

        Renders reachable nodes as blue markers with a convex hull polygon overlay,
        inline (MCP Apps) or saved to ~/Downloads/desirepath_isochrone_map.html (fallback).
        """
        from shapely.geometry import MultiPoint, mapping

        G = store.get(graph_name)
        sample = next(iter(G.edges(data=True)), None)
        if sample is None or "travel_time" not in sample[2]:
            raise ValueError(
                "Graph edges are missing 'travel_time'. "
                "Call add_edge_travel_times before running map_isochrone."
            )

        center_node = ox.nearest_nodes(G, lng, lat)
        reachable = nx.single_source_dijkstra_path_length(
            G, center_node, cutoff=trip_time_s, weight="travel_time"
        )

        node_pts = [
            [round(G.nodes[n]["y"], 4), round(G.nodes[n]["x"], 4)]
            for n in reachable
            if "x" in G.nodes[n] and "y" in G.nodes[n]
        ]
        coords = [
            (G.nodes[n]["x"], G.nodes[n]["y"]) for n in reachable if "x" in G.nodes[n]
        ]
        hull = None
        if len(coords) >= 3:
            hull = mapping(MultiPoint(coords).convex_hull)

        _, edges_gdf = ox.graph_to_gdfs(G)
        sw, ne, _ = _map_bounds(edges_gdf)
        edges = _edge_lines(edges_gdf)
        map_center = [round(lat, 4), round(lng, 4)]

        if ctx and ctx.client_supports_extension(UI_EXTENSION_ID):
            return json.dumps(
                {
                    "type": "isochrone",
                    "edges": edges,
                    "nodes": node_pts,
                    "hull": hull,
                    "bounds": [sw, ne],
                    "center": map_center,
                    "reachable_count": len(node_pts),
                    "trip_time_s": trip_time_s,
                },
                separators=(",", ":"),
            )

        overlay = {"type": "isochrone", "nodes": node_pts, "hull": hull}
        html = _fallback_html(edges, overlay, sw, ne, map_center)
        out_path = _SAVE_DIR / "desirepath_isochrone_map.html"
        out_path.write_text(html, encoding="utf-8")
        return html
