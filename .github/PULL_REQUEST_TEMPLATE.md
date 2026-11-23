<!--
filepath: .github/PULL_REQUEST_TEMPLATE.md
layer:    Tooling
module:   n/a (repository root)
since:    0.0.0
purpose:  Phase exit-gate checklist applied to the last PR of every phase
-->

# Pull Request

## Summary

<!-- One or two sentences. What changed and why. -->

## Phase exit-gate checklist

Every item must be checked before this PR is merged. If an item does not apply, write `N/A - <reason>`.

- [ ] All sub-phase deliverables are merged.
- [ ] Unit tests pass on Windows, Linux, and macOS.
- [ ] Conformance vectors for this phase are green.
- [ ] The phase documentation pages are written, and every code block is verified against a compiled sample region.
- [ ] The paired sample builds and runs against the packed local wheel, with no project references.
- [ ] `audit.py` is green: zero third-party references, no banned network or ambient-time APIs in core.
- [ ] The public API baseline is diffed; any change is intentional and recorded in `CHANGELOG.md`.
- [ ] `IMPLEMENTATION_STATE.md` and `HANDOVER.md` describe what actually shipped, not what was planned.
- [ ] The pre-release package is tagged according to the release train.
- [ ] The risk register has been reviewed and any new risk recorded.

## Documentation discipline

- [ ] Every new or modified public symbol has a Google-style docstring with Args, Returns, Raises where applicable.
- [ ] Every new or modified file has a file header block (purpose, layer, module, since, implements, depends on, used by, see also, notes).
- [ ] Documentation was verified against the code in this change, not written from memory.
- [ ] If a code block was added to `docs/`, it is tagged with a sample region and matches the compiled sample source.

## Findings

<!-- List any findings opened, closed, or carried forward by this PR. Include IDs. -->

## Not verified in this PR

<!-- Anything the author could not verify. Protocol Law 3: label honestly. -->

