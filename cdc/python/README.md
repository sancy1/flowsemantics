# CDCT — Python consumer

Verifies that a developer using **only the published `flow-semantics`
package and the public docs** can exercise all 62 SPEC features.

## Pre-publish (local wheel)

```bash
# from repo root
python -m build --wheel python/
python -m venv cdc/python/.venv
cdc/python/.venv/Scripts/pip install python/dist/*.whl pytest
cdc/python/.venv/Scripts/python -m pytest cdc/python/tests -v
```

## Post-publish (PyPI)

```bash
pip install flow-semantics pytest
pytest cdc/python/tests -v
```

## Coverage

`tests/test_consumer.py` — 46 tests mapping to all 62 features in
`docs/feature-audit.md` (some tests cover multiple features).
