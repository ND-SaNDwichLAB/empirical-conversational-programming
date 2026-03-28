"""
t-SNE visualization of session archetypes.
Reads: ../data/clusters/tsne_visualization.json
Outputs: results/tsne.pdf
"""

import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.lines as mlines

# -- Config --

INPUT_PATH = Path("../data/clusters/tsne_visualization.json")
OUT_DIR = Path("./results")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CLUSTER_NAMES = {
    0: "Planning & Comprehension",
    1: "Failure-Driven Debugging",
    2: "Focused Iterative Refinement",
    3: "Continuation-Driven Delegation",
    4: "Extended Iterative\nCo-Development",
    5: "Toolchain-Oriented Operations",
}

CLUSTER_COLORS = {
    0: "#4e79a7",
    1: "#e15759",
    2: "#59a14f",
    3: "#f28e2b",
    4: "#b07aa1",
    5: "#76b7b2",
}

# -- Load data --

with open(INPUT_PATH, "r", encoding="utf-8") as f:
    records = json.load(f)

xs = np.array([r["x"] for r in records])
ys = np.array([r["y"] for r in records])
cids = np.array([r["cluster_id"] for r in records])
is_medoid = np.array([r["is_medoid"] for r in records])

# -- Plot --

fig, ax = plt.subplots(figsize=(9, 6))

for cid in sorted(CLUSTER_NAMES):
    mask = (cids == cid) & ~is_medoid
    ax.scatter(
        xs[mask],
        ys[mask],
        c=CLUSTER_COLORS[cid],
        s=12,
        alpha=0.65,
        edgecolors="none",
        label=CLUSTER_NAMES[cid],
        rasterized=True,
    )

# Medoids on top
import matplotlib.colors as mcolors


def darken(hex_color, factor=0.8):
    rgb = mcolors.to_rgb(hex_color)
    return tuple(c * factor for c in rgb)


for cid in sorted(CLUSTER_NAMES):
    mask = (cids == cid) & is_medoid
    if mask.any():
        ax.scatter(
            xs[mask],
            ys[mask],
            c=CLUSTER_COLORS[cid],
            s=200,
            marker="*",
            edgecolors=darken(CLUSTER_COLORS[cid]),
            linewidths=1.2,
            zorder=10,
        )

# Legend
handles = [
    mlines.Line2D(
        [],
        [],
        marker="o",
        color="w",
        markerfacecolor=CLUSTER_COLORS[cid],
        markersize=10,
        label=CLUSTER_NAMES[cid],
    )
    for cid in sorted(CLUSTER_NAMES)
]
handles.append(
    mlines.Line2D(
        [],
        [],
        marker="*",
        color="w",
        markerfacecolor="gray",
        markeredgecolor="black",
        markersize=14,
        label="Medoid",
    )
)

for spine in ax.spines.values():
    spine.set_visible(False)

ax.set_xlim(xs.min() - 1, xs.max() + 1)
ax.set_ylim(ys.min() - 1, ys.max() + 1)

ax.set_xticks([])
ax.set_yticks([])
ax.set_xlabel("")
ax.set_ylabel("")
ax.tick_params(axis="both", labelsize=14, length=0)


for spine in ax.spines.values():
    spine.set_color("#bbbbbb")
    spine.set_linewidth(0.5)

plt.tight_layout()
fig.savefig(OUT_DIR / "tsne.pdf", bbox_inches="tight", dpi=300)
fig.savefig(OUT_DIR / "tsne.svg", bbox_inches="tight", dpi=300)
print(f"Saved to {OUT_DIR / 'tsne.pdf'}")
print(f"Saved to {OUT_DIR / 'tsne.svg'}")
