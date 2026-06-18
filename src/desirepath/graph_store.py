import networkx as nx
from dataclasses import dataclass
from typing import Optional


@dataclass
class GraphEntry:
    graph: nx.MultiDiGraph
    name: str
    source: str  # "place", "point", "file", "subgraph", "mount"
    description: str = ""


class GraphStore:
    def __init__(self):
        self._graphs: dict[str, GraphEntry] = {}
        self._active: Optional[str] = None

    def add(
        self, name: str, G: nx.MultiDiGraph, source: str, description: str = ""
    ) -> None:
        self._graphs[name] = GraphEntry(
            graph=G, name=name, source=source, description=description
        )
        if self._active is None:
            self._active = name

    def get(self, name: Optional[str] = None) -> nx.MultiDiGraph:
        target = name or self._active
        if not target or target not in self._graphs:
            raise ValueError(f"Graph '{target}' not found. Load a graph first.")
        return self._graphs[target].graph

    def get_entry(self, name: Optional[str] = None) -> GraphEntry:
        target = name or self._active
        if not target or target not in self._graphs:
            raise ValueError(f"Graph '{target}' not found.")
        return self._graphs[target]

    def set_active(self, name: str) -> None:
        if name not in self._graphs:
            raise ValueError(f"Graph '{name}' not found.")
        self._active = name

    def drop(self, name: str) -> None:
        if name not in self._graphs:
            raise ValueError(f"Graph '{name}' not found.")
        del self._graphs[name]
        if self._active == name:
            self._active = next(iter(self._graphs), None)

    def list(self) -> list[dict]:
        return [
            {
                "name": e.name,
                "active": e.name == self._active,
                "source": e.source,
                "description": e.description,
                "nodes": len(e.graph.nodes),
                "edges": len(e.graph.edges),
            }
            for e in self._graphs.values()
        ]

    @property
    def active_name(self) -> Optional[str]:
        return self._active


_store = GraphStore()


def get_store() -> GraphStore:
    return _store
