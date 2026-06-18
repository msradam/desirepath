from fastmcp import FastMCP
from fastmcp.apps import AppConfig, ResourceCSP

_MAP_CSP = ResourceCSP(
    resource_domains=[
        "https://unpkg.com",
        "https://*.basemaps.cartocdn.com",
        "https://*.tile.openstreetmap.org",
    ],
    connect_domains=["https://unpkg.com"],
)

_MAP_HTML = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>desirepath Map</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,sans-serif}
#map{width:100%;height:100vh}
#badge{
  position:absolute;top:12px;left:50%;transform:translateX(-50%);
  background:rgba(20,20,20,.78);color:#fff;padding:5px 14px;
  border-radius:999px;font-size:12px;z-index:1000;
  pointer-events:none;white-space:nowrap;transition:opacity .4s;
}
</style>
</head>
<body>
<div id="map"></div>
<div id="badge">Waiting for graph data...</div>
<script type="module">
import{App}from"https://unpkg.com/@modelcontextprotocol/ext-apps@1.7.4/dist/src/app-with-deps.js";

const badge=document.getElementById("badge");
let map=null;

function render(d){
  if(map){map.remove();map=null;}
  map=L.map("map");
  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",{
    attribution:"(c)OpenStreetMap (c)CARTO",maxZoom:19
  }).addTo(map);

  const route=d.type==="route";
  const iso=d.type==="isochrone";

  d.edges.forEach(c=>L.polyline(c,{
    color:route?"#bbb":iso?"#ccc":"#555",weight:route||iso?1:2,opacity:.65
  }).addTo(map));

  if(route){
    L.polyline(d.route,{color:"#e00",weight:4,opacity:.9}).addTo(map);
    L.circleMarker(d.orig,{radius:8,color:"#080",fillColor:"#2c2",fillOpacity:1})
      .bindTooltip("Origin").addTo(map);
    L.circleMarker(d.dest,{radius:8,color:"#800",fillColor:"#e33",fillOpacity:1})
      .bindTooltip("Destination").addTo(map);
    badge.textContent="Route: "+(d.length_m/1000).toFixed(2)+" km";
  }else if(iso){
    if(d.hull){
      L.geoJSON(d.hull,{style:{color:"#2255aa",fillOpacity:.15,weight:2,dashArray:"6 4"}}).addTo(map);
    }
    d.nodes.forEach(pt=>L.circleMarker(pt,{radius:4,color:"#2255aa",fillColor:"#4477cc",fillOpacity:.7,weight:1}).addTo(map));
    badge.textContent=d.reachable_count+" nodes reachable in "+d.trip_time_s+"s";
  }else{
    badge.textContent=d.node_count+" nodes · "+d.edge_count+" edges";
  }

  map.fitBounds(d.bounds);
  setTimeout(()=>{badge.style.opacity=".25";},3500);
}

const app=new App({name:"desirepath Map",version:"1.0"});
app.ontoolresult=({content})=>{
  const t=content.find(c=>c.type==="text");
  if(!t)return;
  try{render(JSON.parse(t.text));}
  catch(e){badge.textContent="Error: "+e.message;}
};

try{
  await app.connect();
  badge.textContent="Connected: call map_graph, map_route, or map_isochrone";
}catch(e){
  badge.textContent="SDK error: "+e.message;
}
</script>
</body>
</html>
"""


def register(mcp: FastMCP) -> None:
    @mcp.resource(
        "ui://desirepath/map",
        app=AppConfig(csp=_MAP_CSP),
        mime_type="text/html",
    )
    def map_renderer() -> str:
        """Leaflet iframe renderer for map_graph, map_route, and map_isochrone MCP App tools."""
        return _MAP_HTML
