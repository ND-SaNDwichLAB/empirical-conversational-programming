# `data/classifications_for_analysis.csv` — File Spec

## Overview
Label-level classification data for conversational programming sessions. Each row represents
one (message, label) pair. Multi-label messages produce multiple rows.

## Granularity
- **Unit of analysis:** one label assigned to one message
- **Message:** identified by `(sha, index_in_chat)`
- **Session:** identified by `sha`
- **Repository:** identified by `repository_full_name`

## Columns

| Column | Type | Description |
|---|---|---|
| `repository_full_name` | str | GitHub repo identifier, e.g. `owner/repo` |
| `sha` | str | Session ID (unique per Cursor/Copilot chat session) |
| `timestamp` | datetime (UTC) | Session-level timestamp — **all messages in a session share the same value**. Use for chronological ordering of sessions within a repo (cross-session analysis). |
| `title` | str | Auto-generated session title |
| `index_in_chat` | int | 0-based message position within session |
| `index_in_chat_original` | int | Original 0-based message position within session (before filtering out `"8.1 Others"` messages) |
| `truncated_content` | str | Truncated user message text (used for classification context) |
| `labels` | str (JSON) | Raw LLM output — list of label objects with `reasoning`, `main_category`, `sub_category` |
| `content` | str | Full user message text |
| `label_rank` | int | 1-based rank of this label within the message (1 = dominant label) |
| `reasoning` | str | Flattened: LLM reasoning for this specific label |
| `main_category` | str | Flattened: e.g. `"2. Failure Reporting"` |
| `sub_category` | str | Flattened: e.g. `"2.2 Symptom Description"` |

## Key Properties
- **Multi-label:** a message with N labels appears as N rows with `label_rank` 1..N
- **Single-label message:** exactly one row with `label_rank = 1`
- **Message-level weight:** when aggregating, use `label_weight = 1 / count(rows per (sha, index_in_chat))` to avoid over-counting multi-label messages
- **Session ordering:** sort by `(repository_full_name, timestamp, sha)` for cross-session analysis; sort by `(sha, index_in_chat)` for within-session analysis
- **`labels` column** is the raw JSON list; `reasoning`, `main_category`, `sub_category` are the flattened scalar fields derived from it
- **Pre-cleaned:** `"8. Others"` / `"8.1 Others"` rows are already excluded; no missing values or invalid categories

## Taxonomy
See `intent_classification/categories.py` for the full list of valid `(main_category, sub_category)` pairs.