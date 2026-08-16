# ORION_NEXT — PHASE A — SIGNAL ACCURACY / SCORE CALIBRATION DEVELOPER PLAN

## Baseline

Accepted Engineering Baseline:

`integration/final-release-20260815 @ c54dc67792776da905a3efb1f667c1869c15db3d`

This baseline is frozen. Phase A work must not rewrite or modify the accepted integration history.

## Phase Objective

Determine whether ORION_NEXT signal values are comparable, interpretable and empirically useful across different assets and market regimes before Paper Trading begins.

Phase A is not a profitability claim and does not approve live trading.

## Core Questions

1. Do raw Score and Confidence remain comparable across assets of very different size, liquidity and volatility?
2. Does a high score actually correspond to better forward outcomes than a lower score?
3. Are absolute values being mistaken for relative strength?
4. Can Volume, Volatility, Momentum and other features be normalized or expressed relative to an appropriate peer/market context?
5. Is Confidence calibrated, or is it only an internal model score?
6. Does performance change materially by market regime, timeframe or liquidity class?

## Required Observation Fields

Each observed signal should be traceable by at least:

- timestamp
- symbol
- timeframe
- raw score
- confidence
- decision
- market regime
- volume / turnover
- relative volume
- volatility / ATR proxy
- relative volatility
- liquidity proxy
- momentum / directional context
- multi-timeframe alignment
- forward 1h outcome
- forward 4h outcome
- forward 24h outcome
- MFE
- MAE

## Calibration Rules

- Raw Score is not treated as a probability of success.
- Confidence is not treated as a probability until empirically calibrated.
- Cross-asset comparison must account for asset context; identical raw scores do not automatically imply identical opportunity quality.
- Relative rank/percentile should be evaluated alongside absolute values.
- No Paper Trading launch is approved from a short positive P&L result alone.
- Two to three days may serve as an operational smoke test only; statistical acceptance requires enough observations to support a meaningful conclusion.

## Developer Ownership

### D1 — Core Intelligence / Score Semantics

Mission: audit and define how Core Analysis/Profile/Score values should be interpreted for cross-asset comparison and calibration. Identify absolute-vs-relative measurement risks without weakening existing production contracts.

### D2 — Execution / Paper Boundary

Mission: define the paper-execution boundary and ensure Phase A observations cannot accidentally place live orders. Preserve live execution semantics as frozen until a later approval gate.

### D3 — Opportunity Intelligence / Ranking

Mission: design asset-relative opportunity ranking and investigate whether a raw score of 100 means comparable opportunity quality across assets. Define contextual ranking inputs without implementing live trading behavior.

### D4 — Materialization / Runtime Operations

Mission: define a clean operational observation workflow: run configuration, snapshot identity, start/stop state, reproducibility and artifact location. No synchronization redesign.

### D5 — Verification / E2E / Experiment Harness

Mission: build the Phase A verification harness and repeatable experiment fixtures needed to collect and compare signal observations without modifying core production semantics.

### D6 — Reporting / Auditability

Mission: define the signal journal and audit record that stores every observed signal and later outcome so that score/confidence calibration can be measured objectively.

### D7 — Market Data Quality

Mission: audit data completeness, freshness, liquidity and normalization quality across the asset universe used in Phase A. Prevent misleading rankings caused by bad or incomparable input data.

## Dependencies

D7 and D4 establish observation/data integrity foundations.
D1 and D3 define interpretation/ranking requirements.
D6 defines the persistent observation record.
D5 validates the experiment harness and evidence path.
D2 remains a safety boundary and must not be used to enable live trading.

## Phase Gate

Phase A is APPROVED only when leadership confirms:

- observation schema is stable
- data quality requirements are met
- cross-asset comparison method is explicit
- score/confidence semantics are measurable
- observation/replay process is repeatable
- paper trading is still prevented from starting until leadership issues a separate launch decision

## Freeze Rule

No developer may modify the accepted engineering baseline branch. All Phase A implementation belongs on independent post-acceptance branches and must be reviewed before any integration into operational-readiness work.
