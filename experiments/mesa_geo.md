# mesa-geo

**Feasibility: medium**

## What it adds

mesa and mesa-geo enable agent-based simulation on street networks. Agents (pedestrians, vehicles, cyclists) are placed on network nodes, move along edges according to a behavioral model, and accumulate traversal statistics. The output is edge-level congestion data: which segments were used most often, where bottlenecks formed, what the spatial distribution of activity looks like.

This answers questions that no static analysis tool in desirepath can touch: "If 500 commuters start at random residential nodes and route to a downtown cluster, which edges become bottlenecks?" or "How does restricting one arterial redistribute flow across the rest of the network?"

## Integration point

`mesa.spaces.NetworkGrid(G)` accepts any `nx.Graph` directly. mesa-geo wraps this with a `GeoSpace` layer that understands lat/lng node coordinates. The OSMnx graph is passed in unchanged; no conversion or attribute renaming is required.

```python
import mesa
import mesa_geo as mg

class WalkAgent(mg.GeoAgent):
    def step(self):
        neighbors = self.model.grid.get_neighbors(self.pos, include_center=False)
        if neighbors:
            self.model.grid.move_agent(self, random.choice(neighbors))

class WalkModel(mesa.Model):
    def __init__(self, G, n_agents):
        self.grid = mesa.spaces.NetworkGrid(G)
        for _ in range(n_agents):
            agent = WalkAgent(self.next_id(), self, None)
            start = random.choice(list(G.nodes))
            self.grid.place_agent(agent, start)
        self.datacollector = mesa.DataCollector(
            agent_reporters={"Position": "pos"}
        )

    def step(self):
        self.datacollector.collect(self)
        for agent in self.agents:
            agent.step()
```

After N steps, count agent positions per node, join to G.nodes, and store back as a `traversal_count` attribute. `mount(G)` then exposes this via the resources.

## New tool surface

`simulate_flow(n_agents, steps, model='random_walk', graph_name)` -- run N agents for K steps using the specified behavioral model; return node traversal counts and top 10 most-visited edges as a congestion estimate.

## Blocking issues

1. **Mesa 4.0 breaking changes.** Mesa 4.0 is in alpha as of mid-2026 with substantial API changes. Pin to `mesa>=3.0,<4.0` and `mesa-geo>=0.9,<1.0` until 4.0 stabilizes.
2. **Random walk vs. routing.** A pure random walk produces a traversal distribution proportional to node degree, not realistic flow. Useful for stress-testing the network topology; not a substitute for traffic assignment. A shortest-path behavioral model requires per-agent route computation, which gets slow past ~5000 agents.
3. **Simulation is not deterministic by default.** Seed the RNG for reproducible results.

## License

Mesa: Apache 2.0. mesa-geo: MIT. No license blocker.

## Effort to integrate

Medium. The network setup is one call. The complexity is in the behavioral model and result summarization. A random-walk model is one afternoon. A shortest-path model is two days.

## Verdict

experiments/ for now; promote when the mesa 4.0 API stabilizes. The random-walk version is the right starting point.
