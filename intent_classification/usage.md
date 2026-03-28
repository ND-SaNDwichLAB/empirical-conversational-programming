# Intent Classification Pipeline

All commands are run from `intent_classification/`.

## File Layout

```
intent_classification/
  categories.py                  # shared VALID_CATEGORIES / VALID_LABELS
  codebook.txt                   # system prompt for the model
  classification_batch.py        # batch API workflow
  classification_batch_ops.sh    # shell wrapper for batch operations
  classification_failed.py       # retry failed/invalid rows in real-time

data/classifications/
  all_user_messages_cleaned.csv  # input (produced by pipeline.ipynb)
  batch_inputs/                  # JSONL files fed to the batch API
  batch_ids/                     # one .txt per submitted batch
  raw_output/                    # raw JSONL returned by the batch API
  parsed/                        # parsed classifications per batch
  submission_logs/               # optional logs for submit commands
  status_logs/                   # optional logs for status commands
  download_logs/                 # optional logs for download commands
  all_classifications.jsonl      # merged across all batches (pipeline.ipynb)
  fail/
    failed_indexes.json              # indexes to retry (pipeline.ipynb)
    classifications_failed_retry.jsonl
    failed_indexes_after_retry.json
  classifications_with_messages.csv  # final output (pipeline.ipynb)
  classifications_for_analysis.csv   # analysis-ready output (distribution.ipynb)
```

## Step-by-step

### Command Pattern (General)

`classification_batch_ops.sh` supports three range styles for `submit | status | download`:

- no batch args: auto-detect range from available files
- one batch arg (`N`): run only batch `N`
- two batch args (`A B`): run inclusive range `A..B`

Examples:

```bash
./classification_batch_ops.sh submit
./classification_batch_ops.sh submit 3
./classification_batch_ops.sh submit 1 100
```

### 1. Prepare input (run once in pipeline.ipynb)

Run cells 1–4 to produce `all_user_messages_cleaned.csv`.

### 2. Prepare batch input files

```bash
python classification_batch.py prepare [limit] [chunk_size]
# default chunk_size = 100; omit limit to process all rows
```

### 3. Submit batches

```bash
./classification_batch_ops.sh submit
./classification_batch_ops.sh submit N
./classification_batch_ops.sh submit A B
```

Save submission logs:

```bash
mkdir -p ../data/classifications/submission_logs
nohup ./classification_batch_ops.sh submit 1 100 \
  > ../data/classifications/submission_logs/submit_1_100.log 2>&1 &
```

### 4. Check status

```bash
./classification_batch_ops.sh status
./classification_batch_ops.sh status N
./classification_batch_ops.sh status A B
```

Save status logs:

```bash
mkdir -p ../data/classifications/status_logs
nohup ./classification_batch_ops.sh status 1 100 \
  > ../data/classifications/status_logs/status_1_100.log 2>&1 &
```

### 5. Download & parse

```bash
./classification_batch_ops.sh download
./classification_batch_ops.sh download N
./classification_batch_ops.sh download A B
```

Save download logs:

```bash
mkdir -p ../data/classifications/download_logs
nohup ./classification_batch_ops.sh download 1 100 \
  > ../data/classifications/download_logs/download_1_100.log 2>&1 &
```

Parsed results land in `../data/classifications/parsed/`.

### 6. Merge classifications

Run the merge cell in `pipeline.ipynb` to generate
`../data/classifications/all_classifications.jsonl`.

### 7. Identify failures (pipeline.ipynb)

Run the failure-detection cell to save `../data/classifications/fail/failed_indexes.json`.

### 8. Retry failures

```bash
python classification_failed.py
```

Results: `fail/classifications_failed_retry.jsonl`  
Unresolved: `fail/failed_indexes_after_retry.json`

### 9. Finalize (pipeline.ipynb)

Run the remaining cells to merge retried results and produce
`classifications_with_messages.csv`.

### 10. Distribution analysis

Run `distribution.ipynb` to compute summary stats and export:
`../data/classifications/classifications_for_analysis.csv`.

---

## Other batch commands

| Command | Purpose |
|---------|---------|
| `./classification_batch_ops.sh errors [n]` | Print error file IDs and first 3 error lines |
| `./classification_batch_ops.sh peek [n]` | Pretty-print first result of a completed batch |
