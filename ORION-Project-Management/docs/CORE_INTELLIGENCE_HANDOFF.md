# ORION_NEXT — Core Intelligence Integration Handoff

## Exact package state

- Branch: `phase2/core-intelligence-hardening`
- Exact pre-handoff HEAD: `49c799384225e820814a73fe81cfdce710fa8507`
- Handoff document: this file

## Canonical chain

`Indicator → Analysis → Profile → Score → Decision`

## Main implementation files

- `binansScanner/engines/indicator_engine.py` — indicator calculation and boundary validation.
- `binansScanner/engines/analysis_engine.py` — produces `AnalysisResult`.
- `binansScanner/engines/profile_engine.py` — coordinates `ProfileResult` construction without mutating market input.
- `binansScanner/engines/profile_builder.py` — calculates `MarketCharacteristics` and enforces indicator provenance.
- `binansScanner/engines/score_engine.py` — produces `ScoreResult`.
- `binansScanner/engines/decision_engine.py` — produces `DecisionResult`.
- `binansScanner/core/intelligence_contract.py` — single cross-layer semantic guard.
- `binansScanner/core/orchestrator.py` — runtime sequencing and gate enforcement.
- `binansScanner/models/indicators.py` — `IndicatorResult` provenance contract.
- `binansScanner/models/analysis.py` — `AnalysisResult` contract.
- `binansScanner/models/profile.py` — `ProfileResult` and profile-domain contracts.
- `binansScanner/models/score.py` — `ScoreResult` contract.
- `binansScanner/models/decision.py` — `DecisionResult` contract.

## Public contract transitions

### Indicator → Analysis

**Input:** canonical `MarketDataset` / OHLCV timeframe data.

**Output:** indicator-enriched dataset with `DataFrame.attrs["indicator_result"]` containing `IndicatorResult` provenance.

**Gate:** valid OHLCV structure, successful calculation, required/Profile-critical indicators valid, truthful provenance.

**Fail-closed:** indicator calculation or validation failure blocks downstream Analysis.

### Analysis → Profile

**Input:** indicator-validated `MarketDataset`.

**Output:** canonical `AnalysisResult` plus the same validated market dataset available to the next stage.

**Gate:** state is `BULLISH`, `BEARISH`, or `NEUTRAL`; strength is finite and bounded; signals/warnings are string lists; fail-closed warnings cannot coexist with directional state.

**Fail-closed:** incomplete or invalid intelligence remains `NEUTRAL` with zero strength and diagnostics.

### Market Intelligence → Profile

**Input:** indicator-validated `MarketDataset` with explicit provenance.

**Output:** canonical `ProfileResult`.

**Gate:** valid `IndicatorResult`, `SUFFICIENT` quality, no failed indicators, complete critical provenance, finite critical values, valid profile statistics/timeframes.

**Fail-closed:** malformed, incomplete, non-finite, blocked-risk, warning-bearing, or non-tradeable Profile results are rejected.

### Analysis → Score

**Input:** validated `AnalysisResult`. Profile validity has already been enforced by the preceding runtime gate.

**Output:** `ScoreResult`.

**Gate:** finite/bounded score, canonical category thresholds, string-only factors/warnings, no directional inference from `NEUTRAL` magnitude alone.

**Fail-closed:** invalid Analysis/Score semantics cannot become actionable.

### Score + Analysis → Decision

**Input:** validated `AnalysisResult` and validated `ScoreResult`.

**Output:** `DecisionResult`.

**Gate:** decision is `FAVORABLE`, `UNFAVORABLE`, or `WAIT`; confidence finite/bounded; `WAIT` confidence exactly `0.0`; directional decisions require semantically matching Analysis and Score states/thresholds.

**Fail-closed:** contradictions or invalid confidence reject actionable Decision output.

## Runtime gate order

`Download → Validation → Indicators → Analysis → Profile → Score → Decision`

The `Orchestrator` applies runtime gates after Analysis, Profile, Score, and Decision. A failed stage stops downstream stages. Execution-plan preparation remains downstream of the validated Decision and is not a Core Intelligence contract dependency.

## Contract ownership / import model

- `models.*` own the Result/domain contracts.
- `core.intelligence_contract` is the single cross-layer semantic guard.
- Engines produce canonical results and do not define alternate downstream contracts.
- `ProfileBuilder` explicitly requires `IndicatorResult` provenance at its boundary; it does not inspect hidden IndicatorEngine internals.
- Downstream validators operate on public Result contracts rather than private Engine state.
- No duplicate semantic helper is intended to coexist with `core.intelligence_contract`.

## Downstream consumers

- `Orchestrator` consumes the canonical Result contracts and validators.
- `ScoreEngine` consumes `AnalysisResult`.
- `DecisionEngine` consumes `AnalysisResult` and `ScoreResult`.
- Existing execution-plan preparation occurs only after the Decision gate succeeds.

## Integration assumptions

1. Central integration preserves the canonical Result model ownership under `models.*`.
2. Indicator provenance remains available to `ProfileBuilder` through `DataFrame.attrs["indicator_result"]` until the Profile boundary.
3. `core.intelligence_contract` remains the single cross-layer semantic guard.
4. `Orchestrator` stage ordering remains unchanged.
5. No merge/rebase/reset/cherry-pick/force-push or lineage rewrite is required for the handoff.

## Exclusions

Execution, Opportunity, Sync/Restore, MAIN/ALL, and future Trading Intelligence features are outside this handoff.

## Documentation authority

`ORION-Project-Management/docs/CORE_INTELLIGENCE_INTEGRATION_MAP.md` remains the canonical transition map. This document records the exact branch/HEAD, implementation ownership, downstream consumers, and assumptions needed for central integration.
