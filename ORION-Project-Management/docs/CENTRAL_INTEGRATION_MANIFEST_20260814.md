# ORION_NEXT — Central Integration Manifest

## Integration identity
- Base: `main` @ `9a02e4a94ea1fd3b63ecf17209211735ed554c83`
- Integration branch: `integration/final-current-20260814`
- Package content HEAD: `447d82dc50806352df5ff361a502d669d2cc481c`

## Approved package sources
- CORE: `phase2/core-intelligence-hardening` @ `3b37ad94d3440463f4e440c7e46ca0380d7ce900`
- EXECUTION: `ops/execution-fail-closed` @ `1ae3cca91f7b58e221e7e005f7949aceb1e96b02`
- OPPORTUNITY: `future/opportunity-intelligence-complete` @ `0257a339f5f1725e424cf0cc3f83806d1faf4588`

## Actual integrated Opportunity package
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

## Core and Execution integration
Core, Execution, and approved tests/docs remain integrated as previously established. Shared `binansScanner/core/orchestrator.py` remains CORE-authoritative.

## Explicit exclusions
- Sync/Restore tooling and protocol changes.
- MAIN/ALL tooling and GUI collateral.
- Backups and generated artifacts.
- Unrelated GUI/tooling.
- Cross-package pipeline tests and ancestry collateral.
- Any Opportunity source collateral outside the files listed above.

## Truth rule
Every file named in this manifest is required to exist in the final integration Git tree. No file outside approved package scope is admitted by this manifest.

## Opportunity confidence
`Opportunity.confidence` is sourced only from the requested `ProfileResult.TimeframeProfile.confidence`. `AnalysisResult.strength` is not substituted or aggregated.
