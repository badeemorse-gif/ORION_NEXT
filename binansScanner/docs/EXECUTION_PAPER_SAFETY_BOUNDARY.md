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

## Phase A guardrail

`paper_trading_enabled == False` → **FAIL CLOSED**

No execution adapter or execution engine is constructed after that failure.

## Prohibited Phase A behavior

- Live credentials used for order execution.
- Live order-placement API calls.
- Live adapter construction.
- Configuration-only activation of live execution.
- Unknown-decision fallback to `ExecutionSide.NONE` / `SKIPPED`.
