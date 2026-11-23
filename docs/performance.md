# Performance

FlowSemantics performance rules (SPEC.md Section 13). This page records
what the Python implementation does, what it does not do, and the
reproducible evidence behind every claim.

## 13.1 Compiled equals interpreted

The Python implementation provides **no compiled execution path**.
`Flow.compile()` produces an immutable `FlowContract` that is executed
by the interpreted engine on every call. There is no fused-delegate or
bytecode path, so the compiled-equals-interpreted MUST is satisfied
vacuously: there is exactly one execution path, and it is the
interpreted one.

If a future version adds a compiled path, it MUST produce identical
outcomes for every input and MUST be covered by the full conformance
vector suite plus a dedicated parity test before release.

## 13.2 Allocation goals

The common path (no trace, FirstMatch, no exceptions, no finalization,
no effects) allocates per execution:

- One `FlowContext` per `try_execute` call.
- One `FlowOutcome` per execution (immutable result — required by
  SPEC 3.6).
- Trace recorder: **none** when tracing is disabled (zero-cost, SPEC
  12.3).

Per-rule allocation on the common path is limited to the outcome value
produced by the user action. The engine itself does not allocate
per-rule on the matched path beyond the outcome.

A zero-allocation common path is RECOMMENDED but not required
(SPEC 13.2). The current implementation allocates the outcome object
per call, which is documented here as required by the immutable
FlowOutcome contract.

## 13.3 Benchmarking rules

All performance claims MUST be backed by a committed, reproducible
benchmark (SPEC 13.3). The harness is:

- `benchmarks/bench_common_path.py` — stdlib only, deterministic
  iteration counts, reports p50/p95/p99 latency, throughput, and
  allocations.
- `benchmarks/results/` — committed benchmark data.

Reproduce:

```bash
python benchmarks/bench_common_path.py --iterations 50000 --warmup 2000
```

### Latest recorded result (2026-11-22)

Environment: Python 3.11.9, Windows (win32). Contract: 5 rules,
FirstMatch, common path.

| Metric | Value |
|---|---|
| p50 latency | 16.3 µs |
| p95 latency | 31.2 µs |
| p99 latency | 46.1 µs |
| Throughput | ~50,170 ops/sec |
| Peak allocation (50k-call batch) | 688 bytes (tracemalloc) |

Data: `benchmarks/results/common-path-2026-11-22.json`.

### What is NOT claimed

- No comparison to native code, other libraries, or other versions is
  published. The 3-5x compiled-path hypothesis (SPEC 13.4) is **not**
  claimed: there is no compiled path to measure.
- No marketing performance figures appear in this documentation.

## Reproducing on different hardware

The benchmark is hardware-dependent. To compare across machines, run
the same command and commit the new JSON under
`benchmarks/results/<date>-<host>.json`. Do not overwrite prior results;
they are the historical record.
