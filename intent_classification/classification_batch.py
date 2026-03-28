import json
from openai import OpenAI
from pathlib import Path
import pandas as pd
from categories import VALID_LABELS


CODEBOOK = open("codebook.txt").read()
client = OpenAI()

CLASSIFICATION_DIR = Path("../data/classifications")
BATCH_INPUT_DIR = CLASSIFICATION_DIR / "batch_inputs"
RAW_OUTPUT_DIR = CLASSIFICATION_DIR / "raw_output"
BATCH_ID_DIR = CLASSIFICATION_DIR / "batch_ids"
PARSED_OUTPUT_DIR = CLASSIFICATION_DIR / "parsed"

RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "classification",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "labels": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "reasoning": {"type": "string"},
                            "main_category": {"type": "string"},
                            "sub_category": {"type": "string"},
                        },
                        "required": ["reasoning", "main_category", "sub_category"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["labels"],
            "additionalProperties": False,
        },
    },
}


def build_user_prompt(row):
    context = str(row.get("context", "")) if not pd.isna(row.get("context", "")) else ""
    current = str(row.get("truncated_content", ""))
    parts = []
    if context:
        parts.append(context)
    parts.append(f"[current]: {current}")
    return "\n".join(parts)


def ensure_classification_dirs():
    BATCH_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    BATCH_ID_DIR.mkdir(parents=True, exist_ok=True)
    PARSED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def normalize_batch_no(batch_no: int | str) -> int:
    batch_no_int = int(batch_no)
    if batch_no_int < 1:
        raise ValueError("batch_no must be >= 1")
    return batch_no_int


def get_batch_tag(batch_no: int | str) -> str:
    return f"{normalize_batch_no(batch_no):04d}"


def get_batch_input_path(batch_no: int | str) -> Path:
    return BATCH_INPUT_DIR / f"batch_input_{get_batch_tag(batch_no)}.jsonl"


def get_batch_id_path(batch_no: int | str) -> Path:
    return BATCH_ID_DIR / f"batch_id_{get_batch_tag(batch_no)}.txt"


def get_parsed_output_path(batch_no: int | str) -> Path:
    return PARSED_OUTPUT_DIR / f"classifications_{get_batch_tag(batch_no)}.jsonl"


# ── Step 1: Prepare batch input file ────────────────────────────────────────
def prepare_batch_file(
    df,
    batch_input_dir: str | Path = BATCH_INPUT_DIR,
    chunk_size: int = 10000,
    limit: int = None,
):
    ensure_classification_dirs()
    if limit:
        df = df.head(limit)
    output_dir = Path(batch_input_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    total_rows = len(df)
    if total_rows == 0:
        print("No rows found. No batch input files were generated.")
        return []

    written_files = []
    total_batches = (total_rows + chunk_size - 1) // chunk_size

    for batch_index, start in enumerate(range(0, total_rows, chunk_size), start=1):
        end = min(start + chunk_size, total_rows)
        chunk_df = df.iloc[start:end]
        output = output_dir / f"batch_input_{batch_index:04d}.jsonl"

        with open(output, "w", encoding="utf-8") as f:
            for offset, (_, row) in enumerate(chunk_df.iterrows()):
                global_idx = start + offset
                request = {
                    "custom_id": str(global_idx),
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": "gpt-5-mini",
                        "messages": [
                            {"role": "system", "content": CODEBOOK},
                            {"role": "user", "content": build_user_prompt(row)},
                        ],
                        "response_format": RESPONSE_SCHEMA,
                        "max_completion_tokens": 4096,
                    },
                }
                f.write(json.dumps(request, ensure_ascii=False) + "\n")

        written_files.append(output)
        print(
            f"Batch input written: {output} "
            f"({end - start} requests, ids {start}..{end - 1})"
        )

    print(f"Prepared {len(written_files)} batch file(s) for {total_rows} rows.")
    print(f"Chunk size: {chunk_size} | Total batches: {total_batches}")
    return written_files


# ── Step 2: Submit batch ─────────────────────────────────────────────────────
def submit_batch(
    batch_input_path: str,
    batch_id_path: str | Path,
):
    ensure_classification_dirs()
    with open(batch_input_path, "rb") as f:
        uploaded = client.files.create(file=f, purpose="batch")

    batch = client.batches.create(
        input_file_id=uploaded.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={"description": "conversational programming message classification"},
    )

    with open(batch_id_path, "w") as f:
        f.write(batch.id)

    print(f"Batch submitted: {batch.id}")
    print(f"Status: {batch.status}")
    return batch.id


# ── Step 3: Check status ─────────────────────────────────────────────────────
def check_status(batch_id_path: str | Path):
    batch_id = open(batch_id_path).read().strip()
    batch = client.batches.retrieve(batch_id)
    print(f"Batch ID: {batch.id}")
    print(f"Status:   {batch.status}")
    print(f"Progress: {batch.request_counts.completed} / {batch.request_counts.total}")
    if batch.status == "completed":
        print(f"Output file ID: {batch.output_file_id}")
    return batch


# ── Step 4a: Download raw batch output ──────────────────────────────────────
def download_raw(
    raw_dir: str | Path = RAW_OUTPUT_DIR,
    batch_id_path: str | Path = None,
):
    ensure_classification_dirs()
    if not batch_id_path:
        raise ValueError("batch_id_path is required")
    batch_id = open(batch_id_path).read().strip()
    batch = client.batches.retrieve(batch_id)

    if batch.status != "completed":
        print(f"Batch not ready yet. Status: {batch.status}")
        return

    Path(raw_dir).mkdir(parents=True, exist_ok=True)
    raw_path = Path(raw_dir) / f"{batch_id}.jsonl"

    content = client.files.content(batch.output_file_id).text
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(content)

    line_count = len(content.strip().split("\n"))
    print(f"Raw output saved: {raw_path} ({line_count} lines)")
    return raw_path


# ── Step 4b: Parse raw output into classifications ───────────────────────────
def parse_results(raw_path: str, output_path: str):
    results = []
    invalid_count = 0
    failure_count = 0

    with open(raw_path, "r", encoding="utf-8") as f:
        lines = f.read().strip().split("\n")

    for line in lines:
        record = json.loads(line)
        idx = int(record["custom_id"])

        if record.get("error"):
            results.append(
                {
                    "index": idx,
                    "status": f"failure: {record['error']}",
                    "labels": [],
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "cached_tokens": 0,
                }
            )
            failure_count += 1
            continue

        body = record["response"]["body"]
        usage = body["usage"]
        content_str = body["choices"][0]["message"]["content"]

        if not content_str:
            results.append(
                {
                    "index": idx,
                    "status": "failure: empty content",
                    "labels": [],
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "cached_tokens": usage.get("prompt_tokens_details", {}).get(
                        "cached_tokens", 0
                    ),
                }
            )
            failure_count += 1
            continue

        parsed = json.loads(content_str)
        labels = parsed.get("labels", [])
        if not labels:
            results.append(
                {
                    "index": idx,
                    "status": "failure: empty labels",
                    "labels": [],
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "cached_tokens": usage.get("prompt_tokens_details", {}).get(
                        "cached_tokens", 0
                    ),
                }
            )
            failure_count += 1
            continue

        all_valid = all(
            (lbl.get("main_category", ""), lbl.get("sub_category", "")) in VALID_LABELS
            for lbl in labels
        )
        if not all_valid:
            invalid_count += 1

        results.append(
            {
                "index": idx,
                "status": "success" if all_valid else "invalid_category",
                "labels": labels,
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "cached_tokens": usage.get("prompt_tokens_details", {}).get(
                    "cached_tokens", 0
                ),
            }
        )

    results.sort(key=lambda x: x["index"])

    with open(output_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    total_prompt = sum(r["prompt_tokens"] for r in results)
    total_completion = sum(r["completion_tokens"] for r in results)
    total_cached = sum(r["cached_tokens"] for r in results)

    print(f"\n── Results Summary ─────────────────────────")
    print(f"  Total:            {len(results)}")
    print(f"  Success:          {len(results) - failure_count - invalid_count}")
    print(f"  Invalid category: {invalid_count}")
    print(f"  Failures:         {failure_count}")
    print(f"  Prompt tokens:    {total_prompt:,}")
    print(f"  Cached tokens:    {total_cached:,}")
    print(f"  Completion tokens:{total_completion:,}")
    print(f"────────────────────────────────────────────")
    print(f"Classifications saved to {output_path}")


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    df = pd.read_csv("../data/classifications/all_user_messages_cleaned.csv")

    cmd = sys.argv[1] if len(sys.argv) > 1 else "prepare"

    if cmd == "prepare":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        chunk_size = int(sys.argv[3]) if len(sys.argv) > 3 else 100
        prepare_batch_file(
            df,
            batch_input_dir=BATCH_INPUT_DIR,
            chunk_size=chunk_size,
            limit=limit,
        )
    elif cmd == "submit":
        batch_no = normalize_batch_no(sys.argv[2] if len(sys.argv) > 2 else 1)
        batch_input_path = get_batch_input_path(batch_no)
        batch_id_path = get_batch_id_path(batch_no)
        submit_batch(str(batch_input_path), batch_id_path=batch_id_path)
    elif cmd == "status":
        batch_no = normalize_batch_no(sys.argv[2] if len(sys.argv) > 2 else 1)
        check_status(batch_id_path=get_batch_id_path(batch_no))
    elif cmd == "download":
        batch_no = normalize_batch_no(sys.argv[2] if len(sys.argv) > 2 else 1)
        raw_path = download_raw(batch_id_path=get_batch_id_path(batch_no))
        if raw_path:
            parse_results(str(raw_path), str(get_parsed_output_path(batch_no)))
    elif cmd == "errors":
        batch_no = normalize_batch_no(sys.argv[2] if len(sys.argv) > 2 else 1)
        batch_id = open(get_batch_id_path(batch_no)).read().strip()
        batch = client.batches.retrieve(batch_id)
        print(f"Output file ID: {batch.output_file_id}")
        print(f"Error file ID:  {batch.error_file_id}")
        if batch.error_file_id:
            content = client.files.content(batch.error_file_id).text
            for line in content.strip().split("\n")[:3]:
                print(json.dumps(json.loads(line), indent=2, ensure_ascii=False))
    elif cmd == "peek":
        batch_no = normalize_batch_no(sys.argv[2] if len(sys.argv) > 2 else 1)
        batch_id = open(get_batch_id_path(batch_no)).read().strip()
        batch = client.batches.retrieve(batch_id)
        content = client.files.content(batch.output_file_id).text
        first_line = content.strip().split("\n")[0]
        print(json.dumps(json.loads(first_line), indent=2, ensure_ascii=False))
    else:
        print(
            "Usage: python classification_batch.py "
            "[prepare [limit] [chunk_size]|submit [batch_no]|status [batch_no]|download [batch_no]|errors [batch_no]|peek [batch_no]]"
        )
