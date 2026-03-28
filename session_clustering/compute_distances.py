"""
Compute pairwise session edit distances for downstream clustering.

Each session (identified by `sha`) is represented as a sequence of label sets,
where each position corresponds to a user message and its associated
sub_category labels (a message may have multiple labels).

The distance metric is a custom weighted Levenshtein edit distance:
  - Indel cost: configurable (default 1.0)
  - Substitution cost between two label sets: mean pairwise label cost
  - Label-level cost:
      * same sub_category  -> 0
      * same main_category -> same_parent_weight  (default 0.5)
      * different main     -> cross_parent_weight (default 1.0)

Optionally normalized by max(len(s1), len(s2)).

Uses ProcessPoolExecutor for parallel computation and deduplicates identical
sequences to avoid redundant work.
"""

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
from tqdm import tqdm


# ---------------------------------------------------------------------------
# Cost helpers
# ---------------------------------------------------------------------------


def label_cost(label_a, label_b, same_parent_weight, cross_parent_weight):
    """Cost of substituting one individual label for another.

    Each label is a tuple (main_category, sub_category).
    """
    if label_a[1] == label_b[1]:
        return 0.0
    if label_a[0] == label_b[0]:
        return same_parent_weight
    return cross_parent_weight


def substitution_cost(set_a, set_b, same_parent_weight, cross_parent_weight):
    """Mean pairwise label cost between two label sets (frozensets of tuples)."""
    if set_a == set_b:
        return 0.0
    total = 0.0
    for la in set_a:
        for lb in set_b:
            total += label_cost(la, lb, same_parent_weight, cross_parent_weight)
    return total / (len(set_a) * len(set_b))


# ---------------------------------------------------------------------------
# Edit distance
# ---------------------------------------------------------------------------


def weighted_levenshtein(
    seq_a, seq_b, indel_weight, same_parent_weight, cross_parent_weight
):
    """Weighted Levenshtein distance between two label-set sequences.

    Parameters
    ----------
    seq_a, seq_b : list[frozenset[tuple[str, str]]]
        Each element is a frozenset of (main_category, sub_category) tuples.
    """
    n, m = len(seq_a), len(seq_b)
    # Use two-row DP to save memory
    prev = [j * indel_weight for j in range(m + 1)]
    curr = [0.0] * (m + 1)
    for i in range(1, n + 1):
        curr[0] = i * indel_weight
        for j in range(1, m + 1):
            sub = prev[j - 1] + substitution_cost(
                seq_a[i - 1], seq_b[j - 1], same_parent_weight, cross_parent_weight
            )
            ins = curr[j - 1] + indel_weight
            delete = prev[j] + indel_weight
            curr[j] = min(sub, ins, delete)
        prev, curr = curr, prev
    return prev[m]


def compute_distance(
    seq_a, seq_b, indel_weight, same_parent_weight, cross_parent_weight, normalize
):
    """Compute (optionally normalized) edit distance between two sequences."""
    raw = weighted_levenshtein(
        seq_a, seq_b, indel_weight, same_parent_weight, cross_parent_weight
    )
    if normalize:
        denom = max(len(seq_a), len(seq_b))
        return raw / denom if denom > 0 else 0.0
    return raw


# ---------------------------------------------------------------------------
# Process pool workers
# ---------------------------------------------------------------------------

# Module-level globals set by each worker via initializer
_WORKER_SEQUENCES: Optional[List[tuple]] = None
_WORKER_INDEL_WEIGHT: float = 1.0
_WORKER_SAME_PARENT_WEIGHT: float = 0.5
_WORKER_CROSS_PARENT_WEIGHT: float = 1.0
_WORKER_NORMALIZE: bool = True


def _init_worker(
    sequences, indel_weight, same_parent_weight, cross_parent_weight, normalize
):
    """Initializer for each worker process — avoids re-pickling data per task."""
    global _WORKER_SEQUENCES, _WORKER_INDEL_WEIGHT
    global _WORKER_SAME_PARENT_WEIGHT, _WORKER_CROSS_PARENT_WEIGHT, _WORKER_NORMALIZE
    _WORKER_SEQUENCES = sequences
    _WORKER_INDEL_WEIGHT = indel_weight
    _WORKER_SAME_PARENT_WEIGHT = same_parent_weight
    _WORKER_CROSS_PARENT_WEIGHT = cross_parent_weight
    _WORKER_NORMALIZE = normalize


def _process_block(task: Tuple[int, int]) -> Tuple[int, np.ndarray]:
    """Compute distances for all pairs (i, j) where i in [i_start, i_end) and j > i."""
    i_start, i_end = task
    seqs = _WORKER_SEQUENCES
    n = len(seqs)

    block_pairs = sum(n - i - 1 for i in range(i_start, i_end))
    distances = np.empty(block_pairs, dtype=np.float64)

    ptr = 0
    for i in range(i_start, i_end):
        for j in range(i + 1, n):
            distances[ptr] = compute_distance(
                seqs[i],
                seqs[j],
                _WORKER_INDEL_WEIGHT,
                _WORKER_SAME_PARENT_WEIGHT,
                _WORKER_CROSS_PARENT_WEIGHT,
                _WORKER_NORMALIZE,
            )
            ptr += 1

    return i_start, distances


# ---------------------------------------------------------------------------
# Data loading & sequence construction
# ---------------------------------------------------------------------------


def build_sequences(df):
    """Build session sequences from the classifications dataframe.

    Returns
    -------
    sha_to_seq : dict[str, tuple[frozenset]]
        Mapping from sha to its label-set sequence.
    """
    # Collect label sets per (sha, index_in_chat)
    label_sets = (
        df.groupby(["sha", "index_in_chat"])
        .apply(
            lambda g: frozenset(zip(g["main_category"], g["sub_category"])),
            include_groups=False,
        )
        .reset_index(name="label_set")
    )

    # Build ordered sequence per sha
    sha_to_seq = (
        label_sets.sort_values(["sha", "index_in_chat"])
        .groupby("sha")["label_set"]
        .apply(tuple)
        .to_dict()
    )
    return sha_to_seq


def deduplicate_sequences(sha_to_seq):
    """Map each sha to a unique sequence index.

    Returns
    -------
    unique_sequences : list[tuple[frozenset]]
        Deduplicated list of sequences.
    sha_to_idx : dict[str, int]
        Mapping from sha to index in unique_sequences.
    """
    seq_to_idx = {}
    unique_sequences = []
    sha_to_idx = {}

    for sha, seq in sha_to_seq.items():
        if seq not in seq_to_idx:
            seq_to_idx[seq] = len(unique_sequences)
            unique_sequences.append(seq)
        sha_to_idx[sha] = seq_to_idx[seq]

    return unique_sequences, sha_to_idx


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Compute pairwise session edit distances for clustering."
    )
    parser.add_argument(
        "--input",
        type=str,
        default="../data/classifications/classifications_for_analysis.csv",
        help="Path to classifications_for_analysis.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="../data/clusters/distances",
        help="Directory to save distance matrix and mappings",
    )
    parser.add_argument(
        "--indel-weight",
        type=float,
        default=1.0,
        help="Cost of insertion / deletion (default: 1.0)",
    )
    parser.add_argument(
        "--same-parent-weight",
        type=float,
        default=0.5,
        help="Substitution cost when main_category matches (default: 0.5)",
    )
    parser.add_argument(
        "--cross-parent-weight",
        type=float,
        default=1.0,
        help="Substitution cost when main_category differs (default: 1.0)",
    )
    parser.add_argument(
        "--normalize",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Normalize distance by max(len(s1), len(s2)) (default: True)",
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=0,
        help="Number of worker processes (default: 0 = cpu_count - 1)",
    )
    parser.add_argument(
        "--block-size",
        type=int,
        default=8,
        help="Number of i-rows per process block (default: 8)",
    )
    args = parser.parse_args()

    # Resolve paths relative to this script
    script_dir = Path(__file__).resolve().parent
    input_path = (
        Path(args.input) if Path(args.input).is_absolute() else script_dir / args.input
    )
    output_dir = (
        Path(args.output_dir)
        if Path(args.output_dir).is_absolute()
        else script_dir / args.output_dir
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Load data
    # ------------------------------------------------------------------
    print(f"Loading data from {input_path} ...")
    df = pd.read_csv(
        input_path,
        usecols=["sha", "index_in_chat", "main_category", "sub_category"],
    )
    print(f"  Rows: {len(df):,}")

    # ------------------------------------------------------------------
    # 2. Build sequences & deduplicate
    # ------------------------------------------------------------------
    print("Building session sequences ...")
    sha_to_seq = build_sequences(df)
    n_sessions = len(sha_to_seq)
    print(f"  Total sessions: {n_sessions:,}")

    unique_sequences, sha_to_idx = deduplicate_sequences(sha_to_seq)
    n_unique = len(unique_sequences)
    print(
        f"  Unique sequences: {n_unique:,}  (dedup ratio {n_unique / n_sessions:.2%})"
    )

    # ------------------------------------------------------------------
    # 3. Compute pairwise distances (parallel)
    # ------------------------------------------------------------------
    n_pairs = n_unique * (n_unique - 1) // 2
    num_workers = (
        args.num_workers if args.num_workers > 0 else max(1, (os.cpu_count() or 2) - 1)
    )
    block_size = max(1, args.block_size)
    print(f"Computing {n_pairs:,} pairwise distances with {num_workers} workers ...")

    # Build block tasks: each task is a range of i-rows
    tasks = [
        (i_start, min(i_start + block_size, n_unique - 1))
        for i_start in range(0, n_unique - 1, block_size)
    ]

    dist_matrix = np.zeros((n_unique, n_unique), dtype=np.float64)

    t0 = time.time()
    with ProcessPoolExecutor(
        max_workers=num_workers,
        initializer=_init_worker,
        initargs=(
            unique_sequences,
            args.indel_weight,
            args.same_parent_weight,
            args.cross_parent_weight,
            args.normalize,
        ),
    ) as executor:
        for i_start, block_dists in tqdm(
            executor.map(_process_block, tasks),
            total=len(tasks),
            desc=f"Distance blocks (x{num_workers} workers)",
        ):
            i_end = min(i_start + block_size, n_unique - 1)
            ptr = 0
            for i in range(i_start, i_end):
                for j in range(i + 1, n_unique):
                    dist_matrix[i, j] = block_dists[ptr]
                    dist_matrix[j, i] = block_dists[ptr]
                    ptr += 1

    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.1f}s")

    # ------------------------------------------------------------------
    # 4. Save outputs
    # ------------------------------------------------------------------
    dist_path = output_dir / "distance_matrix.npy"
    mapping_path = output_dir / "sha_to_sequence_idx.json"
    meta_path = output_dir / "metadata.json"

    np.save(dist_path, dist_matrix)
    print(f"  Saved distance matrix ({n_unique}x{n_unique}) -> {dist_path}")

    with open(mapping_path, "w") as f:
        json.dump(sha_to_idx, f, indent=2)
    print(f"  Saved sha -> sequence index mapping -> {mapping_path}")

    metadata = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "input_file": str(input_path),
        "n_sessions": n_sessions,
        "n_unique_sequences": n_unique,
        "n_pairs_computed": n_pairs,
        "compute_time_seconds": round(elapsed, 2),
        "parameters": {
            "indel_weight": args.indel_weight,
            "same_parent_weight": args.same_parent_weight,
            "cross_parent_weight": args.cross_parent_weight,
            "normalize": args.normalize,
        },
    }
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"  Saved metadata -> {meta_path}")

    print("All done.")


if __name__ == "__main__":
    main()
