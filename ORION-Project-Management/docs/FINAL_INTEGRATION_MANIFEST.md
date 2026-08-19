# ORION_NEXT — FINAL INTEGRATION MANIFEST

**Status:** FINAL — ROUND 8 RECONCILED
**Integration branch:** `integration/final-release-20260815`
**Base main:** `9147ea6bf6812c4afda8e0e3e9596b0460b05419`
**Round 8 publication baseline:** `4a693ac30e1d9c6bb2e05f6cdaba9a6ab35727c6`

## Approved package sources

| Owner | Source branch | Current approved HEAD used for this round |
|---|---|---|
| CORE / D1 | `developer1/core-profile-test-reconciliation` | `7a8d5919af865d5d8cc323f56c39a78224327215` |
| EXECUTION / D2 | `ops/execution-fail-closed` | `d98013aff8575adca3ce24f3c6c02aa5b4f242aa` |
| OPPORTUNITY / D3 | `future/opportunity-intelligence-complete` | `9880043b138ae61dc07b1923b2bd40e6f7cee683` |
| D4 | `developer4/sync-restore-final-materialization` | `a47d8ff429772debc0285a9b270d408479418977` |
| D5 | `developer5/verification-e2e-parity-final` | `86459cfd873c01a354ecbe675a0132cf12179c15` |
| D6 | `developer6-reporting-auditability` | `abc874aa40c8f3e09dafdf17f0f5587fa151c074` |
| D7 | `developer7-market-data-quality` | `289f273f6217eea4b002101caf6ef6dae9161` |

## Actual inventory

The GitHub comparison from `main @ 9147ea6bf6812c4afda8e0e3e9596b0460b05419` to the current integration state remains **72 net changed paths**. Round 8 changes only the content of two paths already present in the established inventory.

**INCLUDED: 70**  
**EXCLUDED: 2**

## ROUND 6 DELTA LEDGER — AUTHORITATIVE

| Target path | Owner | Source branch | Source HEAD | Source blob SHA | Decision | Reason |
|---|---|---|---|---|---|---|
| `binansScanner/tests/test_profile_intelligence.py` | CORE / D1 | `developer1/core-profile-test-reconciliation` | `7a8d5919af865d5d8cc323f56c39a78224327215` | `18b435c1dc55608d542ea51de6d4a263b8c38b5b` | INCLUDED | Aligns valid directional ProfileIntelligence fixtures to required `1d/4h/1h` without changing fail-closed missing/duplicate/malformed cases. |
| `binansScanner/core/execution_plan_builder.py` | EXECUTION / D2 | `ops/execution-fail-closed` | `d98013aff8575adca3ce24f3c6c02aa5b4f242aa` | `d642486f356b12bc08f47bce07adf7dbfa8c6e10` | INCLUDED | Rejects UNKNOWN/UNSPECIFIED decision metadata before ExecutionPlan creation; canonical FAVORABLE/UNFAVORABLE/WAIT mappings remain unchanged. |
| `binansScanner/tests/test_decision_execution_bridge.py` | EXECUTION / D2 | `ops/execution-fail-closed` | `d98013aff8575adca3ce24f3c6c02aa5b4f242aa` | `b027c98a0a0e03caeb5c17956ba447eed0e686a9` | INCLUDED | Direct contract coverage for UNKNOWN/UNSPECIFIED rejection and canonical BUY/SELL/HOLD behavior. |
| `binansScanner/docs/EXECUTION_UNKNOWN_DECISION_CONTRACT.md` | EXECUTION / D2 | `ops/execution-fail-closed` | `d98013aff8575adca3ce24f3c6c02aa5b4f242aa` | `c886dd438a2b6ebfc88ac068957fd1e2ee2fb1c2` | INCLUDED | Documents the fail-closed UNKNOWN decision boundary and canonical execution mapping. |

## ROUND 7 DELTA LEDGER — AUTHORITATIVE

| Target path | Owner | Source branch | Source HEAD | Source blob SHA | Integration blob SHA | Decision | Reason |
|---|---|---|---|---|---|---|---|
| `binansScanner/tests/test_orchestrator_stage_failure_boundary.py` | D5 | `developer5/verification-e2e-parity-final` | `21440bea1d2e5b86e5cb8b97a90f6d1e2e726c9d` | `635b82c80f03ec61af7e6fc386c2872632e70251` | `635b82c80f03ec61af7e6fc386c2872632e70251` | INCLUDED | Final D5 stage-boundary reconciliation with valid `1d/4h/1h` ProfileResult fixture and downstream fail-fast assertions; exact source identity enforced. |
| `binansScanner/tests/test_orchestrator_validation_order.py` | D5 | `developer5/verification-e2e-parity-final` | `21440bea1d2e5b86e5cb8b97a90f6d1e2e726c9d` | `b190996717a18a2f056bc9170dbcb20450c56680` | `b190996717a18a2f056bc9170dbcb20450c56680` | INCLUDED | Final D5 validation-order reconciliation using canonical AnalysisResult and complete required ProfileResult fixture; exact source identity enforced. Superseded in Round 8 by the approved D5 Round 8 fixture below. |
| `binansScanner/tests/test_pipeline_execution_e2e.py` | D5 | `developer5/verification-e2e-parity-final` | `21440bea1d2e5b86e5cb8b97a90f6d1e2e726c9d` | `a56ec4842494ea6a0c0225b3378a24dd8b191003` | `a56ec4842494ea6a0c0225b3378a24dd8b191003` | INCLUDED | Final D5 E2E reconciliation with complete `1d/4h/1h` ProfileResult fixture, canonical EXECUTED/SKIPPED paths, and preserved Failure Evidence semantics; exact source identity verified. Superseded in Round 8 by the approved D5 Round 8 fixture below. |
| `binansScanner/tests/test_verification_gates.py` | D5 | `developer5/verification-e2e-parity-final` | `21440bea1d2e5b86e5cb8b97a90f6d1e2e726c9d` | `0cc44644bab2370f66fa661005c212cba9c3c558` | `0cc44644bab2370f66fa661005c212cba9c3c558` | INCLUDED | Final D5 verification gates covering ExecutionPlan isolation, canonical decision mappings, valid Profile fixture, E2E execution, and failure evidence semantics without Production changes; exact source identity verified. |

## ROUND 8 DELTA LEDGER — AUTHORITATIVE

| Target path | Owner | Source branch | Source HEAD | Source blob SHA | Integration blob SHA | Decision | Reason |
|---|---|---|---|---|---|---|---|
| `binansScanner/tests/test_orchestrator_validation_order.py` | D5 | `developer5/verification-e2e-parity-final` | `86459cfd873c01a354ecbe675a0132cf12179c15` | `de74433748728bb5c4a835bccdeec5cc381ef8df` | `de74433748728bb5c4a835bccdeec5cc381ef8df` | INCLUDED | Final Round 8 Verification fixture reconciliation for canonical WAIT confidence semantics; complete `1d/4h/1h` profile retained. Production unchanged. |
| `binansScanner/tests/test_pipeline_execution_e2e.py` | D5 | `developer5/verification-e2e-parity-final` | `86459cfd873c01a354ecbe675a0132cf12179c15` | `ea19fe9f8f3c1a0495fb97523f0ff530070ee53c` | `ea19fe9f8f3c1a0495fb97523f0ff530070ee53c` | INCLUDED | Final Round 8 E2E fixture reconciliation for canonical WAIT quantity semantics and canonical favorable analysis/score fixtures. Production unchanged. |

## Shared ownership — final

| Shared file | Owner | Final source decision |
|---|---|---|
| `binansScanner/core/pipeline.py` | D6 | Unchanged in Round 8. |
| `binansScanner/tests/test_pipeline_execution_e2e.py` | D5 | Round 8 approved D5 source identity exact. |
| `binansScanner/tests/test_execution_fail_closed_boundary.py` | D6 | Unchanged in Round 8. |
| `ORION-Project-Management/docs/ORION_CONTROL_INDEX.md` | D1 CENTRAL INTEGRATION | Unchanged in Round 8. |
| `ORION-Project-Management/docs/ORION_PROJECT_STATE.md` | D1 CENTRAL INTEGRATION | Unchanged in Round 8. |

## D2 / D3 publication rule

No D2 or D3 publication was performed in Round 8.

## Excluded collateral

These remain explicitly EXCLUDED:

- `__integration_cleanup_marker__.txt`
- `__integration_probe__.txt`
- `tools/orion_sync.bat`
- `tools/orion_sync_safe.py`
- legacy restore/sync tooling
- backup directories / `.bak` / temporary files
- `binansScanner/models/explosive_watchlist.py`
- unrelated GUI or live/execution wiring outside approved package scope

## Audit status

- Actual net changed paths: **72**
- Included: **70**
- Excluded: **2**
- Round 8 delta paths written: **2**
- Both Round 8 targets were re-read from the Integration branch after publication and their Integration blob SHA equals the approved D5 Round 8 source blob SHA exactly.
- No Production Logic was modified.
- No D1/D2/D3/D4/D6/D7 package was re-published.
- No main/source branch was modified.
