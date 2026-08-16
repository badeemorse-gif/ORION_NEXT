# ORION — Phase A Experiment Harness

## Purpose

This harness is an **observation-only** experimental layer for signal-accuracy and score-calibration studies. It does not alter Production intelligence, decision, execution, or reporting contracts.

## Baseline

`c54dc67792776da905a3efb1f667c1869c15db3d`

## Experiment unit

Each experiment is built from a deterministic `ExperimentFixture`:

- fixed fixture id, symbol, UTC start time, seed, and hourly OHLCV tape;
- identical inputs produce an identical fixture fingerprint;
- no network, exchange, cache, or live market dependency.

## Observation contract

`Observation` is immutable and represents the signal **at `emitted_at` only**.

It contains:

- signal identity and direction;
- confidence and entry price;
- point-in-time context values;
- timestamps for context fields.

Every context timestamp must be `<= emitted_at`. The entry price must equal the fixture close at `emitted_at`.

Forward values, outcome labels, MFE, and MAE are not stored in the observation itself. They are calculated later from candles strictly after the signal timestamp.

## Forward outcomes

Supported horizons are exactly:

- `1h`
- `4h`
- `24h`

The forward window starts at the first candle strictly after `emitted_at` and ends at the candle at the requested horizon.

`return_pct` is direction-adjusted. For BUY it is `(future_close - entry) / entry`; for SELL it is `(entry - future_close) / entry`.

MFE and MAE are non-negative excursion magnitudes measured over the complete future window. MFE uses the favorable side of high/low for the direction; MAE uses the adverse side.

## Replay / comparison

`ExperimentHarness.replay()` rebuilds observations from the same fixture and `ObservationSpec` values. `ExperimentHarness.compare()` returns explicit mismatches instead of silently accepting drift.

Observation identifiers are deterministic hashes of the fixture, point-in-time metadata, and signal context.

## Future-leakage guard

The harness rejects:

- future context timestamps;
- non-UTC timestamps;
- non-finite numeric values;
- observations whose entry price does not match the signal-time close;
- forward windows that do not have the required future history.

## Execution isolation

The harness has `EXECUTION_ENABLED = False` and exposes an explicit `execute()` guard that always raises `ExecutionDisabledError`.

The harness imports no execution engine, exchange adapter, provider, or network client. It is therefore unsuitable for both live trading and paper execution by construction.

## Verification

Contract tests live in `tools/tests/test_experiment_harness.py` and the dedicated GitHub Actions workflow is `.github/workflows/orion-developer5-experiment-harness.yml`.

No Production file is modified by Phase A.
