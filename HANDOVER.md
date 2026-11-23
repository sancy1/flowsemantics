# Next-Session Handoff

Read this file first in every new session. It replaces chat history.

```
NEXT-SESSION HANDOFF

Read first:           v5 feature baseline (Feature Differentiation & Approval Note v5)
                      Implementation Plan v1.0
                      IMPLEMENTATION_STATE.md
                      PLANNING.md
                      SPEC.md (FROZEN v0.1, SHA256 089AD516…)

Current phase:        Phase 1 ~85% (2026-11-22). Engine complete for
                      decision layer; 13/13 vectors PASS; 126 tests pass.
                      Remaining: git init + tag 0.1.0-alpha.1, then Phase 2.

Last verified action: pytest 126/126, conformance 13/13, mypy --strict
                      clean (22 files), ruff clean, audit.py 5/5,
                      wheel installs from local feed

Do not repeat:        SPEC.md is frozen — changes require ADR + version bump.
                      uv.lock must not be regenerated unless pyproject.toml
                      changes. audit.py bans datetime.now/utcnow/time.time
                      in Core; SystemClock is the single sanctioned reader
                      (SPEC 6.3) — keep it that way.
                      Write-to-temp-then-commit discipline for large files;
                      verify temp files for DUPLICATE SECTIONS before commit.

Open findings:        No git repo exists — `git init` needed before
                      tagging 0.1.0-alpha.1. Spec gap: REJECTED polarity
                      undefined in SPEC v0.1 (matched rules yield APPROVED).
                      Merge/DecisionTable lack conformance vectors (schema
                      cannot express them); covered by tests, deferred to
                      portable-IR phase.

Next permitted action: Phase 2.0 — catch rules. Read SPEC.md sections
                      11.1-11.3 (exception model, catch rules, CatchMode)
                      and spec/fixtures.md catch.* entries, then implement
                      Flow.catch() + CatchRule + engine exception routing.
                      ~45 error/finalization vectors follow in 2.0-2.5.
```

## Rules for this file

- Written at every session close, never mid-session.
- The next session reads artifacts, not chat history.
- `Next permitted action` names exactly one read or one write.
- STANDING RULE (user mandate 2026-11-22): every phase and sub-phase ships
  unit tests AND integration/conformance tests in the same commit as the
  code. No feature lands without its tests. Phase 1 pattern: unit tests
  in python/tests/unit/, end-to-end in python/tests/integration/,
  normative semantics as vectors in conformance/vectors/.
