from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import queue
import time
from pathlib import Path
from typing import Any


def worker(pdf_path: str, start: Any, ready: Any, results: Any) -> None:
    try:
        from sanskrit_corpus.ia_ocr import PaddleDevanagariBackend

        backend = PaddleDevanagariBackend()
        ready.put({"status": "ready"})
        if not start.wait(timeout=900):
            raise TimeoutError("start barrier timed out")
        started = time.monotonic()
        text, _ = backend.recognize_pdf(Path(pdf_path))
        results.put(
            {
                "status": "ok",
                "pages": text.count("<<<PAGE "),
                "seconds": time.monotonic() - started,
            }
        )
    except BaseException as exc:
        message = {"status": "failed", "error": f"{type(exc).__name__}:{exc}"}
        ready.put(message)
        results.put(message)


def run_level(pdf_path: Path, concurrency: int, timeout: int) -> dict[str, Any]:
    context = mp.get_context("spawn")
    start = context.Event()
    ready = context.Queue()
    results = context.Queue()
    processes = [context.Process(target=worker, args=(str(pdf_path), start, ready, results)) for _ in range(concurrency)]
    initialized = 0
    init_failures: list[str] = []
    init_started = time.monotonic()
    for process in processes:
        process.start()
    while initialized + len(init_failures) < concurrency and time.monotonic() - init_started < timeout:
        try:
            message = ready.get(timeout=5)
        except queue.Empty:
            continue
        if message["status"] == "ready":
            initialized += 1
        else:
            init_failures.append(message["error"])

    if initialized != concurrency:
        for process in processes:
            process.terminate()
        for process in processes:
            process.join(timeout=10)
        return {
            "concurrency": concurrency,
            "status": "initialization_failed",
            "initialized": initialized,
            "failures": init_failures[:10],
            "initialization_seconds": time.monotonic() - init_started,
        }

    inference_started = time.monotonic()
    start.set()
    completed: list[dict[str, Any]] = []
    while len(completed) < concurrency and time.monotonic() - inference_started < timeout:
        try:
            completed.append(results.get(timeout=5))
        except queue.Empty:
            continue
    wall_seconds = time.monotonic() - inference_started
    for process in processes:
        if process.is_alive():
            process.terminate()
        process.join(timeout=10)
    successes = [result for result in completed if result["status"] == "ok"]
    pages = sum(int(result["pages"]) for result in successes)
    return {
        "concurrency": concurrency,
        "status": "ok" if len(successes) == concurrency else "inference_failed",
        "initialized": initialized,
        "completed": len(successes),
        "pages": pages,
        "wall_seconds": wall_seconds,
        "pages_per_second": pages / wall_seconds if wall_seconds else 0,
        "mean_worker_seconds": sum(float(result["seconds"]) for result in successes) / len(successes) if successes else None,
        "failures": [result["error"] for result in completed if result["status"] != "ok"][:10],
        "initialization_seconds": inference_started - init_started,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--levels", type=int, nargs="+", default=[5, 10, 20, 30, 40, 50, 100])
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for level in args.levels:
        result = run_level(args.pdf.resolve(), level, args.timeout)
        with args.output.open("a", encoding="utf-8") as output:
            output.write(json.dumps(result, sort_keys=True) + "\n")
        print(json.dumps(result, sort_keys=True), flush=True)
        if result["status"] != "ok":
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
