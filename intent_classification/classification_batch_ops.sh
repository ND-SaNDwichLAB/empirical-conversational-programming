#!/bin/zsh
set -euo pipefail

SCRIPT="classification_batch.py"
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLASSIFICATION_DIR="$ROOT_DIR/../data/classifications"
BATCH_INPUT_DIR="$CLASSIFICATION_DIR/batch_inputs"
BATCH_ID_DIR="$CLASSIFICATION_DIR/batch_ids"

usage() {
  echo "Usage:"
  echo "  ./classification_batch_ops.sh <action> [batch_no]"
  echo "  ./classification_batch_ops.sh <action> <start_no> <end_no>"
  echo
  echo "Actions: submit | status | download | errors | peek"
  echo
  echo "Examples:"
  echo "  ./classification_batch_ops.sh submit 1 100"
  echo "  ./classification_batch_ops.sh status 1 100"
  echo "  ./classification_batch_ops.sh download 1 100"
  echo "  ./classification_batch_ops.sh submit      # auto-detect range"
}

if [[ $# -lt 1 || $# -gt 3 ]]; then
  usage
  exit 1
fi

action="$1"

case "$action" in
  submit|status|download|errors|peek) ;;
  *)
    echo "Unknown action: $action"
    usage
    exit 1
    ;;
esac

setopt null_glob

infer_end() {
  local mode="$1"
  local -a files
  if [[ "$mode" == "submit" ]]; then
    files=("$BATCH_INPUT_DIR"/batch_input_*.jsonl)
  else
    files=("$BATCH_ID_DIR"/batch_id_*.txt)
  fi

  if [[ ${#files[@]} -eq 0 ]]; then
    echo ""
    return
  fi

  local max_no=0
  local base no
  for f in "${files[@]}"; do
    base="${f:t}"
    no="${base//[^0-9]/}"
    if [[ -n "$no" ]]; then
      no=$((10#$no))
      if (( no > max_no )); then
        max_no=$no
      fi
    fi
  done

  echo "$max_no"
}

if [[ $# -eq 1 ]]; then
  start_no=1
  end_no="$(infer_end "$action")"
  if [[ -z "$end_no" ]]; then
    if [[ "$action" == "submit" ]]; then
      echo "No batch input files found in: $BATCH_INPUT_DIR"
    else
      echo "No batch id files found in: $BATCH_ID_DIR"
    fi
    exit 1
  fi
elif [[ $# -eq 2 ]]; then
  start_no="$2"
  end_no="$2"
else
  start_no="$2"
  end_no="$3"
fi

if (( start_no < 1 || end_no < start_no )); then
  echo "Invalid range: $start_no..$end_no"
  exit 1
fi

echo "Action: $action | Range: $start_no..$end_no"

for no in $(seq "$start_no" "$end_no"); do
  if [[ "$action" == "submit" ]]; then
    input_file=$(printf "%s/batch_input_%04d.jsonl" "$BATCH_INPUT_DIR" "$no")
    if [[ ! -f "$input_file" ]]; then
      echo "[$no] Skip: missing input file $input_file"
      continue
    fi
  else
    id_file=$(printf "%s/batch_id_%04d.txt" "$BATCH_ID_DIR" "$no")
    if [[ ! -f "$id_file" ]]; then
      echo "[$no] Skip: missing batch id file $id_file"
      continue
    fi
  fi

  echo "[$no] Running: python $SCRIPT $action $no"
  python "$ROOT_DIR/$SCRIPT" "$action" "$no"
  echo "[$no] Done"
  echo "----------------------------------------"
done

echo "All done."