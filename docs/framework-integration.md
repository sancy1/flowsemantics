# Framework integration

> **Status**: planned — Phase 5 (framework integration) per the
> implementation plan. This page will document FastAPI/ASGI integration
> patterns when that phase ships.

## What exists today

The library is framework-agnostic by design (SPEC 1.3 non-goals: no web
framework coupling). Any Python web framework can call
`contract.try_execute(input)` inside a request handler today:

```python
# FastAPI sketch — works today, no integration package needed
from fastapi import FastAPI
from flowsemantics import Flow

app = FastAPI()
contract = Flow().when(...).compile()

@app.post("/decide")
def decide(payload: dict) -> dict:
    outcome = contract.try_execute(payload)
    return {"status": outcome.execution_status.name, "value": outcome.value}
```

## Planned (Phase 5)

- Official FastAPI integration guide and optional helper package.
- ASGI middleware pattern for trace propagation.
- Documentation of async (`try_execute_async`) usage in async
  frameworks.

Until then, the contract API is the integration surface — it is
synchronous and asynchronous, deterministic, and framework-neutral.
