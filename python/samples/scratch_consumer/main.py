"""scratch_consumer: exercises flow-semantics exactly as docs/getting-started.md shows.

Layer:      Tests
Module:     scratch_consumer.main
Since:      0.1.0
Implements: consumer-path behavioral proof (Phase 1.8)
Depends on: flowsemantics (installed package only)
Used by:    manual run; docs-consumer.yml (Phase 1.8)
See also:   docs/getting-started.md, python/samples/scratch_consumer/README.md

Notes:
  - Exits non-zero with a clear message if flowsemantics is not installed.
  - Does not reach into python/src/; only imports the installed package.
  - Mirrors the examples in docs/getting-started.md; docs-snippets.py
    verifies the doc snippets match this file's behavior.
"""

from __future__ import annotations

import sys
from typing import Any


def _total_above_100(input: Any) -> bool:
    return input["total"] > 100


def _approve(input: Any) -> str:
    return "approved:" + str(input["total"])


def _reject(input: Any) -> str:
    return "rejected"


def _needs_review(input: Any) -> str:
    return "review:" + str(input["total"])


def main() -> int:
    """Run the documented example flow and print outcomes."""
    try:
        from flowsemantics import Flow
    except ImportError:
        print("ERROR: flow-semantics is not installed.", file=sys.stderr)
        print("Install the wheel first; see README.md in this folder.", file=sys.stderr)
        return 1

    flow = (
        Flow()
        .when(_total_above_100, then=_approve, id="large-order")
        .when_not(_total_above_100, then=_reject, id="small-order")
        .otherwise(_needs_review)
    )
    contract = flow.compile()

    for order in ({"total": 250}, {"total": 40}, {"total": 0}):
        outcome = contract.try_execute(order)
        print(
            "total={total} -> {status}/{decision} value={value}".format(
                total=order["total"],
                status=outcome.execution_status.name,
                decision=(
                    outcome.decision_status.name
                    if outcome.decision_status is not None
                    else "NONE"
                ),
                value=outcome.value,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
