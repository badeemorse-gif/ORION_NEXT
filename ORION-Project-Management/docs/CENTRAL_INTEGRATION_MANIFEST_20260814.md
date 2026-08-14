# ORION_NEXT — Central Integration Manifest

## Integration identity
- Base: `main` @ `9a02e4a94ea1fd3b63ecf17209211735ed554c83`
- Integration branch: `integration/final-current-20260814`
- Final package content commit: `324d6ccc2483080e93ffa859558afccb70c9deec`

## Approved package sources
- CORE: `phase2/core-intelligence-hardening` @ `3b37ad94d3440463f4e440c7e46ca0380d7ce900`
- EXECUTION: `ops/execution-fail-closed` @ `1ae3cca91f7b58e221e7e005f7949aceb1e96b02`
- OPPORTUNITY: `future/opportunity-intelligence-complete` @ `0257a339f5f1725e424cf0cc3f83806d1faf4588`

## Integrated scope

### CORE
- `ORION-Project-Management/docs/CORE_INTELLIGENCE_HANDOFF.md`
- `ORION-Project-Management/docs/CORE_INTELLIGENCE_HARDENING_COMPLETION.md`
- `ORION-Project-Management/docs/CORE_INTELLIGENCE_INTEGRATION_MAP.md`
- `binansScanner/core/intelligence_contract.md`
- `binansScanner/core/intelligence_contract.py`
- `binansScanner/core/orchestrator.py`
- `binansScanner/core/orchestrator_intelligence_gate.py`
- `binansScanner/core/profile_intelligence.py`
- `binansScanner/core/score_decision_semantics.py`
- `binansScanner/engines/analysis_engine.py`
- `binansScanner/engines/decision_engine.py`
- `binansScanner/engines/indicator_engine.py`
- `binansScanner/engines/profile_builder.py`
- `binansScanner/engines/score_engine.py`
- Approved Core contract/completion tests.

### EXECUTION
- `binansScanner/EXECUTION_BOUNDARY.md`
- `binansScanner/core/execution_plan_builder.py`
- `binansScanner/docs/EXECUTION_INTEGRATION_HANDOFF.md`
- `binansScanner/engines/execution_engine.py`
- `binansScanner/engines/report_engine.py`
- `binansScanner/models/execution.py`
- Approved Execution contract tests.

### OPPORTUNITY
- `ORION-Project-Management/docs/OPPORTUNITY_CONFIDENCE_FIX.md`
- `ORION-Project-Management/docs/OPPORTUNITY_HANDOFF.md`
- `ORION-Project-Management/docs/ORION_FUTURE_TRADING_INTELLIGENCE_CONTRACTS.md`
- `ORION_FUTURE_OPPORTUNITY_INTELLIGENCE.md`
- `binansScanner/engines/opportunity_intelligence.py`
- `binansScanner/models/opportunity.py`
- `binansScanner/models/explosive_watchlist.py`
- `binansScanner/models/opportunity_candidate_set.py`
- `binansScanner/models/opportunity_evaluation.py`
- `binansScanner/models/trading_readiness.py`
- Approved Opportunity contract/integration tests.

## Shared-path decision
`binansScanner/core/orchestrator.py` is CORE-authoritative. It owns the runtime intelligence gates and produces the canonical `ExecutionPlan`; Execution consumes that plan and does not own Core orchestration.

## Explicit exclusions
- Sync/Restore tooling and protocol changes.
- MAIN/ALL tooling and GUI collateral.
- Backups and generated artifacts.
- Unrelated GUI/tooling.
- Cross-package pipeline tests and ancestry collateral.
- Any Opportunity source collateral outside the files listed above.

## Truth rule
Every file named in this manifest must exist in the integration Git tree. No file outside approved package scope is admitted by this manifest.

## Status
Package-scope integration content is assembled from the current `main` baseline and the three approved package HEADs without merging branch history.
