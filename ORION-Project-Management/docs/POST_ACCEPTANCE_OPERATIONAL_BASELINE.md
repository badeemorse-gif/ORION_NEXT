# ORION_NEXT — POST-ACCEPTANCE OPERATIONAL BASELINE

## Purpose

This document freezes the exact project state at the transition from completed engineering/integration work to the next operational phase (Trading/Bot Readiness). It is a leadership handoff record, not a new development specification.

## Accepted Engineering Baseline

**Final accepted integration branch**

`integration/final-release-20260815`

**Final accepted HEAD**

`c54dc67792776da905a3efb1f667c1869c15db3d`

This HEAD is the release baseline for the completed engineering phase.

## Final Local Materialization

The local materialization was rebuilt cleanly from the Integration branch and verified against GitHub.

Verified state:

- Branch: `integration/final-release-20260815`
- Local HEAD: `c54dc67792776da905a3efb1f667c1869c15db3d`
- Remote HEAD: `c54dc67792776da905a3efb1f667c1869c15db3d`
- Working tree: CLEAN

Therefore the locally tested tree and the accepted GitHub Integration HEAD were identical at final verification.

## Final Verification Evidence

The official entry point used from `binansScanner` was:

`python verify.py`

The final run reported:

`Ran 222 tests in 1.905s`

`OK`

`VERIFICATION PASSED`

This proves the completed engineering baseline passed the current repository syntax compilation and full unittest suite.

## Engineering Gates

The following engineering gates were closed during the completed phase:

- D1 Core: APPROVED
- D2 Execution: APPROVED
- D3 Opportunity: APPROVED / FROZEN
- D4 Materialization: APPROVED / FROZEN
- D5 Verification / E2E: APPROVED
- D6 Reporting: APPROVED / FROZEN
- D7 Data Quality: APPROVED / FROZEN
- Central Integration Round 8: APPROVED
- Final Materialization: VERIFIED
- Full Verification: 222/222 PASS
- Final Acceptance: APPROVED

## What We Have in Hand Now

The project currently has a reviewed, integrated, locally materialized and fully verified ORION_NEXT engineering baseline containing the approved Core, Execution, Opportunity, Reporting, Data Quality, Verification/E2E and integration contracts that were exercised by the final test suite.

The current baseline also contains the operationally relevant execution semantics that were verified during integration, including:

- `FAVORABLE -> BUY`
- `UNFAVORABLE -> SELL`
- `WAIT -> HOLD -> quantity=0 -> SKIPPED`
- `UNKNOWN / UNSPECIFIED -> rejected / fail-closed`
- required intelligence timeframes `1d + 4h + 1h`
- Failure Evidence remains distinct from pipeline success

These statements are frozen as the accepted engineering baseline unless a new change request is explicitly opened.

## What Is NOT Yet Proven by Final Acceptance

Final Acceptance of the engineering baseline does **not** by itself prove production/live-trading readiness.

The following operational matters were not established merely by the 222-test engineering verification and must be treated as a separate phase:

- live exchange credentials and secret handling
- live exchange connectivity and market-data behavior under real conditions
- real order submission/cancellation behavior
- rate limits, retries, network failure recovery and reconnect behavior
- operational monitoring/alerting
- process supervision, startup/shutdown and crash recovery
- deployment packaging and runtime environment validation
- paper-trading performance and behavioral observation
- live-trading controls, capital/risk limits and operational runbooks

Therefore **Live Trading is NOT declared APPROVED by this document**.

## Post-Acceptance Roadmap — Mandatory Order

The next operational work is explicitly ordered and must not be collapsed into a single release.

### Phase A — Data Accuracy / Score Calibration Gate

**Status: NEXT / NOT YET VERIFIED**

Before launching the Paper Trading Bot, leadership must first test whether ORION's numeric outputs are comparable and behaviorally meaningful across different coins and market contexts.

The central question is:

> Can two coins with the same raw score (for example, `100` and `100`) represent materially different market situations, and can raw absolute values therefore mislead ranking or confidence decisions?

This phase must explicitly evaluate:

- the meaning and numeric range of every relevant Score and Confidence value
- whether each metric is **absolute** or **relative/contextual**
- comparability across coins with very different price, market size, liquidity and volatility
- **Raw Score** versus contextual/relative measurements
- relative volume / volume expansion
- relative volatility / volatility expansion
- liquidity quality or suitable liquidity proxies
- momentum and multi-timeframe alignment
- market-regime context
- percentile/rank normalization where appropriate
- whether a `Score=90` in one coin has materially the same significance as `Score=90` in another
- whether high Confidence is empirically related to better outcomes or is only an internal model value

The evaluation dataset should capture, at minimum, for each observed signal/opportunity:

- timestamp
- symbol
- raw score
- confidence
- market regime
- volume / turnover where available
- relative volume
- volatility / ATR or equivalent
- relative volatility
- liquidity measure/proxy
- relevant timeframe context
- 1h forward outcome
- 4h forward outcome
- 24h forward outcome
- Maximum Favorable Excursion (MFE)
- Maximum Adverse Excursion (MAE)

The goal of this gate is **not** to prove trading profitability yet. It is to establish whether the signal metrics are measurable, comparable and sufficiently calibrated to justify Paper Trading.

No Paper Trading launch is APPROVED until this gate is passed by leadership.

### Phase B — Paper Trading Bot

**Status: BLOCKED until Phase A is APPROVED**

Run the experimental trading bot without real-money execution.

Operationally, an initial 2–3 day run is acceptable as a **smoke / operational trial**, not by itself as proof of trading competence.

During the run, record every decision, signal, confidence, execution intent, and subsequent market outcome so that the result is auditable.

The operational trial must answer whether the bot:

- receives and processes market data correctly
- avoids stale/duplicate data
- remains stable over the observation window
- produces coherent decisions
- respects the approved WAIT/HOLD/SKIPPED behavior
- maintains an auditable signal-to-outcome trail

A separate statistical performance gate is required once enough observations exist. A 2–3 day profitable result alone is not sufficient for Live Trading approval.

### Phase C — Statistical Performance Validation

**Status: BLOCKED until Phase B evidence exists**

Evaluate whether observed performance is persistent enough to justify progressing toward live operation.

Metrics should include, as applicable:

- signal count and opportunity frequency
- win rate / precision
- profit factor
- maximum drawdown
- MFE / MAE distributions
- performance by confidence/score bucket
- performance by market regime
- consistency across different coins/timeframes
- confidence calibration / reliability

A key desired property is approximately monotonic behavior: higher score/confidence buckets should demonstrate systematically stronger forward outcomes rather than merely producing impressive-looking numbers.

### Phase D — Live Trading Bot Candidate

**Status: NOT APPROVED**

Only after the paper and statistical gates pass may leadership consider cloning the approved paper bot into a live-trading candidate.

The live candidate requires a new operational readiness review covering at minimum:

- live credentials and secret handling
- order submission, modification and cancellation
- exchange/network failure handling
- rate limits and retries
- startup/shutdown and crash recovery
- monitoring and alerting
- position/risk/capital limits
- safe-mode / kill-switch behavior
- deployment and runtime validation
- operational runbook

The live candidate must be treated as a new change set and must not modify the accepted engineering baseline in place.

### Phase E — Explosion Discovery Bot

**Status: CANDIDATE / DESIGN NOT YET STARTED**

A separate non-trading bot may be evaluated for identifying coins that enter a high-probability **pre-explosion / abnormal-move** condition before the move occurs.

This bot is explicitly **alert/ranking only** in its initial phase. It must not execute trades.

The initial conceptual output is a ranked list such as:

- symbol
- Explosion Score
- supporting factors
- relevant timeframe
- observation timestamp
- expected evaluation horizon

Potential factors to investigate include, only where supported by the data and later validated:

- volume expansion
- volatility compression followed by acceleration
- momentum acceleration
- multi-timeframe alignment
- abnormal activity
- breakout proximity
- liquidity conditions

The term “pre-explosion” is a hypothesis to be tested, not a promise that a coin will explode. The bot must be evaluated prospectively by recording its alert time and later measuring actual forward movement.

The Explosion Discovery Bot is independent from the trading execution path until leadership explicitly approves any future integration.

## Mandatory Phase Boundary

The post-acceptance order is:

`Phase A — Data Accuracy / Score Calibration`

`→ Phase B — Paper Trading`

`→ Phase C — Statistical Performance Validation`

`→ Phase D — Live Trading Candidate`

with `Phase E — Explosion Discovery Bot` running as a separate research/alert track when formally opened.

No phase may be skipped merely because an earlier phase produced an encouraging short-term result.

## Governance Rules for This Phase

- The accepted engineering baseline remains frozen.
- All operational/readiness implementation must branch from the accepted HEAD or an explicitly approved post-acceptance branch.
- No engineer may silently modify `integration/final-release-20260815`.
- Trading/live behavior requires new change sets, owners, Definition of Done, review and verification evidence.
- Paper results are evidence, not proof of profitability.
- Raw Score/Confidence values must not be treated as calibrated probabilities unless empirical validation establishes that relationship.
- Any live-trading decision requires an explicit leadership approval after all required gates.

## Source-of-Truth Rule

For the completed engineering phase, the immutable reference point is:

`integration/final-release-20260815 @ c54dc67792776da905a3efb1f667c1869c15db3d`

The operational-readiness phase uses this exact HEAD as its baseline and must not rewrite the accepted history.

## Leadership Decision at Transition

**Engineering Final Acceptance = APPROVED.**

**Phase A — Data Accuracy / Score Calibration = NEXT.**

**Trading/Bot Readiness = NOT YET VERIFIED.**

**Paper Trading = BLOCKED until Phase A approval.**

**Live Trading = NOT APPROVED.**

**Explosion Discovery Bot = CANDIDATE / SEPARATE RESEARCH TRACK.**
