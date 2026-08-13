# ORION Core Intelligence Integration Map

Single integration map for the canonical chain:

`Indicator → Analysis → Profile → Score → Decision`

This document describes the real runtime inputs, outputs, validation gates, fail-closed behavior, allowed states, and rejected states without introducing a second domain contract.

## Indicator → Analysis

**Input**: canonical `MarketDataset` / OHLCV dataframe per timeframe.

**Output**: the same dataset with calculated indicators plus `DataFrame.attrs["indicator_result"]` carrying canonical `IndicatorResult` provenance.

**Gate**: `IndicatorEngine` validates dataframe structure/OHLCV, completes canonical indicator calculation, validates required indicators, and validates Profile-critical latest-bar values as finite numeric data.

**Fail-closed**: calculation or validation failure raises `IndicatorEngineError` / `InvalidIndicatorData`; downstream Analysis does not run.

**Allowed**: valid OHLCV + successful indicator calculation + truthful provenance.

**Rejected**: invalid OHLCV, missing required/profile-critical indicators, missing/invalid provenance, NaN/Inf/non-numeric critical latest values.

## Analysis → Profile

**Input**: canonical `MarketDataset` after indicator processing.

**Output**: `AnalysisResult`.

**Gate**: market state must be `BULLISH`, `BEARISH`, or `NEUTRAL`; strength must be finite `[0,100]`; signals/warnings must be string lists; fail-closed warnings cannot coexist with directional state.

**Fail-closed**: missing/invalid required indicators return `NEUTRAL` with `strength=0.0` and diagnostic warnings/signals.

**Allowed**: structurally valid AnalysisResult whose state is semantically consistent with its warnings.

**Rejected**: invalid state, invalid strength, malformed signal/warning collections, or directional state carrying fail-closed warnings.

## Analysis/Data → Profile

**Input**: canonical `MarketDataset` with validated indicator provenance.

**Output**: canonical `ProfileResult` from `models.profile`.

**Gate**: ProfileBuilder requires real `IndicatorResult` metadata with `quality="SUFFICIENT"`, no failed indicators, calculated critical indicators present, and finite critical latest values. ProfileEngine remains read-only with respect to MarketDataset/TimeframeData. `validate_profile()` additionally verifies canonical ProfileResult semantics.

**Fail-closed**: missing/invalid indicator provenance, malformed profile data, incomplete coverage, non-finite characteristics, invalid timeframe/statistics, extreme-risk directional intelligence, or warning-bearing/non-tradeable profiles are blocked.

**Allowed**: valid, tradeable ProfileResult with coherent timeframe/statistics data and no blocking warnings.

**Rejected**: every failed/partial/invalid case above.

## Profile/Analysis → Score

**Input**: validated AnalysisResult; validated ProfileResult as the upstream intelligence gate.

**Output**: `ScoreResult`.

**Gate**: score finite and within `[-100,100]`; score category must match canonical thresholds; factors/warnings must be string lists; NEUTRAL analysis state cannot gain direction from strength magnitude alone.

**Fail-closed**: invalid Analysis/Score state raises an intelligence contract error and cannot become actionable.

**Allowed**: finite, bounded ScoreResult with coherent category.

**Rejected**: NaN/Inf/non-numeric/out-of-range score, category mismatch, malformed factors/warnings.

## Score + Analysis → Decision

**Input**: validated AnalysisResult + validated ScoreResult.

**Output**: `DecisionResult`.

**Gate**: decision is `FAVORABLE`, `UNFAVORABLE`, or `WAIT`; confidence finite `[0,100]`; WAIT confidence must be exactly `0.0`; FAVORABLE requires `BULLISH + STRONG_BULLISH + score >= 60`; UNFAVORABLE requires `BEARISH + STRONG_BEARISH + score <= -60`.

**Fail-closed**: invalid inputs or semantic contradictions raise an intelligence contract error. Non-actionable conditions remain WAIT with zero actionable confidence.

**Allowed**: semantically coherent DecisionResult matching both Analysis and Score.

**Rejected**: invalid decision, invalid confidence, WAIT with non-zero confidence, or any Analysis/Score contradiction.

## Runtime Orchestration

`Orchestrator.run_pipeline()` follows the canonical order:

`Download → Validation → Indicators → Analysis → Profile → Score → Decision`.

Runtime gates are applied after Analysis, Profile, Score, and Decision. A failed stage stops all downstream stages. Only after Decision validation succeeds is the existing execution-plan preparation invoked.

## Integration Invariants

- `models.*` remain the domain-result contract owners.
- `core.intelligence_contract` is the single cross-layer semantic guard.
- Engine implementations are not used as hidden contract definitions by downstream validation.
- Indicator provenance is carried explicitly through `IndicatorResult` metadata.
- ProfileBuilder is permitted to calculate only from an indicator-validated dataframe; its direct intelligence precondition is explicit in its validation path.
- No Execution, Opportunity, Sync/Restore, or MAIN/ALL behavior belongs to this integration map.
