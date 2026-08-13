# ORION Core Intelligence Integration Map

Canonical chain: `Indicator → Analysis → Profile → Score → Decision`.

This document is the single integration map for runtime inputs/outputs, validation gates, fail-closed behavior, allowed states, and rejected states. It does not introduce a second domain contract.

## Indicator → Analysis

**Input**: canonical `MarketDataset` / OHLCV dataframe per timeframe.

**Output**: the dataset after indicator processing, carrying calculated indicators plus `DataFrame.attrs["indicator_result"]` with canonical `IndicatorResult` provenance.

**Gate**: `IndicatorEngine` validates OHLCV structure, completes canonical indicator calculation, validates required indicators, and validates Profile-critical latest-bar values as finite numeric data.

**Fail-closed**: calculation or validation failure raises the Indicator-layer error; downstream Analysis does not run.

**Allowed**: valid OHLCV + successful indicator calculation + truthful provenance.

**Rejected**: invalid OHLCV, missing required/Profile-critical indicators, missing/invalid provenance, NaN/Inf/non-numeric critical latest values.

## Market Intelligence → Profile

**Input**: canonical `MarketDataset` after indicator processing, with validated indicator provenance. `ProfileEngine` reads the dataset and `ProfileBuilder` produces timeframe market characteristics.

**Output**: canonical `ProfileResult` from `models.profile`.

**Gate**: ProfileBuilder requires real `IndicatorResult` metadata with `quality="SUFFICIENT"`, no failed indicators, calculated critical indicators present, and finite critical latest values. ProfileEngine remains read-only with respect to `MarketDataset`/`TimeframeData`. `validate_profile()` verifies canonical ProfileResult semantics.

**Fail-closed**: missing/invalid provenance, malformed profile data, incomplete coverage, non-finite characteristics, invalid timeframe/statistics, extreme-risk directional intelligence, or warning-bearing/non-tradeable profiles are blocked.

**Allowed**: valid, tradeable ProfileResult with coherent timeframe/statistics data and no blocking warnings.

**Rejected**: every failed, partial, malformed, or non-actionable case above.

## Analysis → Score

**Input**: validated `AnalysisResult`. Profile validity is enforced by the preceding runtime gate; `ScoreEngine` consumes the canonical AnalysisResult contract only.

**Output**: `ScoreResult`.

**Gate**: score finite and within `[-100,100]`; category matches canonical thresholds; factors/warnings are string lists; `NEUTRAL` analysis state cannot gain direction from strength magnitude alone.

**Fail-closed**: invalid Analysis/Score state raises the intelligence contract error and cannot become actionable.

**Allowed**: finite, bounded ScoreResult with coherent category.

**Rejected**: NaN/Inf/non-numeric/out-of-range score, category mismatch, malformed factors/warnings.

## Score + Analysis → Decision

**Input**: validated AnalysisResult + validated ScoreResult.

**Output**: `DecisionResult`.

**Gate**: decision is `FAVORABLE`, `UNFAVORABLE`, or `WAIT`; confidence finite `[0,100]`; WAIT confidence is exactly `0.0`; FAVORABLE requires `BULLISH + STRONG_BULLISH + score >= 60`; UNFAVORABLE requires `BEARISH + STRONG_BEARISH + score <= -60`.

**Fail-closed**: invalid inputs or semantic contradictions raise the intelligence contract error. Non-actionable conditions remain WAIT with zero actionable confidence.

**Allowed**: semantically coherent DecisionResult matching both Analysis and Score.

**Rejected**: invalid decision, invalid confidence, WAIT with non-zero confidence, or any Analysis/Score contradiction.

## Runtime Orchestration

`Orchestrator.run_pipeline()` follows `Download → Validation → Indicators → Analysis → Profile → Score → Decision`.

Runtime gates are applied after Analysis, Profile, Score, and Decision. A failed stage stops downstream stages. Only after Decision validation succeeds does the existing execution-plan preparation run.

## Integration Invariants

- `models.*` remain the domain-result contract owners.
- `core.intelligence_contract` is the single cross-layer semantic guard.
- Downstream validation does not depend on hidden engine internals.
- Indicator provenance is carried explicitly through `IndicatorResult` metadata.
- ProfileBuilder calculations require indicator-validated input explicitly at its boundary.
- Execution, Opportunity, Sync/Restore, and MAIN/ALL are outside this package.
