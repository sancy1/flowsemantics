# Consumer-Driven Contract Tests (CDCT)

These tests verify that **a developer who only has the published package
and the public documentation** can use FlowSemantics correctly.

## Rules

- Each language folder is a standalone consumer project.
- Tests import **only** the published artifact (PyPI package, npm tarball,
  Go module, Maven artifact, NuGet package) — never the source tree.
- Test code is written from the README/docs/SPEC examples only, so a
  documentation bug surfaces as a test failure.
- Every SPEC feature (62 total, see `docs/feature-audit.md`) has at least
  one consumer test.

## Layout

```
cdc/
  python/       pip install flow-semantics  (or local wheel pre-publish)
  typescript/   npm install <packed tarball / registry package>
  go/           go get github.com/flowsemantics/flowsemantics-go@vX.Y.Z
  java/         Maven/Gradle dependency on the published GAV
  csharp/       PackageReference to the published NuGet id
```

## Running pre-publish (local artifact)

```bash
# Python example — build the wheel, then install it into a clean venv
python -m build --wheel python/
python -m venv cdc/python/.venv
cdc/python/.venv/Scripts/pip install python/dist/*.whl pytest
cdc/python/.venv/Scripts/python -m pytest cdc/python/tests -v
```

Post-publish the same tests run unchanged against the registry artifact.
