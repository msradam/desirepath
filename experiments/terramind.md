# terramind

**Feasibility: low (v2+)**

## What it adds

TerraMind produces patch-level embeddings from Sentinel-2 optical and Sentinel-1 SAR imagery. Joining these embeddings by coordinate to OSMnx nodes gives each intersection a feature vector describing its visual and spectral context: vegetation density, impervious surface coverage, urban texture.

## Questions this enables

- Which intersections are in high-canopy areas, and does tree cover correlate with lower traffic speeds?
- How does impervious surface fraction vary with intersection degree?
- Can you cluster neighborhoods by their combined network topology and spectral signature?
- Identify industrial versus residential zones from imagery alone, without OSM land-use tags.

## Integration point

The coordinate join is straightforward once embeddings are available. Each OSMnx node has `x` (longitude) and `y` (latitude). The join is a spatial nearest-neighbor lookup against a raster grid of embedding centroids.

```python
# pseudocode -- TerraMind inference pipeline not shown
import numpy as np
from sklearn.neighbors import BallTree

# embeddings: array of shape (n_patches, embedding_dim)
# patch_coords: array of shape (n_patches, 2) in lat/lng

tree = BallTree(np.radians(patch_coords), metric="haversine")
node_coords = np.array([[G.nodes[n]["y"], G.nodes[n]["x"]] for n in G.nodes])
_, idxs = tree.query(np.radians(node_coords), k=1)

for i, n in enumerate(G.nodes):
    G.nodes[n]["terramind_embedding"] = embeddings[idxs[i, 0]].tolist()
```

After this, `mount(G)` exposes the embeddings via `graph://{name}/nodes/{id}`.

## Blocking issues

1. **Model weights.** Several gigabytes. Not bundled with pip install.
2. **PyTorch dependency.** Significant install footprint. Conflicts with environments that pin PyTorch to a specific CUDA version.
3. **Imagery pipeline.** Sentinel-2 requires Copernicus credentials. Scenes are large (100+ MB per tile). Cloud masking, atmospheric correction, and temporal compositing are non-trivial preprocessing steps.
4. **Inference is not trivial.** Tile extraction, patch slicing, batched inference, and reassembly require a custom pipeline.

The coordinate join at the end is easy. Everything before it is hard.

## Verdict

v2, gated behind `uv add "desirepath[satellite]"`. Would require a companion `desirepath-terramind` package that handles the inference pipeline. Not a near-term priority.
