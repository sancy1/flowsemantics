# Migration guide

SPEC.md Section 15.6 requires every release — including small breaking
changes — to ship a migration guide stating what changed, why, and what
a consumer must do to upgrade. This page is the template; each release
adds a dated section below.

## Template (copy per release)

```markdown
## <version> — <date>

### Breaking changes
- <what changed, with before/after code if applicable>

### Why
- <rationale; link to ADR or SPEC section>

### Migration steps
1. <concrete step>
2. <concrete step>

### Deprecations
- <anything deprecated but still functional, with removal version>
```

## Releases

_No released versions yet. The project is pre-1.0 (`VERSION` = 0.0.0);
SPEC v0.1 is frozen and changes require an ADR plus a specification
version bump (SPEC 8.5)._

## Pre-1.0 compatibility note

Before 1.0.0, the public API may change between minor versions without
a major bump, per semantic versioning pre-1.0 conventions. Every such
change still gets a CHANGELOG entry and, when consumer-visible, a
section in this guide.
