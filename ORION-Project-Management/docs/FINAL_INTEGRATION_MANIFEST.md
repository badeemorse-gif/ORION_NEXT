# ORION_NEXT — FINAL INTEGRATION MANIFEST

**Status:** FINAL — ROUND 5 DELTAS RECONCILED
**Integration branch:** `integration/final-release-20260815`
**Base main:** `9147ea6bf6812c4afda8e0e3e9596b0460b05419`
**Audited integration state before this manifest publication:** `ef51a1a9ef69e889634a68da4c9a73cf1690b1bc`

## Approved package sources

| Owner | Source branch | Current approved HEAD used for this round |
|---|---|---|
| CORE | `phase2/core-intelligence-hardening` | `34b04cc021117b0e712a1dc2a1ff7c751f34948e` |
| EXECUTION / D2 | `ops/execution-fail-closed` | `790eafaa04f335001c792888919921b906753ee5` |
| OPPORTUNITY / D3 | `future/opportunity-intelligence-complete` | `9880043b138ae61dc07b1923b2bd40e6f7cee683` |
| D4 | `developer4/sync-restore-final-materialization` | `a47d8ff429772debc0285a9b270d408479418977` |
| D5 | `developer5/verification-e2e-parity-final` | `a530782a813de4d3c77a3e84a4d2a99c40d0354d` |
| D6 | `developer6-reporting-auditability` | `abc874aa40c8f3e09dafdf17f0f5587fa151c074` |
| D7 | `developer7-market-data-quality` | `289f273f6217eea4b002101caf6ef1356dae9161` |

## Actual inventory

The GitHub comparison from `main @ 9147ea6bf6812c4afda8e0e3e9596b0460b05419` to the post-publication integration state remains **71 net changed paths**. Round 5 changed existing package paths only; it did not introduce a new path outside the established 71-path inventory.

**INCLUDED: 69**  
**EXCLUDED: 2**

The complete 71-path baseline inventory and prior owner/decision records remain the authoritative manifest body above. The following Round 5 ledger **supersedes prior source metadata for the listed paths** and is authoritative for the current publication:

## ROUND 5 DELTA LEDGER — AUTHORITATIVE

| Target path | Owner | Source branch | Source HEAD | Source blob SHA | Decision | Reason |
|---|---|---|---|---|---|---|
| `binansScanner/core/profile_intelligence.py` | CORE | `phase2/core-intelligence-hardening` | `34b04cc021117b0e712a1dc2a1ff7c751f34948e` | `7d5e320a67282704476fb6d34a31b10e6f74981f` | INCLUDED | Required ProfileIntelligence timeframes `1d/4h/1h`; fail-closed gate; verified against approved blob. |
| `binansScanner/tests/test_profile_intelligence_completion_contract.py` | CORE | `phase2/core-intelligence-hardening` | `34b04cc021117b0e712a1dc2a1ff7c751f34948e` | `16312cb3059538440665958f2fa9161b75e58d0d` | INCLUDED | Contract coverage for each missing required timeframe plus complete actionable profile; verified against approved blob. |
| `binansScanner/tests/test_pipeline_execution_e2e.py` | D5 | `developer5/verification-e2e-parity-final` | `a530782a813de4d3c77a3e84a4d2a99c40d0354d` | `615b54c586544d6c7494ee0a9528bb725dc6f2b3` | INCLUDED | Latest D5 zero-quantity fixture reconciliation; preserves original plan builder during quantity-zero fixture execution. |
| `binansScanner/tests/test_execution_fail_closed_boundary.py` | D6 | `developer6-reporting-auditability` | `abc874aa40c8f3e09dafdf17f0f5587fa151c074` | `d5d9a37844e146f15dd5147703c0425d214113f3` | INCLUDED | Final D6 Failure Evidence boundary test; supersedes the older D2 copy for this shared test path. |

## Shared ownership — final

| Shared file | Owner | Final source decision |
|---|---|---|
| `binansScanner/core/pipeline.py` | D6 | Retained previously audited D6 production semantics. |
| `binansScanner/tests/test_pipeline_execution_e2e.py` | D5 | Latest approved D5 verification reconciliation supersedes prior test copy. |
| `binansScanner/tests/test_execution_fail_closed_boundary.py` | D6 | Latest approved D6 reporting/failure-evidence reconciliation supersedes prior D2 copy. |
| `ORION-Project-Management/docs/ORION_CONTROL_INDEX.md` | D1 CENTRAL INTEGRATION | Final shared control ownership retained. |
| `ORION-Project-Management/docs/ORION_PROJECT_STATE.md` | D1 CENTRAL INTEGRATION | Final integrated project state retained. |

## D2 / D3 publication rule

D2 and D3 were **not re-published** in Round 5 because their current integration content was already present; no additional file-level write was required for those packages.

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

- Actual net changed paths: **71**
- Included: **69**
- Excluded: **2**
- Round 5 delta paths written: **4**
- Each Round 5 delta was re-read from the Integration branch after publication and matched its approved source blob exactly.
- No new path was introduced by Round 5.
- No main/source branch was modified.
