# experiments

Feasibility studies for integrations being evaluated before promotion into the main package. Each file documents what the library does, where it connects to desirepath, what new tool surface it would add, and what is blocking or accelerating adoption.

Nothing here is imported by the main package. Code stubs require their own install step and are meant to be run independently.

| Experiment | Feasibility | Status |
|---|---|---|
| [city2graph](city2graph.md) | high | promoted -- in `desirepath[transit]` |
| [cityseer](cityseer.md) | medium | hold -- AGPLv3 |
| [mesa-geo](mesa_geo.md) | medium | hold -- mesa 4.0 API instability |
| [aequilibrae](aequilibrae.md) | medium | hold -- OD matrix requirement |
| [trackintel](trackintel.md) | medium | hold -- GPS data dependency |
| [urbanaccess](urbanaccess.md) | medium-low | deprioritized -- city2graph supersedes |
| [terramind](terramind.md) | low | v2+, satellite pipeline required |
| [gnn](gnn.md) | low | research only |
