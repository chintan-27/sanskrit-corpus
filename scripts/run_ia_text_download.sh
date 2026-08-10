#!/usr/bin/env bash
set -euo pipefail

repo_root=/blue/neurology-dept/chintan.acharya/sanskrit-corpus
catalog_path="$repo_root/data/manifests/internet_archive_format_census.jsonl"
completed_index="$repo_root/data/manifests/internet_archive_completed_ids.txt"
completed_index_partial="$completed_index.partial"
worker_pids=()

stop_workers() {
    if ((${#worker_pids[@]})); then
        kill "${worker_pids[@]}" 2>/dev/null || true
    fi
}
trap stop_workers EXIT INT TERM

cd "$repo_root"
export PYTHONPATH="$repo_root/src"

find "$repo_root/data/raw/internet_archive" -type f -name '*.txt.gz' -printf '%P\n' \
    | cut -d/ -f1 \
    | sort -u > "$completed_index_partial"
mv "$completed_index_partial" "$completed_index"

for shard_index in $(seq 0 23); do
    .venv/bin/python -m sanskrit_corpus.cli ia-pull \
        --catalog "$catalog_path" \
        --completed-index "$completed_index" \
        --limit 0 \
        --max-gb 0 \
        --file-kind ocr_text \
        --compact-text \
        --shard-count 24 \
        --shard-index "$shard_index" &
    worker_pids+=("$!")
done

failed=0
for worker_pid in "${worker_pids[@]}"; do
    if ! wait "$worker_pid"; then
        failed=1
    fi
done
worker_pids=()
exit "$failed"
