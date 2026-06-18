import claude_code_sdk._internal.client as _sdk_client
import claude_code_sdk._internal.message_parser as _mp
from claude_code_sdk._errors import MessageParseError
from claude_code_sdk.types import SystemMessage

_original_parse_message = _mp.parse_message


def _patched_parse_message(data):
    msg_type = data.get("type") if isinstance(data, dict) else None
    try:
        return _original_parse_message(data)
    except MessageParseError:
        return SystemMessage(subtype=msg_type or "unknown", data=data)


_mp.parse_message = _patched_parse_message
_sdk_client.parse_message = _patched_parse_message

import osmnx as ox  # noqa: E402
import pytest  # noqa: E402

from desirepath.graph_store import GraphStore  # noqa: E402
from desirepath.server import create_server  # noqa: E402


@pytest.fixture(scope="session")
def piedmont_graph():
    G = ox.graph_from_place("Piedmont, California, USA", network_type="drive")
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    return G


@pytest.fixture(scope="session")
def store(piedmont_graph):
    s = GraphStore()
    s.add("piedmont", piedmont_graph, "place", "Piedmont, California, USA")
    return s


@pytest.fixture(scope="session")
def mcp_server(store):
    import desirepath.graph_store as gs

    gs._store = store
    return create_server()
