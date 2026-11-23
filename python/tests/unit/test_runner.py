"""Unit tests for the conformance runner (runner-protocol.md)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flowsemantics.testing.conformance.runner import (
    discover_vectors,
    main,
    run_vector,
)


def _write_vector(dir_path: Path, name: str, vector: dict[str, Any]) -> Path:
    path = dir_path / f"{name}.json"
    path.write_text(json.dumps(vector), encoding="utf-8")
    return path


def _base_vector(**overrides: Any) -> dict[str, Any]:
    vector: dict[str, Any] = {
        "id": "test-vector",
        "spec_version": "0.1.0",
        "spec_section": "10.2",
        "pipeline": {
            "rules": [
                {
                    "id": "r1",
                    "condition": {"fixture": "cond.true"},
                    "action": {"fixture": "action.const", "params": {"v": 1}},
                }
            ]
        },
        "input": {"fixture": "input.empty"},
        "expected": {
            "execution_status": "COMPLETED",
            "decision_status": "APPROVED",
            "value": 1,
            "has_finalization": False,
        },
    }
    vector.update(overrides)
    return vector


# -- discovery -----------------------------------------------------------------


def test_discover_vectors_recursive(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    _write_vector(tmp_path, "a", _base_vector())
    _write_vector(tmp_path / "sub", "b", _base_vector())
    (tmp_path / "ignore.txt").write_text("not json")
    found = discover_vectors(tmp_path)
    assert len(found) == 2
    assert all(p.suffix == ".json" for p in found)


# -- run_vector -----------------------------------------------------------------


def test_run_vector_pass(tmp_path: Path) -> None:
    path = _write_vector(tmp_path, "v1", _base_vector())
    result = run_vector(path)
    assert result.passed is True
    assert result.vector_id == "test-vector"


def test_run_vector_wrong_expected_fails(tmp_path: Path) -> None:
    vector = _base_vector()
    vector["expected"]["value"] = 999
    path = _write_vector(tmp_path, "v1", vector)
    result = run_vector(path)
    assert result.passed is False
    assert "value" in result.reason


def test_run_vector_parse_error_is_runner_failure(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    result = run_vector(path)
    assert result.passed is False
    assert "runner failure" in result.reason


def test_run_vector_newer_spec_version_rejected(tmp_path: Path) -> None:
    path = _write_vector(tmp_path, "v1", _base_vector(spec_version="9.9.9"))
    result = run_vector(path)
    assert result.passed is False
    assert "newer than supported" in result.reason


def test_run_vector_missing_required_key(tmp_path: Path) -> None:
    vector = _base_vector()
    del vector["expected"]
    path = _write_vector(tmp_path, "v1", vector)
    result = run_vector(path)
    assert result.passed is False
    assert "runner failure" in result.reason


def test_run_vector_unknown_fixture_fails(tmp_path: Path) -> None:
    vector = _base_vector()
    vector["pipeline"]["rules"][0]["condition"] = {"fixture": "cond.nope"}
    path = _write_vector(tmp_path, "v1", vector)
    result = run_vector(path)
    assert result.passed is False
    assert "fixture" in result.reason


def test_run_vector_finally_supported(tmp_path: Path) -> None:
    vector = _base_vector()
    vector["pipeline"]["finally"] = {"fixture": "cleanup.succeeds"}
    vector["expected"]["has_finalization"] = True
    vector["expected"]["is_clean"] = True
    path = _write_vector(tmp_path, "v1", vector)
    result = run_vector(path)
    assert result.passed is True, result.reason


def test_run_vector_catch_supported(tmp_path: Path) -> None:
    vector = _base_vector()
    vector["pipeline"]["rules"][0]["action"] = {
        "fixture": "action.throws",
        "params": {"kind": "Kind.ValueError"},
    }
    vector["pipeline"]["catches"] = [
        {
            "kind": "typed",
            "exc_kind": "Kind.ValueError",
            "handler": {"fixture": "catch.handles", "params": {"v": "recovered"}},
        }
    ]
    vector["expected"] = {
        "execution_status": "COMPLETED",
        "decision_status": None,
        "value": "recovered",
        "has_recovery": True,
        "has_interruption": False,
        "interruption_kind": None,
        "has_finalization": False,
        "is_clean": None,
        "secondary_exceptions_count": 0,
        "primary_exception_kind": None,
        "effects": [],
    }
    path = _write_vector(tmp_path, "v1", vector)
    result = run_vector(path)
    assert result.passed is True, result.reason


def test_run_vector_trace_subset(tmp_path: Path) -> None:
    vector = _base_vector()
    vector["trace"] = [{"type": "action_executed", "rule_id": "r1"}]
    vector["trace_subset"] = True
    path = _write_vector(tmp_path, "v1", vector)
    result = run_vector(path)
    assert result.passed is True, result.reason


def test_run_vector_failed_outcome(tmp_path: Path) -> None:
    vector = _base_vector()
    vector["pipeline"]["rules"][0]["action"] = {
        "fixture": "action.throws",
        "params": {"kind": "Kind.ValueError"},
    }
    vector["expected"] = {
        "execution_status": "FAILED",
        "has_finalization": False,
        "primary_exception_kind": "Kind.ValueError",
    }
    path = _write_vector(tmp_path, "v1", vector)
    result = run_vector(path)
    assert result.passed is True


def test_run_vector_no_match(tmp_path: Path) -> None:
    vector = _base_vector()
    vector["pipeline"]["rules"][0]["condition"] = {"fixture": "cond.false"}
    vector["expected"] = {
        "execution_status": "COMPLETED",
        "decision_status": "NO_MATCH",
        "has_finalization": False,
    }
    path = _write_vector(tmp_path, "v1", vector)
    result = run_vector(path)
    assert result.passed is True


# -- main ------------------------------------------------------------------------


def test_main_all_pass(tmp_path: Path, capsys: Any) -> None:
    _write_vector(tmp_path, "v1", _base_vector())
    _write_vector(tmp_path, "v2", _base_vector(id="second"))
    rc = main(["--vectors", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "RESULT: 2/2 passed" in out


def test_main_one_fail(tmp_path: Path, capsys: Any) -> None:
    _write_vector(tmp_path, "v1", _base_vector())
    bad = _base_vector(id="bad")
    bad["expected"]["value"] = 999
    _write_vector(tmp_path, "v2", bad)
    rc = main(["--vectors", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "RESULT: 1/2 passed" in out
    assert "FAIL bad" in out


def test_main_missing_dir(capsys: Any) -> None:
    rc = main(["--vectors", "does-not-exist-xyz"])
    assert rc == 2
