# ORION_NEXT — FINAL INTEGRATION MANIFEST

## Integration identity
- Base: `main` @ `9a02e4a94ea1fd3b63ecf17209211735ed554c83`
- Integration branch: `integration/final-current-20260814`
- Core source: `phase2/core-intelligence-hardening` @ `3b37ad94d3440463f4e440c7e46ca0380d7ce900`
- Execution source: `ops/execution-fail-closed` @ `1ae3cca91f7b58e221e7e005f7949aceb1e96b02`
- Opportunity source: `future/opportunity-intelligence-complete` @ `0257a339f5f1725e424cf0cc3f83806d1faf4588`

## Core package — included deltas
- `ORION-Project-Management/docs/CORE_INTELLIGENCE_HANDOFF.md` — authoritative Core handoff.
- `ORION-Project-Management/docs/CORE_INTELLIGENCE_HARDENING_COMPLETION.md` — completion contract.
- `ORION-Project-Management/docs/CORE_INTELLIGENCE_INTEGRATION_MAP.md` — canonical transition map.
- `binansScanner/core/intelligence_contract.md` — contract reference.
- `binansScanner/core/intelligence_contract.py` — single cross-layer semantic guard.
- `binansScanner/core/orchestrator_intelligence_gate.py` — orchestration adapter for the guard.
- `binansScanner/core/profile_intelligence.py` — fail-closed profile intelligence.
- `binansScanner/core/score_decision_semantics.py` — score/decision semantic guard.
- `binansScanner/core/orchestrator.py` — CORE-authoritative runtime sequencing and gates.
- `binansScanner/engines/indicator_engine.py` — indicator boundary.
- `binansScanner/engines/analysis_engine.py` — AnalysisResult producer.
- `binansScanner/engines/profile_engine.py` — ProfileResult coordinator.
- `binansScanner/engines/profile_builder.py` — indicator provenance/profile validation boundary.
- `binansScanner/engines/score_engine.py` — ScoreResult producer.
- `binansScanner/engines/decision_engine.py` — DecisionResult producer.
- `binansScanner/tests/test_analysis_contract.py` — Analysis contract coverage.
- `binansScanner/tests/test_core_intelligence_completion_contract.py` — Core cross-layer completion coverage.
- `binansScanner/tests/test_decision_contract.py` — Decision contract coverage.
- `binansScanner/tests/test_indicator_contract.py` — Indicator contract coverage.
- `binansScanner/tests/test_intelligence_contract.py` — semantic guard coverage.
- `binansScanner/tests/test_profile_contract.py` — Profile contract coverage.
- `binansScanner/tests/test_profile_intelligence.py` — Profile Intelligence coverage.
- `binansScanner/tests/test_profile_intelligence_completion_contract.py` — completion coverage.
- `binansScanner/tests/test_score_contract.py` — Score contract coverage.

## Execution package — included deltas
- `binansScanner/EXECUTION_BOUNDARY.md` — Execution boundary contract.
- `binansScanner/docs/EXECUTION_INTEGRATION_HANDOFF.md` — authoritative Execution handoff.
- `binansScanner/core/execution_plan_builder.py` — Decision → ExecutionPlan translation boundary.
- `binansScanner/engines/execution_engine.py` — ExecutionPlan-only execution boundary.
- `binansScanner/engines/report_engine.py` — failed-execution report rejection boundary.
- `binansScanner/models/execution.py` — Execution domain contract.
- `binansScanner/tests/test_execution_composition_root.py` — composition-root execution coverage.
- `binansScanner/tests/test_execution_fail_closed_boundary.py` — execution fail-closed coverage.
- `binansScanner/tests/test_execution_validation_contract.py` — execution validation coverage.

Shared `binansScanner/core/orchestrator.py` is CORE-owned and is never replaced by the Execution source branch.

## Opportunity package — included deltas
- `ORION-Project-Management/docs/OPPORTUNITY_CONFIDENCE_FIX.md` — canonical confidence semantics.
- `ORION-Project-Management/docs/OPPORTUNITY_HANDOFF.md` — Opportunity handoff.
- `ORION-Project-Management/docs/ORION_FUTURE_TRADING_INTELLIGENCE_CONTRACTS.md` — future contract baseline.
- `ORION_FUTURE_OPPORTUNITY_INTELLIGENCE.md` — Opportunity implementation contract.
- `binansScanner/engines/opportunity_intelligence.py` — Opportunity generator/selection implementation.
- `binansScanner/models/opportunity.py` — Opportunity contract.
- `binansScanner/models/explosive_watchlist.py` — independent watchlist contract.
- `binansScanner/models/opportunity_candidate_set.py` — candidate-set contract.
- `binansScanner/models/opportunity_evaluation.py` — evaluation contract.
- `binansScanner/models/trading_readiness.py` — readiness contract.
- `binansScanner/tests/test_future_trading_intelligence_contract.py` — future contract tests.
- `binansScanner/tests/test_opportunity_candidate_set_contract.py` — candidate-set tests.
- `binansScanner/tests/test_opportunity_confidence_contract.py` — canonical confidence tests.
- `binansScanner/tests/test_opportunity_evaluation_contract.py` — evaluation tests.
- `binansScanner/tests/test_opportunity_integration_fixes.py` — timeframe/risk/selection tests.

## Excluded scopes
- Sync/Restore tooling or protocol changes.
- MAIN/ALL tooling and GUI collateral.
- Backups and generated artifacts.
- Unrelated GUI/tooling.
- Cross-package pipeline tests and ancestry collateral.
- Opportunity source collateral outside the list above.
- Execution-branch changes to Core-owned shared files.

## Truth rule
Every file listed above is required to exist in the final integration tree. Unlisted files may remain only when they are part of the unchanged current `main` baseline; they are not considered package-integrated changes.

## Opportunity confidence invariant
`Opportunity.confidence` comes only from the requested `ProfileResult.TimeframeProfile.confidence`. `AnalysisResult.strength` is not substituted or aggregated.
