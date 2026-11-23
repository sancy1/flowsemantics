# flow-semantics (Python package)

This directory contains the Python distribution of FlowSemantics.

For the full project documentation, see the repository root `README.md`.

## Feature documentation

The language-neutral feature guides live in `../docs/`:

- `../docs/getting-started.md` — first flow
- `../docs/decision-tables.md` — decision tables and hit policies
- `../docs/error-handling.md` — catch/rethrow/finally semantics
- `../docs/finalization.md` — guaranteed cleanup
- `../docs/tracing.md` — execution traces and explain
- `../docs/replay-simulation.md` — replay, shadow, simulate
- `../docs/advanced-features.md` — merge, effective dates, portability
- `../docs/versioning.md` — contract versioning
- `../docs/framework-integration.md` — embedding in applications
- `../docs/cookbook.md` — recipes

The normative specification is `../SPEC.md`.

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

