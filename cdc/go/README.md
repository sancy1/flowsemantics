# CDCT — Go consumer

Verifies that a developer using **only the published
`github.com/sancy1/flowsemantics/go` module and the public docs**
can exercise all 62 SPEC features.

## Pre-publish (local replace)

Go has no registry — the git repo *is* the artifact. Until the first tag
exists, `go.mod` uses a `replace` directive pointing at `../../go`.
The import path is still the real module path, so the consumer code is
identical to post-publish.

```bash
cd cdc/go
go mod tidy
go test ./...
```

## Post-publish (tagged release)

After the repo is pushed and tagged `v0.1.0`:

```bash
# in cdc/go/go.mod: remove the replace line, set
#   require github.com/sancy1/flowsemantics/go v0.1.0
# then:
go mod tidy && go test ./...
```

`go get github.com/sancy1/flowsemantics/go@v0.1.0` resolves via
the Go module proxy automatically — no registry account needed.

## Coverage

`consumer_test.go` — tests mapping to all 62 features in
`docs/feature-audit.md`.
