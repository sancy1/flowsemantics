"""Integration test: the published conformance vector suite passes end-to-end."""

from __future__ import annotations

from pathlib import Path

from flowsemantics.testing.conformance.runner import main

VECTORS_DIR = (
    Path(__file__).resolve().parents[3] / "conformance" / "vectors"
)


def test_published_vectors_all_pass(capsys) -> None:
    assert VECTORS_DIR.is_dir(), f"vectors dir missing: {VECTORS_DIR}"
    rc = main(["--vectors", str(VECTORS_DIR)])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "FAIL" not in out
    assert "RESULT:" in out
