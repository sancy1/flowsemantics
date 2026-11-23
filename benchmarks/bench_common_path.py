"""Reproducible benchmark for the FlowSemantics common path (SPEC 13.3).

Measures the SPEC 13.2 common path: no trace, FirstMatch, no exceptions,
no finalization, no effects. Reports p50/p95/p99 latency, allocations,
and throughput. Stdlib only; deterministic iteration counts.

Usage:
    python benchmarks/bench_common_path.py [--iterations N] [--warmup N]

Output is a single JSON document on stdout, suitable for committing
benchmark data alongside the harness (SPEC 13.3).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python" / "src"))

from flowsemantics import Flow, FlowContract


def build_contract() -> FlowContract:
    """Representative common-path contract: 5 rules, first match wins."""
    flow = Flow()
    for i in range(5):
        flow.when(
            lambda inp, i=i: inp.get("tier") == i,
            then=lambda inp, i=i: {"tier": i, "ok": True},
            id=f"r{i}",
        )
    return flow.default({"tier": -1, "ok": False}).compile()


def percentile(sorted_values: list[float], pct: float) -> float:
    """Nearest-rank percentile on a sorted list."""
    if not sorted_values:
        return 0.0
    rank = max(
        0, min(len(sorted_values) - 1, round(pct / 100.0 * len(sorted_values)) - 1)
    )
    return sorted_values[rank]


def run_benchmark(iterations: int, warmup: int) -> dict[str, object]:
    """Run the benchmark and return the results document."""
    contract = build_contract()
    inp = {"tier": 3}

    for _ in range(warmup):
        contract.try_execute(inp)

    # Latency: per-call wall time in microseconds.
    latencies_us: list[float] = []
    t0 = time.perf_counter()
    for _ in range(iterations):
        start = time.perf_counter()
        contract.try_execute(inp)
        latencies_us.append((time.perf_counter() - start) * 1e6)
    total_s = time.perf_counter() - t0
    latencies_us.sort()

    # Allocations: tracemalloc over a fresh batch.
    tracemalloc.start()
    for _ in range(iterations):
        contract.try_execute(inp)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return {
        "benchmark": "common_path_first_match",
        "iterations": iterations,
        "warmup": warmup,
        "latency_us": {
            "p50": percentile(latencies_us, 50),
            "p95": percentile(latencies_us, 95),
            "p99": percentile(latencies_us, 99),
            "mean": statistics.fmean(latencies_us),
        },
        "throughput_ops_per_sec": iterations / total_s if total_s > 0 else 0.0,
        "allocations": {
            "peak_bytes_during_batch": peak,
            "note": "tracemalloc peak over the full batch, not per-call",
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": sys.platform,
        },
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=100_000)
    parser.add_argument("--warmup", type=int, default=1_000)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            run_benchmark(args.iterations, args.warmup), indent=2, sort_keys=True
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
