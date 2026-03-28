import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import pandas as pd
from openai import OpenAI
from categories import VALID_LABELS


CODEBOOK = open("codebook.txt").read()
client = OpenAI()

CLASSIFICATION_DIR = Path("../data/classifications")
FAIL_DIR = CLASSIFICATION_DIR / "fail"
FAILED_INDEXES_PATH = FAIL_DIR / "failed_indexes.json"
OUTPUT_PATH = FAIL_DIR / "classifications_failed_retry.jsonl"
UNRESOLVED_PATH = FAIL_DIR / "failed_indexes_after_retry.json"

MODEL = "gpt-5-mini"
BATCH_SIZE = 16
MAX_ATTEMPTS = 3
REQUEST_TIMEOUT = 180
MAX_CONCURRENCY = 8

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


def ensure_dirs():
    FAIL_DIR.mkdir(parents=True, exist_ok=True)


def chunked(items, chunk_size):
    for i in range(0, len(items), chunk_size):
        yield items[i : i + chunk_size]


def get_cached_tokens(usage):
    if usage is None:
        return 0
    details = getattr(usage, "prompt_tokens_details", None)
    if details is None:
        return 0
    if isinstance(details, dict):
        return details.get("cached_tokens", 0) or 0
    return getattr(details, "cached_tokens", 0) or 0


def classify_one(
    index: int,
    row: pd.Series,
    attempt: int,
    batch_no: int,
    batch_total: int,
    item_pos: int,
    item_total: int,
) -> dict:
    prompt = build_user_prompt(row)
    print(
        f"    [attempt {attempt}] [batch {batch_no}/{batch_total}] "
        f"[{item_pos}/{item_total}] idx={index} -> sending request",
        flush=True,
    )
    started_at = time.time()

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": CODEBOOK},
                {"role": "user", "content": prompt},
            ],
            response_format=RESPONSE_SCHEMA,
            max_completion_tokens=4096,
            timeout=REQUEST_TIMEOUT,
        )
    except Exception as e:
        elapsed = time.time() - started_at
        print(
            f"    [attempt {attempt}] idx={index} request failed in {elapsed:.1f}s: {e}",
            flush=True,
        )
        return {
            "index": index,
            "status": f"failure: request_error: {str(e)}",
            "labels": [],
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cached_tokens": 0,
        }

    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    cached_tokens = get_cached_tokens(usage)
    elapsed = time.time() - started_at
    print(
        f"    [attempt {attempt}] idx={index} response in {elapsed:.1f}s "
        f"(prompt={prompt_tokens}, completion={completion_tokens}, cached={cached_tokens})",
        flush=True,
    )

    content = ""
    try:
        content = response.choices[0].message.content or ""
    except Exception:
        content = ""

    if not content:
        print(f"    [attempt {attempt}] idx={index} failure: empty content", flush=True)
        return {
            "index": index,
            "status": "failure: empty content",
            "labels": [],
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cached_tokens": cached_tokens,
        }

    try:
        parsed = json.loads(content)
    except Exception as e:
        print(f"    [attempt {attempt}] idx={index} failure: invalid json", flush=True)
        return {
            "index": index,
            "status": f"failure: invalid json: {str(e)}",
            "labels": [],
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cached_tokens": cached_tokens,
        }

    labels = parsed.get("labels", [])
    if not labels:
        print(f"    [attempt {attempt}] idx={index} failure: empty labels", flush=True)
        return {
            "index": index,
            "status": "failure: empty labels",
            "labels": [],
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cached_tokens": cached_tokens,
        }

    all_valid = all(
        (lbl.get("main_category", ""), lbl.get("sub_category", "")) in VALID_LABELS
        for lbl in labels
    )
    label_summary = ", ".join(
        f"{lbl.get('main_category','')} / {lbl.get('sub_category','')}"
        for lbl in labels
    )
    print(
        f"    [attempt {attempt}] idx={index} done: {'success' if all_valid else 'invalid_category'} "
        f"({label_summary})",
        flush=True,
    )

    return {
        "index": index,
        "status": "success" if all_valid else "invalid_category",
        "labels": labels,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cached_tokens": cached_tokens,
    }


def main():
    ensure_dirs()
    df = pd.read_csv("../data/classifications/all_user_messages_cleaned.csv")

    if not FAILED_INDEXES_PATH.exists():
        raise FileNotFoundError(f"Missing file: {FAILED_INDEXES_PATH}")

    failed_indexes = json.loads(FAILED_INDEXES_PATH.read_text())
    failed_indexes = sorted({int(i) for i in failed_indexes})

    if not failed_indexes:
        print("No failed indexes found. Nothing to do.")
        return

    max_idx = len(df) - 1
    valid_indexes = [i for i in failed_indexes if 0 <= i <= max_idx]
    invalid_indexes = [i for i in failed_indexes if i < 0 or i > max_idx]

    if invalid_indexes:
        print(f"Skipped out-of-range indexes: {len(invalid_indexes)}")

    attempt_count = {i: 0 for i in valid_indexes}
    pending = set(valid_indexes)
    latest_results = {}

    for attempt in range(1, MAX_ATTEMPTS + 1):
        if not pending:
            break

        current = sorted(pending)
        print(f"\nAttempt {attempt}/{MAX_ATTEMPTS} | pending: {len(current)}")

        batches = list(chunked(current, BATCH_SIZE))
        for batch_idx, batch in enumerate(batches, start=1):
            print(
                f"  Processing batch {batch_idx}/{len(batches)} | size {len(batch)}",
                flush=True,
            )
            max_workers = min(MAX_CONCURRENCY, len(batch))
            print(f"    Parallel workers: {max_workers}", flush=True)

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {}
                for item_pos, idx in enumerate(batch, start=1):
                    attempt_count[idx] += 1
                    future = executor.submit(
                        classify_one,
                        idx,
                        df.iloc[idx],
                        attempt,
                        batch_idx,
                        len(batches),
                        item_pos,
                        len(batch),
                    )
                    futures[future] = idx

                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        result = future.result()
                    except Exception as e:
                        result = {
                            "index": idx,
                            "status": f"failure: worker_error: {str(e)}",
                            "reasoning": "",
                            "main_category": "",
                            "sub_category": "",
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "cached_tokens": 0,
                        }

                    result["attempt"] = attempt_count[idx]
                    latest_results[idx] = result

                    if result["status"] == "success":
                        pending.discard(idx)
                    elif attempt_count[idx] >= MAX_ATTEMPTS:
                        pending.discard(idx)

    for idx in invalid_indexes:
        latest_results[idx] = {
            "index": idx,
            "status": "failure: index out of range",
            "labels": [],
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cached_tokens": 0,
            "attempt": 0,
        }

    final_results = [latest_results[i] for i in sorted(latest_results)]

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for row in final_results:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    unresolved = [r["index"] for r in final_results if r["status"] != "success"]
    with open(UNRESOLVED_PATH, "w", encoding="utf-8") as f:
        json.dump(unresolved, f, indent=2)

    success_count = sum(r["status"] == "success" for r in final_results)
    invalid_count = sum(r["status"] == "invalid_category" for r in final_results)
    failure_count = len(final_results) - success_count - invalid_count

    total_prompt = sum(r["prompt_tokens"] for r in final_results)
    total_completion = sum(r["completion_tokens"] for r in final_results)
    total_cached = sum(r["cached_tokens"] for r in final_results)

    print("\n── Retry Results Summary ─────────────────────")
    print(f"  Total processed:   {len(final_results)}")
    print(f"  Success:           {success_count}")
    print(f"  Invalid category:  {invalid_count}")
    print(f"  Failures:          {failure_count}")
    print(f"  Still unresolved:  {len(unresolved)}")
    print(f"  Prompt tokens:     {total_prompt:,}")
    print(f"  Cached tokens:     {total_cached:,}")
    print(f"  Completion tokens: {total_completion:,}")
    print("──────────────────────────────────────────────")
    print(f"Saved retry results: {OUTPUT_PATH}")
    print(f"Saved unresolved ids: {UNRESOLVED_PATH}")


if __name__ == "__main__":
    main()
