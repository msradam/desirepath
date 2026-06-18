# gnn

**Feasibility: low (research only)**

## What it means to expose GNN embeddings as MCP tools

A graph neural network trained on a street network produces a node embedding: a dense vector that encodes each intersection's structural position in the graph. If those vectors are stored as node attributes, desirepath can expose them via `graph://{name}/nodes/{id}` immediately.

The interesting question is what an agent would do with them:

- **Semantic similarity queries**: "find intersections with similar structural roles to this one" -- cosine similarity in embedding space
- **Neighborhood classification**: cluster embeddings to partition the network into structurally similar zones without any labeled data
- **Anomaly detection**: intersections whose embeddings are far from their spatial neighbors in embedding space may indicate errors in the road network or unusual design choices

## city2graph as the bridge

city2graph's PyTorch Geometric output is the natural bridge. `c2g.from_osmnx(G)` returns a `torch_geometric.data.Data` object. Run a GNN on that data, then map the node embeddings back to OSMnx node IDs for storage in the graph.

```python
import city2graph as c2g
import torch
from torch_geometric.nn import GCNConv

data = c2g.from_osmnx(G)
# ... train or load a GCN ...
embeddings = model(data.x, data.edge_index)  # shape: (n_nodes, embedding_dim)

for i, node_id in enumerate(data.node_ids):
    G.nodes[node_id]["gnn_embedding"] = embeddings[i].detach().tolist()
```

## Why it is not straightforward

1. **A trained model is required.** Embeddings require a GNN, and a GNN requires either training from scratch or a pre-trained checkpoint. There are no widely available pre-trained urban street network GNNs analogous to ImageNet-pretrained vision models.
2. **Labeled data is scarce.** Supervised GNNs need labeled nodes (e.g., intersection type, crash risk, land use). Urban labeled datasets are jurisdiction-specific and often proprietary.
3. **Transfer across cities is an open research question.** A GNN trained on Manhattan may not transfer to Houston. The structural statistics that generalize across cities (degree distribution, betweenness) are already available as explicit tools in desirepath without any machine learning.
4. **Unsupervised GNNs exist** (GraphSAGE, DGI, node2vec), but their embeddings are not interpretable without downstream tasks. An agent cannot explain what a cluster in embedding space means without labels.

## The interesting research question

Can a pre-trained urban GNN trained on one city's street network transfer useful structural representations to another? This is not answered in the literature. If it could, it would make semantic similarity queries across cities possible without city-specific training.

## Verdict

Research experiment only. No near-term path to a tool surface that an agent can use productively. Revisit when pre-trained urban network models become available.
