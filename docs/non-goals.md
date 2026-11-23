# Non-goals

FlowSemantics deliberately excludes the following. Each exclusion is a
scope decision, not an oversight. Feature F39.

- Authentication or identity provider
- Authorization platform
- Database, ORM, or persistence in the core
- Message broker or distributed workflow scheduler
- Durable workflow engine
- Payment processor
- API gateway or cloud control plane
- AI or LLM runtime
- Hidden automatic retries
- Hidden network activity
- Default telemetry
- A mandatory visual editor
- Replacing `with` / `async with` or any native control flow

## Retry, circuit breaker, timeout enforcement

These belong to a separate resilience concern (`Portfolio.Resilience` or
`resilience-py`). FlowSemantics recognizes externally-imposed timeout
outcomes; it does not implement timeout policies.

## Why these exclusions matter

The core value of FlowSemantics is a small, formally specified execution
contract. Every feature that expands scope dilutes that contract. The
non-goals list is enforced through the pull request template, not just
stated here.

