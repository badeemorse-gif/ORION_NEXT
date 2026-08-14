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

## Public boundary guarantees
- Indicator provenance is explicit and required at the Profile boundary.
- Incomplete/invalid Analysis fails closed to neutral diagnostics.
- Profile validity/tradeability is required before Score.
- Score is finite/bounded and category-consistent.
- Decision is finite/bounded, semantically consistent with Analysis/Score, and WAIT has zero actionable confidence.

## Runtime order
`Download → Validation → Indicators → Analysis → Profile → Score → Decision`

## Contract ownership
`models.*` own result contracts. `core.intelligence_contract` is the single semantic guard. Engines do not define duplicate downstream contracts.

## Exclusions
Execution, Opportunity, Sync/Restore, MAIN/ALL and future Trading Intelligence are outside Core scope.
