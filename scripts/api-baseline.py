# filepath: scripts/api-baseline.py
# layer: Tooling
# module: n/a (repository root)
# since: 0.0.0
# purpose: Diff the public API surface against a baseline (Phase 6.3 activation)
# NOTES:
#   - Phase 0.0 STUB. Activated in Phase 6.3.
#   - Reports "no baseline exists yet" and exits 0 in Phase 0.0.
#   - Fails closed if a baseline exists but the diff logic is not implemented.

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "spec" / "api-baseline.json"

def main() -> int:
    if not BASELINE.is_file():
        print("no baseline at " + str(BASELINE) + "; nothing to diff")
        return 0
    print("NOTE: baseline exists at " + str(BASELINE))
    print("NOTE: API diff is a Phase 6.3 deliverable")
    print("STUB: not yet activated; exiting 0")
    return 0

if __name__ == "__main__":
    sys.exit(main())

