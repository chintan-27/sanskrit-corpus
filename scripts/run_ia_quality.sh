#!/usr/bin/env bash
set -euo pipefail

repo_root=/blue/neurology-dept/chintan.acharya/sanskrit-corpus
worker_pids=()

stop_workers() {
    if ((${#worker_pids[@]})); then
        kill "${worker_pids[@]}" 2>/dev/null || true
    fi
}
trap stop_workers EXIT INT TERM

cd "$repo_root"
export PYTHONPATH="$repo_root/src"

for shard_index in $(seq 0 3); do
    .venv/bin/python -m sanskrit_corpus.cli ia-quality \
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
