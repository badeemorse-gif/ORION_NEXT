# ORION_NEXT — FINAL INTEGRATION MANIFEST

## Integration identity
- Base: `main` @ `9a02e4a94ea1fd3b63ecf17209211735ed554c83`
- Integration branch: `integration/final-current-20260814`
- FINAL HEAD: `2f6477d60a30744b307b62bea9b01142bd50f3d3`
- Core source: `phase2/core-intelligence-hardening` @ `3b37ad94d3440463f4e440c7e46ca0380d7ce900`
- Execution source: `ops/execution-fail-closed` @ `1ae3cca91f7b58e221e7e005f7949aceb1e96b02`
- Opportunity source: `future/opportunity-intelligence-complete` @ `0257a339f5f1725e424cf0cc3f83806d1faf4588`

## Core package — included deltas
- `ORION-Project-Management/docs/CORE_INTELLIGENCE_HANDOFF.md`
- `ORION-Project-Management/docs/CORE_INTELLIGENCE_HARDENING_COMPLETION.md`
- `ORION-Project-Management/docs/CORE_INTELLIGENCE_INTEGRATION_MAP.md`
- `binansScanner/core/intelligence_contract.md`
- `binansScanner/core/intelligence_contract.py`
- `binansScanner/core/orchestrator_intelligence_gate.py`
- `binansScanner/core/profile_intelligence.py`
- `binansScanner/core/score_decision_semantics.py`
- `binansScanner/core/orchestrator.py`
- `binansScanner/engines/indicator_engine.py`
- `binansScanner/engines/analysis_engine.py`
- `binansScanner/engines/profile_engine.py`
- `binansScanner/engines/profile_builder.py`
- `binansScanner/engines/score_engine.py`
- `binansScanner/engines/decision_engine.py`
- `binansScanner/tests/test_analysis_contract.py`
- `binansScanner/tests/test_core_intelligence_completion_contract.py`
- `binansScanner/tests/test_decision_contract.py`
- `binansScanner/tests/test_indicator_contract.py`
- `binansScanner/tests/test_intelligence_contract.py`
- `binansScanner/tests/test_profile_contract.py`
- `binansScanner/tests/test_profile_intelligence.py`
- `binansScanner/tests/test_profile_intelligence_completion_contract.py`
- `binansScanner/tests/test_score_contract.py`

## Execution package — included deltas
- `binansScanner/EXECUTION_BOUNDARY.md`
- `binansScanner/docs/EXECUTION_INTEGRATION_HANDOFF.md`
- `binansScanner/core/execution_plan_builder.py`
- `binansScanner/engines/execution_engine.py`
- `binansScanner/engines/report_engine.py`
- `binansScanner/models/execution.py`
- `binansScanner/tests/test_execution_composition_root.py`
- `binansScanner/tests/test_execution_fail_closed_boundary.py`
- `binansScanner/tests/test_execution_validation_contract.py`

Shared `binansScanner/core/orchestrator.py` is Core-owned; Execution does not replace it.

## Opportunity package — included deltas
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
- `binansScanner/tests/test_future_trading_intelligence_contract.py`
- `binansScanner/tests/test_opportunity_candidate_set_contract.py`
- `binansScanner/tests/test_opportunity_confidence_contract.py`
- `binansScanner/tests/test_opportunity_evaluation_contract.py`
- `binansScanner/tests/test_opportunity_integration_fixes.py`

## Excluded scopes
- Sync/Restore tooling or protocol changes.
- MAIN/ALL tooling and GUI collateral.
- Backups and generated artifacts.
- Unrelated GUI/tooling.
- Cross-package pipeline wiring not explicitly listed above.
- Opportunity source collateral outside the list above.
- Execution-branch changes to Core-owned shared files.

## Truth rule
Every file listed above is required to exist in the final integration Git tree. Unlisted files are accepted only when they are part of the unchanged current `main` baseline; they are not package-integrated deltas.

## Opportunity confidence invariant
`Opportunity.confidence` comes only from the requested `ProfileResult.TimeframeProfile.confidence`. `AnalysisResult.strength` is never substituted or aggregated.
