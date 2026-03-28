# `repo_characteristics.csv` — File Spec

## Overview
One row per repository. Aggregated from five data sources: GitHub API metadata
(`repositories.json`), commit history (`commits_history/*.json`), language
distribution (`languages.json`), file tree snapshots (`file_trees/*.json`),
and README files (`readmes/*.md`).

## Columns

### Identity
| Column | Type | Description |
|---|---|---|
| `repo_id` | int | GitHub numeric repository ID |
| `full_name` | str | `owner/repo` |

### GitHub Metadata
| Column | Type | Description |
|---|---|---|
| `stars` | int | `stargazers_count` from GitHub API |
| `forks` | int | Fork count |
| `watchers_count` | int | Watcher count |
| `open_issues_count` | int | Open issues + PRs |
| `size` | int | GitHub-reported repo size (KB) |
| `created_at` | datetime (UTC) | Repo creation time |
| `pushed_at` | datetime (UTC) | Last push time |
| `repo_age_days` | int | `pushed_at - created_at` in days, clipped ≥ 0 |
| `language` | str | Primary language reported by GitHub (nullable) |
| `has_wiki` | bool | |
| `has_discussions` | bool | |
| `has_issues` | bool | |
| `has_projects` | bool | |
| `has_license` | bool | True if `license.spdx_id` or `license.name` is non-null |
| `license_type` | str | SPDX ID if available, else license name; `"NO_LICENSE"` if absent |
| `fork` | bool | Whether this repo is a fork |
| `archived` | bool | |
| `has_topics` | bool | `topics_count > 0` |
| `topics_count` | int | Number of GitHub topics |
| `has_description` | bool | True if description is non-empty |

### Commit Activity
Derived from `commits_history/<repo_id>.json` (GitHub commits API payload).

| Column | Type | Description |
|---|---|---|
| `total_commits` | int | Total commits in the API payload |
| `active_days` | int | Number of distinct calendar days with at least one commit |
| `first_commit_at` | datetime (UTC) | Earliest commit author date |
| `last_commit_at` | datetime (UTC) | Latest commit author date |
| `commit_span_days` | float | `last_commit_at - first_commit_at` in days |

### Language Distribution
Derived from `languages.json` (GitHub languages API — byte counts per language).

| Column | Type | Description |
|---|---|---|
| `num_languages` | int | Number of languages with byte count > 0 |
| `primary_language_ratio` | float | Bytes of dominant language / total bytes |
| `language_entropy` | float | Shannon entropy over language byte counts (nats); higher = more polyglot |

### File Tree Structure
Derived from `file_trees/<repo_id>.json` (flat list of all file paths).

| Column | Type | Description |
|---|---|---|
| `total_files` | int | Number of file paths (non-directory nodes) |
| `total_dirs` | int | Number of implied directory nodes |
| `max_depth` | int | Maximum path depth (number of `/`-separated components) |
| `avg_files_per_dir` | float | `total_files / total_dirs` |
| `has_readme` | bool | True if `readmes/<repo_id>.md` exists and is non-empty |
| `has_tests` | bool | True if any path matches `test/`, `tests/`, `spec/`, `*.test.*`, or `*.spec.*` |
| `has_ci` | bool | True if any path starts with `.github/workflows/` or matches known CI config filenames (`.travis.yml`, `.gitlab-ci.yml`, etc.) |
| `has_dockerfile` | bool | True if any file is named `dockerfile*` (case-insensitive) |
| `has_config_files` | bool | True if any path starts with `config/` or matches common config filenames (`package.json`, `pyproject.toml`, `requirements.txt`, etc.) |
| `doc_files_count` | int | Number of `.md` files in the file tree |
| `doc_files` | list of str | List of `.md` file paths in the file tree |

### README & Contributors
| Column | Type | Description |
|---|---|---|
| `readme_char_count` | int | Character count of `readmes/<repo_id>.md`; 0 if absent |
| `contributors_count` | int | Length of the GitHub contributors API response list |