# ORION_NEXT — Core Intelligence Integration Handoff

## Exact package state

- Branch: `phase2/core-intelligence-hardening`
- Approved HEAD: `3b37ad94d3440463f4e440c7e46ca0380d7ce900`

## Canonical chain

`Indicator → Analysis → Profile → Score → Decision`

## Main implementation files

- `binansScanner/engines/indicator_engine.py`
- `binansScanner/engines/analysis_engine.py`
- `binansScanner/engines/profile_engine.py`
- `binansScanner/engines/profile_builder.py`
- `binansScanner/engines/score_engine.py`
- `binansScanner/engines/decision_engine.py`
- `binansScanner/core/intelligence_contract.py`
- `binansScanner/core/orchestrator.py`
- `binansScanner/models/indicators.py`
- `binansScanner/models/analysis.py`
- `binansScanner/models/profile.py`
- `binansScanner/models/score.py`
- `binansScanner/models/decision.py`

## Runtime gates

`Download → Validation → Indicators → Analysis → Profile → Score → Decision`

The orchestrator applies validation gates after Analysis, Profile, Score, and Decision. A failed gate blocks downstream stages. Execution-plan preparation remains downstream of a validated Decision and is outside the Core contract.

## Contract ownership

- `models.*` own canonical Result/domain contracts.
- `core.intelligence_contract` is the single cross-layer semantic guard.
- Engines produce canonical results and do not create alternate downstream contracts.
- `ProfileBuilder` explicitly requires `IndicatorResult` provenance.

## Fail-closed guarantees

Missing/invalid indicators, malformed provenance, incomplete profile coverage, non-finite values, warning-bearing directional results, score/category contradictions, and Decision/Analysis/Score contradictions cannot become actionable intelligence.

## Exclusions

Execution, Opportunity, Sync/Restore, MAIN/ALL, and future Trading Intelligence features are outside this package.
