# scratch_consumer

Sample consumer that proves the installed `flow-semantics` wheel works
end to end. **No project-reference imports.** The only way this sample
finds `flowsemantics` is as an installed package.

## How to run

From the repository root:

```
cd python
python -m build --wheel
cd ..
python -m venv .venv-sample
.venv-sample/Scripts/activate    # Windows
pip install python/dist/*.whl
cd python/samples/scratch_consumer
python main.py
```

Expected output: `flowsemantics version: <version>` and exit code 0.

## What this sample proves

- The wheel installs cleanly with plain `pip`.
- `import flowsemantics` succeeds in a clean environment.
- `flowsemantics.__version__` reports the version from the wheel metadata
  (not from a VERSION file -- the wheel does not ship VERSION).
- The sample has no reference to `../../src/` or any project file.

## What this sample does not prove

- It does not exercise any feature. Features begin in Phase 1.
- It does not replace the pip-wheel exit gate that runs in CI.

