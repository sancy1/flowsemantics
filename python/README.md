# flow-semantics (Python)

FlowSemantics expresses the decision, error-recovery, guaranteed-cleanup,
and interruption-accounting portions of complex application logic as a
traceable, testable, portable pipeline — with **zero runtime
dependencies** (standard library only).

Repository: [github.com/sancy1/flowsemantics](https://github.com/sancy1/flowsemantics)`n`n**Documentation:** [sancy1.github.io/flowsemantics](https://sancy1.github.io/flowsemantics/) — guides, feature catalog, and API reference

## Feature documentation

The language-neutral feature guides live in the
[repository documentation](https://github.com/sancy1/flowsemantics/tree/main/docs):

- [Feature catalog](https://github.com/sancy1/flowsemantics/blob/main/docs/features.md) — all 62 features
- [Getting started](https://github.com/sancy1/flowsemantics/blob/main/docs/getting-started.md) — first flow
- [Decision tables](https://github.com/sancy1/flowsemantics/blob/main/docs/decision-tables.md) — hit policies
- [Error handling](https://github.com/sancy1/flowsemantics/blob/main/docs/error-handling.md) — catch/rethrow/finally
- [Finalization](https://github.com/sancy1/flowsemantics/blob/main/docs/finalization.md) — guaranteed cleanup
- [Tracing](https://github.com/sancy1/flowsemantics/blob/main/docs/tracing.md) — traces and explain
- [Replay & simulation](https://github.com/sancy1/flowsemantics/blob/main/docs/replay-simulation.md)
- [Advanced features](https://github.com/sancy1/flowsemantics/blob/main/docs/advanced-features.md) — merge, portability
- [Versioning](https://github.com/sancy1/flowsemantics/blob/main/docs/versioning.md)
- [Framework integration](https://github.com/sancy1/flowsemantics/blob/main/docs/framework-integration.md)
- [Cookbook](https://github.com/sancy1/flowsemantics/blob/main/docs/cookbook.md) — recipes

The normative specification is [SPEC.md](https://github.com/sancy1/flowsemantics/blob/main/SPEC.md).

## Package identity

| Purpose | Name |
|---|---|
| PyPI distribution | `flow-semantics` |
| Python import | `flowsemantics` |
| Minimum Python | 3.11 |

## Dependencies

Runtime dependencies: **zero third-party**. Standard library only. Enforced by the repository audit.

Build dependencies: `hatchling` (declared in `pyproject.toml`).

Development dependencies: `ruff`, `mypy`, `pytest`, `pytest-asyncio`, `uv`, `sphinx` (declared in `pyproject.toml` under `[dependency-groups].dev`; not shipped).

## API documentation (auto-generated HTML)

Published: https://sancy1.github.io/flowsemantics/python/

Docstrings are the single source of truth; Sphinx renders them to HTML,
mirroring the C# XML file, Java Javadoc, and Go godoc output.

```
python -m sphinx.ext.apidoc -o docs -f src/flowsemantics   # regenerate module stubs
python -m sphinx -b html docs docs/_build/html             # build HTML
```

Output: `docs/_build/html/index.html`.

## Installation (consumer path is `pip`)

```
pip install flow-semantics
```

## Local development

See the root `CONTRIBUTING.md` for the tooling, the packaging rules, and the pull request checklist.

