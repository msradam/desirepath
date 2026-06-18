import importlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="desirepath",
    help="Urban street network analysis via MCP and CLI.",
    no_args_is_help=True,
)

_PROJECT_DIR = Path(__file__).parent.parent.parent  # repo root


@app.command()
def serve(
    place: Optional[str] = typer.Option(None, help="Place name to load on startup."),
    lat: Optional[float] = typer.Option(None, help="Latitude for point-based load."),
    lng: Optional[float] = typer.Option(None, help="Longitude for point-based load."),
    dist: int = typer.Option(1000, help="Radius in meters for point-based load."),
    graphml: Optional[Path] = typer.Option(None, help="Path to a GraphML file."),
    name: str = typer.Option("graph", help="Name for the loaded graph."),
    network_type: str = typer.Option("drive", help="OSMnx network type."),
    port: Optional[int] = typer.Option(
        None, help="Run HTTP server on this port instead of stdio."
    ),
    host: str = typer.Option("127.0.0.1", help="Host for HTTP transport."),
) -> None:
    """Start the MCP server (stdio by default; use --port for HTTP)."""
    import asyncio

    import osmnx as ox

    from desirepath.server import create_server, mount

    if graphml:
        typer.echo(f"Loading '{graphml}'...", err=True)
        G = ox.load_graphml(str(graphml))
        typer.echo(f"Loaded: {len(G.nodes)} nodes, {len(G.edges)} edges", err=True)
        server = mount(G, name=name)
    elif place:
        typer.echo(f"Fetching '{place}' ({network_type}) from OSM...", err=True)
        G = ox.graph_from_place(place, network_type=network_type)
        G = ox.add_edge_speeds(G)
        G = ox.add_edge_travel_times(G)
        typer.echo(f"Loaded: {len(G.nodes)} nodes, {len(G.edges)} edges", err=True)
        server = mount(G, name=name)
    elif lat is not None and lng is not None:
        typer.echo(
            f"Fetching ({lat}, {lng}) dist={dist}m ({network_type})...", err=True
        )
        G = ox.graph_from_point((lat, lng), dist=dist, network_type=network_type)
        G = ox.add_edge_speeds(G)
        G = ox.add_edge_travel_times(G)
        typer.echo(f"Loaded: {len(G.nodes)} nodes, {len(G.edges)} edges", err=True)
        server = mount(G, name=name)
    else:
        typer.echo(
            "Starting empty; use load_graph(source='place') to load a graph.",
            err=True,
        )
        server = create_server()

    if port:
        typer.echo(f"Serving on http://{host}:{port}/mcp", err=True)
        asyncio.run(server.run_async(transport="streamable-http", host=host, port=port))
    else:
        server.run()


@app.command()
def stats(
    place: str = typer.Argument(..., help="Place name to analyze."),
    network_type: str = typer.Option("drive", help="OSMnx network type."),
) -> None:
    """Print basic stats for a place as JSON."""
    import osmnx as ox

    typer.echo(f"Fetching '{place}' ({network_type})...", err=True)
    G = ox.graph_from_place(place, network_type=network_type)
    result = ox.stats.basic_stats(G)
    out: dict = {}
    for k, v in result.items():
        if hasattr(v, "item"):
            out[k] = v.item()
        elif isinstance(v, dict):
            out[k] = {
                str(kk): vv.item() if hasattr(vv, "item") else vv
                for kk, vv in v.items()
            }
        else:
            out[k] = v
    typer.echo(json.dumps(out, indent=2))


@app.command()
def compare(
    place_a: str = typer.Argument(..., help="First place name."),
    place_b: str = typer.Argument(..., help="Second place name."),
    network_type: str = typer.Option("drive", help="OSMnx network type."),
) -> None:
    """Compare two places side by side."""
    import osmnx as ox

    def summarize(place: str) -> dict:
        typer.echo(f"Fetching '{place}'...", err=True)
        G = ox.graph_from_place(place, network_type=network_type)
        s = ox.stats.basic_stats(G)
        n, e = len(G.nodes), len(G.edges)
        meshedness = (e - n + 1) / (2 * n - 5) if (2 * n - 5) > 0 else None
        return {
            "place": place,
            "nodes": n,
            "edges": e,
            "avg_streets_per_node": round(float(s.get("streets_per_node_avg", 0)), 3),
            "edge_length_total_km": round(
                float(s.get("edge_length_total", 0)) / 1000, 2
            ),
            "edge_length_avg_m": round(float(s.get("edge_length_avg", 0)), 1),
            "circuity_avg": round(float(s.get("circuity_avg", 0)), 4),
            "meshedness": round(meshedness, 4) if meshedness is not None else None,
        }

    a = summarize(place_a)
    b = summarize(place_b)
    typer.echo(json.dumps({"a": a, "b": b}, indent=2))


@app.command()
def doctor() -> None:
    """Check environment and print client config snippets."""
    ok = typer.style("v", fg=typer.colors.GREEN, bold=True)
    fail = typer.style("x", fg=typer.colors.RED, bold=True)
    warn = typer.style("!", fg=typer.colors.YELLOW, bold=True)

    typer.echo("\ndesirepath doctor\n" + "-" * 40)

    v = sys.version_info
    if v >= (3, 12):
        typer.echo(f"  {ok}  Python {v.major}.{v.minor}.{v.micro}")
    else:
        typer.echo(f"  {fail}  Python {v.major}.{v.minor}.{v.micro} (need >= 3.12)")

    uv_path = shutil.which("uv")
    if uv_path:
        try:
            uv_ver = subprocess.check_output(["uv", "--version"], text=True).split()[1]
            typer.echo(f"  {ok}  uv {uv_ver}  ({uv_path})")
        except Exception:
            typer.echo(f"  {ok}  uv found ({uv_path})")
    else:
        typer.echo(f"  {fail}  uv not found in PATH")

    packages = [
        ("osmnx", "osmnx"),
        ("fastmcp", "fastmcp"),
        ("networkx", "networkx"),
        ("momepy", "momepy"),
        ("geopandas", "geopandas"),
        ("shapely", "shapely"),
        ("typer", "typer"),
        ("anthropic", "anthropic"),
        ("numpy", "numpy"),
    ]
    for mod, display in packages:
        try:
            m = importlib.import_module(mod)
            ver = getattr(m, "__version__", "?")
            typer.echo(f"  {ok}  {display} {ver}")
        except ImportError:
            typer.echo(f"  {fail}  {display} -- not importable")

    typer.echo("\n  Optional packages:")
    optional = [
        ("pyrosm", "pyrosm", 'uv add "desirepath[loaders]"'),
        ("city2graph", "city2graph", 'uv add "desirepath[transit]"'),
        ("pandana", "pandana", 'uv add "desirepath[access]"'),
        ("libpysal", "libpysal", 'uv add "desirepath[spatial]"'),
        ("esda", "esda", 'uv add "desirepath[spatial]"'),
        ("spaghetti", "spaghetti", 'uv add "desirepath[spatial]"'),
    ]
    for mod, display, install_cmd in optional:
        try:
            m = importlib.import_module(mod)
            ver = getattr(m, "__version__", "?")
            typer.echo(f"  {ok}  {display} {ver}")
        except ImportError:
            typer.echo(f"  {warn}  {display} -- not installed  ({install_cmd})")

    try:
        if importlib.util.find_spec("desirepath") is not None:
            typer.echo(f"  {ok}  desirepath importable")
        else:
            typer.echo(f"  {fail}  desirepath not found")
    except Exception as e:
        typer.echo(f"  {fail}  desirepath import failed: {e}")

    typer.echo("\n  Connectivity checks (may take a few seconds)...")
    try:
        import osmnx as ox

        ox.geocode("Times Square, New York")
        typer.echo(f"  {ok}  Nominatim reachable")
    except Exception as e:
        typer.echo(f"  {warn}  Nominatim: {e}")

    try:
        import osmnx as ox

        ox.features_from_point((40.758, -73.985), tags={"amenity": "cafe"}, dist=100)
        typer.echo(f"  {ok}  Overpass API reachable")
    except Exception as e:
        typer.echo(f"  {warn}  Overpass API: {e}")

    venv_exe = _PROJECT_DIR / ".venv" / "bin" / "desirepath"
    typer.echo(f"\n  Project dir : {_PROJECT_DIR}")
    typer.echo(
        f"  venv binary : {venv_exe} {'(exists)' if venv_exe.exists() else '(not found)'}"
    )

    project_dir = str(_PROJECT_DIR)
    typer.echo("\n" + "-" * 40)
    typer.echo(
        "Claude Desktop  ~/Library/Application Support/Claude/claude_desktop_config.json"
    )
    typer.echo("-" * 40)
    config = f"""\
{{
  "mcpServers": {{
    "desirepath": {{
      "command": "uv",
      "args": ["run", "--project", "{project_dir}", "desirepath", "serve"]
    }}
  }}
}}"""
    typer.echo(config)

    typer.echo("\n" + "-" * 40)
    typer.echo("Claude Code  .mcp.json  (project root)")
    typer.echo("-" * 40)
    mcp_json = f"""\
{{
  "mcpServers": {{
    "desirepath": {{
      "command": "uv",
      "args": ["run", "desirepath", "serve"],
      "cwd": "{project_dir}",
      "type": "stdio"
    }}
  }}
}}"""
    typer.echo(mcp_json)
    typer.echo()


def main() -> None:
    app()
