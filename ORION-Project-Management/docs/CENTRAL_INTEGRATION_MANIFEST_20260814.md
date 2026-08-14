# ORION_NEXT — Central Integration Manifest

## Integration identity
- Base: `main` @ `9a02e4a94ea1fd3b63ecf17209211735ed554c83`
- Integration branch: `integration/final-current-20260814`
- FINAL HEAD: `0783c97b4165416c4a5bfc45320ec9601ff9e077`

## Approved package sources
- CORE: `phase2/core-intelligence-hardening` @ `3b37ad94d3440463f4e440c7e46ca0380d7ce900`
- EXECUTION: `ops/execution-fail-closed` @ `1ae3cca91f7b58e221e7e005f7949aceb1e96b02`
- OPPORTUNITY: `future/opportunity-intelligence-complete` @ `0257a339f5f1725e424cf0cc3f83806d1faf4588`

## Integrated scope — actual package files

### CORE
- `ORION-Project-Management/docs/CORE_INTELLIGENCE_HANDOFF.md`
- `ORION-Project-Management/docs/CORE_INTELLIGENCE_HARDENING_COMPLETION.md`
- `ORION-Project-Management/docs/CORE_INTELLIGENCE_INTEGRATION_MAP.md`
- `binansScanner/core/intelligence_contract.md`
- `binansScanner/core/intelligence_contract.py`
- `binansScanner/core/orchestrator.py` (CORE-authoritative shared path)
- `binansScanner/core/orchestrator_intelligence_gate.py`
- `binansScanner/core/profile_intelligence.py`
- `binansScanner/core/score_decision_semantics.py`
- `binansScanner/engines/analysis_engine.py`
- `binansScanner/engines/decision_engine.py`
- `binansScanner/engines/indicator_engine.py`
- `binansScanner/engines/profile_builder.py`
- `binansScanner/engines/score_engine.py`
- `binansScanner/tests/test_analysis_contract.py`
- `binansScanner/tests/test_core_intelligence_completion_contract.py`
- `binansScanner/tests/test_decision_contract.py`
- `binansScanner/tests/test_indicator_contract.py`
- `binansScanner/tests/test_intelligence_contract.py`
- `binansScanner/tests/test_profile_contract.py`
- `binansScanner/tests/test_profile_intelligence.py`
- `binansScanner/tests/test_profile_intelligence_completion_contract.py`
- `binansScanner/tests/test_score_contract.py`

### EXECUTION
- `binansScanner/EXECUTION_BOUNDARY.md`
- `binansScanner/core/execution_plan_builder.py`
- `binansScanner/docs/EXECUTION_INTEGRATION_HANDOFF.md`
- `binansScanner/engines/execution_engine.py`
- `binansScanner/engines/report_engine.py`
- `binansScanner/models/execution.py`
- `binansScanner/tests/test_decision_execution_bridge.py`
- `binansScanner/tests/test_execution_composition_root.py`
- `binansScanner/tests/test_execution_fail_closed_boundary.py`
- `binansScanner/tests/test_execution_validation_contract.py`

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
- `binansScanner/tests/test_future_trading_intelligence_contract.py`
- `binansScanner/tests/test_opportunity_candidate_set_contract.py`
- `binansScanner/tests/test_opportunity_confidence_contract.py`
- `binansScanner/tests/test_opportunity_evaluation_contract.py`
- `binansScanner/tests/test_opportunity_integration_fixes.py`

## Truth and conflict policy
- Only files in this manifest are package-scope integration inputs.
- Shared `binansScanner/core/orchestrator.py` uses the CORE-authoritative version.
- Opportunity confidence is canonical `TimeframeProfile.confidence`; `AnalysisResult.strength` is never substituted or aggregated.
- No Opportunity source tooling, Sync/Restore, MAIN/ALL, backup, artifact, GUI collateral, or cross-package pipeline test was integrated.

## Verification state
The branch ref was checked directly in GitHub and points to `0783c97b4165416c4a5bfc45320ec9601ff9e077`. Manifest/tree parity is an exact acceptance requirement; local verification is intentionally outside this executor's scope.
