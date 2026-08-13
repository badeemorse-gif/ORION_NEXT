# ORION_NEXT — Central Integration Manifest

## Integration identity
- Base: `main`
- Base content baseline at integration start: `a831bd3c3f3e8aa7ca4e051eda245fb48641daf3`
- Integration branch: `integration/final-current-20260814`
- Integration package commit: `894a14b085599d5a2fe3e9454320f70200d90044`

## Approved package sources
- CORE: `phase2/core-intelligence-hardening` @ `3b37ad94d3440463f4e440c7e46ca0380c7e46ca0380d7ce900`
- EXECUTION: `ops/execution-fail-closed` @ `1ae3cca91f7b58e221e7e005f7949aceb1e96b02`
- OPPORTUNITY: `future/opportunity-intelligence-complete` @ `4975292572a8446a1786a5d1afe708792082767a1`

## Package scope applied

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
- Core contract/completion test files from the approved handoff.

### EXECUTION
- `binansScanner/EXECUTION_BOUNDARY.md`
- `binansScanner/core/execution_plan_builder.py`
- `binansScanner/docs/EXECUTION_INTEGRATION_HANDOFF.md`
- `binansScanner/engines/execution_engine.py`
- `binansScanner/engines/report_engine.py`
- `binansScanner/models/execution.py`
- Execution contract test files from the approved handoff.

### OPPORTUNITY
- `ORION-Project-Management/docs/OPPORTUNITY_HANDOFF.md`
- `ORION-Project-Management/docs/ORION_FUTURE_TRADING_INTELLIGENCE_CONTRACTS.md`
- `ORION_FUTURE_OPPORTUNITY_INTELLIGENCE.md`
- `binansScanner/engines/opportunity_intelligence.py`
- `binansScanner/models/opportunity.py`
- `binansScanner/models/explosive_watchlist.py`
- `binansScanner/models/opportunity_candidate_set.py`
- `binansScanner/models/opportunity_evaluation.py`
- `binansScanner/models/trading_readiness.py`
- Opportunity contract test files from the approved handoff.

## Shared-path decision
`binansScanner/core/orchestrator.py` differed across CORE and EXECUTION. The CORE version was selected because Core owns the Intelligence runtime gates and already constructs the canonical `ExecutionPlan`; Execution consumes that plan and does not own Core orchestration.

Execution-branch edits to Core engines/tests were excluded as collateral. Core versions remain authoritative for those shared Core paths.

## Explicit exclusions
- Sync/Restore tooling and protocol changes.
- MAIN/ALL tooling and GUI collateral.
- Backup directories and generated artifacts.
- Global documentation changes that are ancestry collateral rather than package-owned handoff scope.
- Execution-branch changes to Core Intelligence files.
- Opportunity tooling changes and current-pipeline wiring.
- Cross-package `test_pipeline_execution_e2e.py` changes from source branches.

## Final status
Package-scope integration tree was committed at `894a14b085599d5a2fe3e9454320f70200d90044`.
