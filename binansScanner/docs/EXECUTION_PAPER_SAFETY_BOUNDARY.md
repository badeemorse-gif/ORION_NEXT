# ORION Phase A — Paper Execution Safety Boundary

Phase A execution is paper-only. The execution entry path is:

`DecisionResult → ExecutionPlanBuilder → ExecutionEngine → ExecutionAdapter`

Canonical decision semantics remain:

- `FAVORABLE` → `BUY`
- `UNFAVORABLE` → `SELL`
- `WAIT` → `HOLD` with `quantity=0` → `SKIPPED`
- `UNKNOWN` / `UNSPECIFIED` → rejected before `ExecutionPlan` creation

The current composition root creates only `PaperExecutionAdapter`. The paper adapter validates locally and produces synthetic `PAPER-ORD-*` identifiers; it does not contact a live exchange.

## Configuration boundary

`ORION_TRADING_PAPER_TRADING` is loaded into `ContainerConfiguration.paper_trading_enabled`.

- `true` → build the existing `PaperExecutionAdapter`.
- `false` → fail closed with `ContainerError`.

There is no fallback from `paper_trading_enabled=false` to a live execution implementation.

Binance API credentials are provider-layer settings and are not consumed by `PaperExecutionAdapter`. `ORION_BINANCE_TESTNET` selects the Binance provider configuration for market-data/provider access; it is not an execution-mode switch and cannot activate live orders.

## Accidental-live paths

The review found no `LiveExecutionAdapter` and no live order-placement implementation in the current Phase A branch. The previous risk was therefore configuration semantics: a future live executor could have been introduced behind the existing `paper_trading_enabled` flag without a separate boundary.

That path is now closed at the composition root. A future live implementation must introduce a separately reviewed execution boundary instead of reusing the Phase A paper path as an implicit bridge.

## Opportunity-response timing boundary

Paper execution must preserve timing evidence needed to determine whether an opportunity was lost because of execution-path delay.

Where the upstream opportunity/decision path supplies timestamps, the paper path must retain or expose, without inventing timestamps:

- `opportunity_detected_at`
- `decision_at`
- `execution_requested_at`
- `execution_confirmed_at`

The execution layer is responsible for measuring execution-path latency, not for redefining when the opportunity became valid.

A paper execution success must therefore not be interpreted as evidence that opportunity response was timely. Timing acceptance is a separate verification concern.

## Position-management boundary

Phase A remains limited to paper entry/execution safety. It does not imply that `ExecutionResult` completes the lifecycle of an active trading position.

When Position Management is introduced, it must be a separately reviewed component handling the post-entry lifecycle, including profit protection, trailing/scale-out decisions, invalidation, and exit execution. A future exit must not be implemented by silently changing the meaning of the existing entry `DecisionResult` contract.

## Phase A guardrail

`paper_trading_enabled == False` → **FAIL CLOSED**

No execution adapter or execution engine is constructed after that failure.

## Prohibited Phase A behavior

- Live credentials used for order execution.
- Live order-placement API calls.
- Live adapter construction.
- Configuration-only activation of live execution.
- Unknown-decision fallback to `ExecutionSide.NONE` / `SKIPPED`.
- Claiming opportunity-response latency is acceptable without timestamp evidence.
- Treating paper execution success as proof of trading-strategy profitability or timely opportunity capture.
