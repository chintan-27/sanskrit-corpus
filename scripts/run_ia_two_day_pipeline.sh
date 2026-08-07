#!/usr/bin/env bash
set -euo pipefail

repo_root=/blue/neurology-dept/chintan.acharya/sanskrit-corpus
catalog_path="$repo_root/data/manifests/internet_archive_format_census.jsonl"
worker_pids=()

stop_workers() {
    if ((${#worker_pids[@]})); then
        kill "${worker_pids[@]}" 2>/dev/null || true
    fi
}
trap stop_workers EXIT INT TERM

cd "$repo_root"
export PYTHONPATH="$repo_root/src"
export PADDLE_PDX_CACHE_HOME="$repo_root/data/tools/paddle-models"
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
export UV_CACHE_DIR=/tmp/sanskrit-corpus-uv-cache

for shard_index in $(seq 0 11); do
    .venv/bin/python -m sanskrit_corpus.cli ia-pull \
        --catalog "$catalog_path" \
        --limit 0 \
        --max-gb 0 \
        --file-kind ocr_text \
        --compact-text \
        --shard-count 12 \
        --shard-index "$shard_index" &
    worker_pids+=("$!")
done

for shard_index in $(seq 0 3); do
    data/tools/paddleocr-venv/bin/python -m sanskrit_corpus.cli ia-ocr-pdf \
        --catalog "$catalog_path" \
        --limit 0 \
        --shard-count 4 \
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
