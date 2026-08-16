# ORION Phase A — Paper Execution Safety Boundary

## Scope

Phase A is paper-only. The execution entry path is:

`DecisionResult → ExecutionPlanBuilder → ExecutionEngine → ExecutionAdapter`

Canonical decision semantics remain:

- `FAVORABLE` → `BUY`
- `UNFAVORABLE` → `SELL`
- `WAIT` → `HOLD` with `quantity=0` → `SKIPPED`
- `UNKNOWN` / `UNSPECIFIED` → rejected before `ExecutionPlan` creation

## Paper / Live separation

The Phase A composition root registers only `PaperExecutionAdapter`.

`PaperExecutionAdapter` performs local validation and emits synthetic `PAPER-ORD-*` identifiers. It does not submit orders to a live exchange and it does not consume live order credentials.

There is no Live execution adapter or live order-placement implementation in this Phase A boundary.

## Configuration guardrail

`ContainerConfiguration.paper_trading_enabled` is the authoritative Phase A execution-mode gate.

- `True` → the existing `PaperExecutionAdapter` may be constructed.
- `False` → execution-engine construction fails closed with `ContainerError`.

A disabled Paper mode **never** falls back to a Live executor.

The Binance API key, API secret, and testnet settings belong to the market-data/provider configuration path. They are not execution-mode controls and cannot activate live orders through the Paper boundary.

## Accidental-live protection

Any future live execution capability must be introduced through a separately reviewed execution boundary. It must not be selected implicitly by reinterpreting the Phase A `paper_trading_enabled` flag.

Phase A therefore guarantees:

`paper_trading_enabled == False` → **FAIL CLOSED**

No execution adapter or execution engine is constructed after that failure.

## Prohibited behavior

- Live order-placement calls.
- Live order credentials in the Paper adapter.
- Configuration-only activation of Live execution.
- Unknown-decision fallback to `ExecutionSide.NONE` / `SKIPPED`.

## Verification contract

The Execution Composition Root contract tests must prove:

1. default configuration builds `PaperExecutionAdapter`;
2. BUY/SELL behavior remains paper execution;
3. disabling Paper fails closed;
4. disabled Paper does not create an execution adapter or engine;
5. no Live execution fallback exists in this Phase A path.
