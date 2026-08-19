# Execution Unknown Decision Contract

Execution accepts only canonical decision metadata:

- `FAVORABLE` → `BUY`
- `UNFAVORABLE` → `SELL`
- `WAIT` → `HOLD`

Any other decision metadata is invalid for the execution planning boundary and must fail closed before an `ExecutionPlan` is created. It must never be mapped to `ExecutionSide.NONE` or allowed to become a skipped execution.
