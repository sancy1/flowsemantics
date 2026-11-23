"""Smoke tests for the committed benchmark harness (SPEC 13.3)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BENCH = REPO_ROOT / "benchmarks" / "bench_common_path.py"


def test_benchmark_runs_and_reports_required_metrics() -> None:
    """The harness must produce p50/p95/p99, throughput, and allocations."""
    proc = subprocess.run(
        [sys.executable, str(BENCH), "--iterations", "200", "--warmup", "20"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["benchmark"] == "common_path_first_match"
    assert data["iterations"] == 200
    for key in ("p50", "p95", "p99", "mean"):
        assert key in data["latency_us"]
        assert data["latency_us"][key] >= 0
    assert data["throughput_ops_per_sec"] > 0
    assert "peak_bytes_during_batch" in data["allocations"]


def test_benchmark_is_deterministic_in_shape() -> None:
    """Two runs produce the same document shape (values may differ)."""
    proc = subprocess.run(
        [sys.executable, str(BENCH), "--iterations", "100", "--warmup", "10"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert set(data.keys()) == {
        "benchmark",
        "iterations",
        "warmup",
        "latency_us",
        "throughput_ops_per_sec",
        "allocations",
        "environment",
    }
