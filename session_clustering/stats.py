"""
Cluster-level quantitative statistics for RQ2 session archetypes.

Reads: ../data/clusters/tsne_visualization.json
       (each record: sha, timestamp, cluster_id, is_medoid, x, y, sequence)

Outputs (all written to ./results/):
  - cluster_overview.csv          : per-cluster summary (n, session length stats, multi-label rate)
  - category_heatmap.csv          : cluster x 7 main-category message proportions
  - subcategory_top5.csv          : top-5 subcategories per cluster
  - positional_patterns.csv       : intent share in first / middle / last third of session
  - fig_category_heatmap.pdf      : heatmap figure
  - fig_session_length_violin.pdf : session-length violin plot
  - fig_positional_patterns.pdf   : positional pattern facet plot
"""

import json
import math
from pathlib import Path
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
import seaborn as sns

# ── Configuration ─────────────────────────────────────────────────────────────

INPUT_PATH = Path("../data/clusters/tsne_visualization.json")
OUT_DIR = Path("./results")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CLUSTER_NAMES = {
    0: "Planning & Comprehension",
    1: "Failure-Driven Debugging",
    2: "Focused Iterative Refinement",
    3: "Continuation-Driven Delegation",
    4: "Extended Iterative Co-Development",
    5: "Toolchain-Oriented Operations",
}

MAIN_CATEGORIES = {
    "1": "Code Authoring",
    "2": "Failure Reporting",
    "3": "Inquiry",
    "4": "Context Specification",
    "5": "Validation",
    "6": "Delegation",
    "7": "Workflow Control",
}

MAIN_CAT_ORDER = ["1", "2", "3", "4", "5", "6", "7"]
MAIN_CAT_LABELS = [MAIN_CATEGORIES[c] for c in MAIN_CAT_ORDER]


# ── Helpers ───────────────────────────────────────────────────────────────────


def parse_label_set(label_str: str) -> list[str]:
    """Split a multi-label string like '1.2 Iterative Modification + 2.2 Symptom Description'
    into individual subcategory labels."""
    return [l.strip() for l in label_str.split("+")]


def sub_to_main(label: str) -> str:
    """Extract main-category code from a subcategory label, e.g. '1.2 ...' -> '1'."""
    return label.strip().split(".")[0]


def compute_percentiles(values):
    """Return dict with mean, median, Q1, Q3, min, max."""
    arr = np.array(values)
    return {
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "q1": float(np.percentile(arr, 25)),
        "q3": float(np.percentile(arr, 75)),
        "min": int(np.min(arr)),
        "max": int(np.max(arr)),
    }


# ── Load data ─────────────────────────────────────────────────────────────────

print("Loading data...")
with open(INPUT_PATH, "r", encoding="utf-8") as f:
    records = json.load(f)
print(
    f"  Loaded {len(records)} sessions across clusters "
    f"{sorted(set(r['cluster_id'] for r in records))}"
)

# Group by cluster
clusters = defaultdict(list)
for r in records:
    clusters[r["cluster_id"]].append(r)


# =============================================================================
# 1. Cluster overview table
# =============================================================================

print("\n[1/5] Computing cluster overview stats...")

overview_rows = []
for cid in sorted(clusters):
    sessions = clusters[cid]
    lengths = [len(s["sequence"]) for s in sessions]
    length_stats = compute_percentiles(lengths)

    # Multi-label rate: fraction of messages with 2+ labels
    n_msgs = 0
    n_multi = 0
    for s in sessions:
        for msg in s["sequence"]:
            labels = parse_label_set(msg)
            n_msgs += 1
            if len(labels) > 1:
                n_multi += 1

    multi_rate = n_multi / n_msgs if n_msgs > 0 else 0.0

    overview_rows.append(
        {
            "cluster_id": cid,
            "cluster_name": CLUSTER_NAMES[cid],
            "n_sessions": len(sessions),
            "pct_sessions": len(sessions) / len(records) * 100,
            "n_messages": n_msgs,
            "len_mean": length_stats["mean"],
            "len_median": length_stats["median"],
            "len_q1": length_stats["q1"],
            "len_q3": length_stats["q3"],
            "len_min": length_stats["min"],
            "len_max": length_stats["max"],
            "multi_label_rate": multi_rate * 100,
        }
    )

overview_df = pd.DataFrame(overview_rows)
overview_df.to_csv(OUT_DIR / "cluster_overview.csv", index=False, float_format="%.2f")
print("  Saved cluster_overview.csv")


# =============================================================================
# 2. Main-category heatmap (cluster x 7 categories)
# =============================================================================

print("[2/5] Computing main-category proportions per cluster...")

heat_rows = []
for cid in sorted(clusters):
    sessions = clusters[cid]
    main_counts = Counter()
    n_msgs = 0
    for s in sessions:
        for msg in s["sequence"]:
            labels = parse_label_set(msg)
            n_msgs += 1
            mains_in_msg = set(sub_to_main(l) for l in labels)
            for m in mains_in_msg:
                main_counts[m] += 1
    row = {"cluster_id": cid, "cluster_name": CLUSTER_NAMES[cid], "n_messages": n_msgs}
    for mc in MAIN_CAT_ORDER:
        row[MAIN_CATEGORIES[mc]] = (
            main_counts.get(mc, 0) / n_msgs * 100 if n_msgs else 0
        )
    heat_rows.append(row)

heat_df = pd.DataFrame(heat_rows)
heat_df.to_csv(OUT_DIR / "category_heatmap.csv", index=False, float_format="%.2f")
print("  Saved category_heatmap.csv")


# =============================================================================
# 3. Top-5 subcategories per cluster
# =============================================================================

print("[3/5] Computing top-5 subcategories per cluster...")

top5_rows = []
for cid in sorted(clusters):
    sessions = clusters[cid]
    sub_counts = Counter()
    n_msgs = 0
    for s in sessions:
        for msg in s["sequence"]:
            labels = parse_label_set(msg)
            n_msgs += 1
            for l in labels:
                sub_counts[l] += 1
    for rank, (label, count) in enumerate(sub_counts.most_common(5), 1):
        top5_rows.append(
            {
                "cluster_id": cid,
                "cluster_name": CLUSTER_NAMES[cid],
                "rank": rank,
                "subcategory": label,
                "count": count,
                "pct_messages": count / n_msgs * 100,
            }
        )

top5_df = pd.DataFrame(top5_rows)
top5_df.to_csv(OUT_DIR / "subcategory_top5.csv", index=False, float_format="%.2f")
print("  Saved subcategory_top5.csv")


# =============================================================================
# 4. Positional patterns (first / middle / last third)
# =============================================================================

print("[4/5] Computing positional intent patterns...")

positional_rows = []
for cid in sorted(clusters):
    sessions = clusters[cid]
    third_counts = {t: Counter() for t in ["first", "middle", "last"]}
    third_totals = Counter()

    for s in sessions:
        seq = s["sequence"]
        n = len(seq)
        if n < 3:
            boundaries = [0, n, n, n]
        else:
            t1 = math.ceil(n / 3)
            t2 = math.ceil(2 * n / 3)
            boundaries = [0, t1, t2, n]

        for idx, msg in enumerate(seq):
            if idx < boundaries[1]:
                third = "first"
            elif idx < boundaries[2]:
                third = "middle"
            else:
                third = "last"

            labels = parse_label_set(msg)
            mains_in_msg = set(sub_to_main(l) for l in labels)
            third_totals[third] += 1
            for m in mains_in_msg:
                third_counts[third][m] += 1

    for third in ["first", "middle", "last"]:
        total = third_totals[third]
        for mc in MAIN_CAT_ORDER:
            positional_rows.append(
                {
                    "cluster_id": cid,
                    "cluster_name": CLUSTER_NAMES[cid],
                    "position": third,
                    "main_category": MAIN_CATEGORIES[mc],
                    "pct_messages": (
                        third_counts[third].get(mc, 0) / total * 100 if total else 0
                    ),
                }
            )

pos_df = pd.DataFrame(positional_rows)
pos_df.to_csv(OUT_DIR / "positional_patterns.csv", index=False, float_format="%.2f")
print("  Saved positional_patterns.csv")


# =============================================================================
# 5. Figures
# =============================================================================

print("[5/5] Generating figures...")

mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.size": 10,
        "axes.titlesize": 11,
        "figure.dpi": 150,
    }
)

# -- 5a. Category heatmap --
fig, ax = plt.subplots(figsize=(10, 6))
heatmap_data = heat_df.set_index("cluster_name")[MAIN_CAT_LABELS].astype(float)
heatmap_data = heatmap_data.loc[[CLUSTER_NAMES[i] for i in sorted(CLUSTER_NAMES)]]

sns.heatmap(
    heatmap_data,
    annot=True,
    fmt=".2f",
    annot_kws={"fontsize": 14},
    cmap="Reds",
    linewidths=0.5,
    linecolor="white",
    cbar=False,
    ax=ax,
)
ax.set_xlabel("")
ax.set_ylabel("")
ax.tick_params(axis="both", which="both", length=0)
ax.set_xticklabels(ax.get_xticklabels(), rotation=30, ha="right", fontsize=16)
ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=16)

for spine in ax.spines.values():
    spine.set_visible(False)

plt.tight_layout()
fig.savefig(OUT_DIR / "fig_category_heatmap.pdf", bbox_inches="tight")
plt.close(fig)
print("  Saved fig_category_heatmap.pdf")


# -- 5b. Session-length violin plot --
length_data = []
for cid in sorted(clusters):
    for s in clusters[cid]:
        length_data.append(
            {
                "cluster_name": CLUSTER_NAMES[cid],
                "cluster_id": cid,
                "session_length": len(s["sequence"]),
            }
        )
length_df = pd.DataFrame(length_data)

fig, ax = plt.subplots(figsize=(8, 4))
order = [CLUSTER_NAMES[i] for i in sorted(CLUSTER_NAMES)]
sns.violinplot(
    data=length_df,
    x="cluster_name",
    y="session_length",
    order=order,
    cut=0,
    inner="box",
    palette="Set2",
    ax=ax,
)
ax.set_xlabel("")
ax.set_ylabel("Messages per session")
ax.set_title("Session Length Distribution by Archetype")
plt.xticks(rotation=25, ha="right")
plt.tight_layout()
fig.savefig(OUT_DIR / "fig_session_length_violin.pdf", bbox_inches="tight")
plt.close(fig)
print("  Saved fig_session_length_violin.pdf")


# -- 5c. Positional patterns facet plot --
pos_plot_df = pos_df.copy()
pos_plot_df["position"] = pd.Categorical(
    pos_plot_df["position"], categories=["first", "middle", "last"], ordered=True
)

g = sns.FacetGrid(
    pos_plot_df,
    col="cluster_name",
    col_wrap=3,
    col_order=[CLUSTER_NAMES[i] for i in sorted(CLUSTER_NAMES)],
    height=3,
    aspect=1.1,
    sharey=True,
)
g.map_dataframe(
    sns.barplot,
    x="position",
    y="pct_messages",
    hue="main_category",
    hue_order=MAIN_CAT_LABELS,
    palette="tab10",
    dodge=True,
)
g.set_axis_labels("Session position", "% of messages")
g.set_titles("{col_name}")
g.add_legend(title="Category", bbox_to_anchor=(1.02, 0.5), loc="center left")
plt.tight_layout()
g.savefig(OUT_DIR / "fig_positional_patterns.pdf", bbox_inches="tight")
plt.close()
print("  Saved fig_positional_patterns.pdf")


# =============================================================================
# Done
# =============================================================================

print("\n" + "=" * 60)
print("All outputs saved to:", OUT_DIR.resolve())
print("=" * 60)

print("\n── Cluster Overview ──")
for _, row in overview_df.iterrows():
    print(
        f"  C{int(row['cluster_id'])} {row['cluster_name']:40s}  "
        f"n={int(row['n_sessions']):>4d} ({row['pct_sessions']:>5.1f}%)  "
        f"median_len={row['len_median']:>4.0f}  "
        f"mean_len={row['len_mean']:>5.1f}  "
        f"multi={row['multi_label_rate']:>5.1f}%"
    )
