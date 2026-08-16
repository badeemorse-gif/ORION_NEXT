# ORION Phase A — Paper Execution Safety Boundary

## Scope

This document defines the execution safety boundary for Phase A signal-accuracy / score-calibration work.

Phase A is **paper-only**. It may create canonical `ExecutionPlan` objects and run them through `PaperExecutionAdapter`, but it must not expose a configuration path that silently activates live order execution.

## Canonical decision semantics

- `FAVORABLE` → `BUY`
- `UNFAVORABLE` → `SELL`
- `WAIT` → `HOLD` with `quantity=0` → `SKIPPED`
- `UNKNOWN` / `UNSPECIFIED` → rejected before `ExecutionPlan` creation

These semantics are unchanged.

## Entry points reviewed

The current execution path is:

`DecisionResult → ExecutionPlanBuilder → ExecutionEngine → ExecutionAdapter`

The composition root currently creates only `PaperExecutionAdapter` for the execution boundary.

`PaperExecutionAdapter` validates the request locally and returns synthetic `PAPER-ORD-*` identifiers. It does not contact a live exchange.

## Paper / Live separation

The current repository does not contain a `LiveExecutionAdapter` or a live order-placement implementation. Consequently, live order submission is not an available execution path in this Phase A branch.

The composition root now enforces this explicitly: when `paper_trading_enabled` is false, execution-engine construction fails closed with `ContainerError` rather than selecting or inventing a live executor.

This means a future live implementation cannot be activated merely by changing an existing boolean configuration value.

## Configuration paths reviewed

### `ORION_TRADING_PAPER_TRADING`

This value is loaded into `ContainerConfiguration.paper_trading_enabled`.

- `true`: the current composition root creates `PaperExecutionAdapter`.
- `false`: the current composition root refuses to build an execution engine.

There is no fallback from `false` to a live executor.

### Binance credentials

`ORION_BINANCE_API_KEY` and `ORION_BINANCE_API_SECRET` are accepted by `BinanceSettings` and passed to `BinanceProvider` for the market-data/provider layer.

Those credentials are **not** used by `PaperExecutionAdapter` and cannot turn paper execution into live order placement.

### `ORION_BINANCE_TESTNET`

This setting controls the Binance provider configuration used by the market-data/provider layer. It is not an execution-mode switch.

A value of `false` therefore does not activate live orders in the current execution boundary. Paper execution remains Paper execution.

## Explicit guardrail

The composition root is the authoritative execution-mode gate for the current phase:

`paper_trading_enabled == False` → **FAIL CLOSED**

No live execution adapter is registered, constructed, or selected by configuration.

Any future live execution must introduce a separately reviewed execution boundary rather than reusing this Phase A paper path as an implicit bridge.

## Prohibited Phase A behavior

- No live credentials are required for execution.
- No live order-placement API is called.
- No live adapter is instantiated.
- No configuration-only switch can activate live execution.
- No `ExecutionSide.NONE` fallback is allowed for unknown decisions.

## Verification requirements

The execution composition-root tests must prove:

1. default composition creates `PaperExecutionAdapter`;
2. BUY and SELL still execute through the paper adapter;
3. disabling paper trading fails closed at composition-root construction;
4. no execution adapter or execution engine is created after that failure.
