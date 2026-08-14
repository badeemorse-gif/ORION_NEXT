# ORION Core Intelligence Integration Map

Canonical chain: `Indicator → Analysis → Profile → Score → Decision`.

This document is the single integration map for runtime inputs/outputs, validation gates, fail-closed behavior, allowed states, and rejected states. It does not introduce a second domain contract.

## Indicator → Analysis
Input: canonical `MarketDataset` / OHLCV dataframe per timeframe.
Output: indicator-enriched dataset carrying calculated indicators plus `DataFrame.attrs["indicator_result"]` provenance.
Gate: valid OHLCV structure, successful indicator calculation, required/Profile-critical indicators valid and finite.
Fail-closed: calculation or validation failure blocks downstream Analysis.

## Market Intelligence → Profile
Input: indicator-validated `MarketDataset` with explicit provenance.
Output: canonical `ProfileResult`.
Gate: valid `IndicatorResult`, `SUFFICIENT` quality, no failed indicators, complete critical provenance, finite critical values and coherent statistics/timeframes.
Fail-closed: malformed, incomplete, non-finite, blocked-risk, warning-bearing or non-tradeable Profile results are blocked.

## Analysis → Score
Input: validated `AnalysisResult`.
Output: `ScoreResult`.
Gate: finite/bounded score, category consistency, string-only factors/warnings, and no directional inference from NEUTRAL magnitude alone.
Fail-closed: invalid Analysis/Score semantics cannot become actionable.

## Score + Analysis → Decision
Input: validated AnalysisResult + validated ScoreResult.
Output: `DecisionResult`.
Gate: FAVORABLE/UNFAVORABLE/WAIT; confidence finite [0,100]; WAIT confidence exactly 0; directional decisions must match Analysis and Strong Score semantics.
Fail-closed: invalid inputs or contradictions block actionable Decision output.

## Runtime orchestration
`Orchestrator.run_pipeline()` follows `Download → Validation → Indicators → Analysis → Profile → Score → Decision`, applying validation gates before downstream stages. Execution-plan preparation runs only after Decision validation succeeds.

## Integration invariants
- `models.*` remain domain-result contract owners.
- `core.intelligence_contract` is the single cross-layer semantic guard.
- Indicator provenance is explicit.
- Execution, Opportunity, Sync/Restore and MAIN/ALL remain outside this package.
