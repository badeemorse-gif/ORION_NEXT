# ORION Future Risk, Universe & Control Center Policy

## Purpose

This document records a future product/policy requirement discovered during Phase A calibration. It is a **planning and governance document only**.

It does **not** change the current Production Risk semantics, Profile semantics, Opportunity eligibility, Score/Decision semantics, or Execution behavior.

The current fail-closed contracts remain authoritative until a separately approved redesign is implemented and verified.

## 1. Risk Must Be Separated From Signal Existence

A high-risk or extreme-risk market condition must not be interpreted as proof that no market signal exists.

The desired future product model is:

```text
Market Data
    ↓
Signal Analysis
    ↓
Signal Strength / Context
    ↓
Risk Assessment
    ↓
Trade Gate
```

The future system should be able to distinguish:

```text
SIGNAL DETECTED
        ≠
TRADE APPROVED
```

A strong signal in a high-risk market may remain valuable as analytical evidence even when automatic trading is blocked.

### Future risk presentation

Examples of the intended semantics:

```text
Strong Signal + Low Risk
→ Trade Candidate

Strong Signal + High Risk
→ Strong Signal / High Risk / Restricted Trade

Strong Signal + Extreme Risk
→ Signal Detected / Trade Blocked / Watchlist Candidate
```

This does **not** authorize bypassing the current `EXTREME` fail-closed Production contract. The redesign must be implemented only as a separately approved policy change.

## 2. Extreme Risk Should Be Observable Even When Trading Is Blocked

Future ORION behavior should preserve the distinction between:

- **signal detection**,
- **risk classification**, and
- **execution eligibility**.

An `EXTREME` risk state should not automatically erase the analytical event from all monitoring surfaces.

The intended future UX is approximately:

```text
ADAUSDT
Strong Signal Detected
Risk: EXTREME
Trade: BLOCKED
Reason: Extreme market risk
```

This allows ORION to learn from and audit important market events without weakening the safety gate.

## 3. New Listings Must Not Be Permanently Hidden Merely Because They Are New

A new or recently listed asset should not be excluded forever solely because it is new.

The future policy should distinguish:

```text
NEW LISTING
+
INSUFFICIENT HISTORY
→ insufficient evidence / no automatic trade
```

from:

```text
NEW LISTING
+
SUFFICIENT VALID HISTORY
+
VALID DATA QUALITY
→ eligible for normal analysis subject to risk policy
```

The system must never invent missing history, interpolate missing candles, forward-fill unsupported history, or fabricate calibration evidence.

Newness is therefore a **data/history state**, not by itself a permanent rejection reason.

## 4. Universe Policy — Binance Spot / USDT

The intended future production universe is:

```text
Binance Spot
    ↓
quoteAsset = USDT
    ↓
status = TRADING
    ↓
policy-based eligibility
    ↓
Market Data Quality Gate
    ↓
ORION Intelligence
```

The current five-asset universe used in Phase A (`BTCUSDT`, `ETHUSDT`, `BNBUSDT`, `SOLUSDT`, `ADAUSDT`) is an experimental calibration cohort and is **not** the intended final universe.

The future universe discovery mechanism should be dynamic rather than maintaining a permanent hard-coded list.

The final eligibility policy must remain evidence-based. It should be possible to exclude an asset because of concrete contract violations such as insufficient history, invalid data, missing required timeframes, stale/invalid provenance, or another explicitly approved policy gate.

## 5. Data Sufficiency for New Assets

A newly listed USDT spot pair becomes a valid analysis candidate only after it satisfies the required historical-data contract for the relevant analysis policy.

The system must record a deterministic reason when a symbol is excluded, for example:

```text
INSUFFICIENT_HISTORY
MISSING_REQUIRED_TIMEFRAME
INVALID_DATA
STALE_DATA
PROVENANCE_INVALID
RISK_POLICY_BLOCKED
```

The distinction between **data exclusion** and **trade-risk blocking** must remain explicit in the audit trail.

## 6. Future Control Center Requirements

The eventual ORION desktop control center should expose these states directly rather than collapsing them into a single `tradable / not tradable` flag.

Recommended signal-board columns include:

```text
Symbol
Timeframe
Signal
Raw Score
Confidence
Relative Context
Risk
Trade Status
Reason
Data Status
```

Example:

| Symbol | Signal | Risk | Trade Status | Explanation |
|---|---|---|---|---|
| BTCUSDT | WAIT | LOW | — | No directional edge |
| SOLUSDT | STRONG BUY | HIGH | RESTRICTED | Strong signal, elevated risk |
| ADAUSDT | STRONG SIGNAL | EXTREME | BLOCKED | Signal detected, trade blocked |
| NEWCOINUSDT | STRONG SIGNAL | HIGH | NO AUTO TRADE | Insufficient history |

## 7. Explosive Watchlist Interaction

A future Explosive Watchlist may surface strong signals that are not execution-eligible.

The watchlist must clearly label itself as **ALERT / ANALYTICS ONLY** when a candidate is blocked by risk, data insufficiency, or another safety gate.

The watchlist must not silently turn a blocked signal into an execution intent.

## 8. GUI Safety Principle

The future interface may control the universe, observation, paper trading, and live trading from one control center, but the execution engines must remain technically separated.

The GUI must not create a hidden bypass around:

- Risk gates
- Data-quality gates
- Opportunity eligibility
- Paper/Live separation
- Kill-switch behavior
- Audit requirements

A visible signal and an executable trade must remain distinct concepts in both the UI and the underlying architecture.

## 9. Required Future Implementation Sequence

This policy is intentionally deferred. The recommended order is:

```text
Phase A calibration evidence
        ↓
Risk-policy redesign decision
        ↓
Dynamic Binance Spot / USDT universe discovery
        ↓
New-listing history policy
        ↓
Risk-aware signal presentation
        ↓
Explosive Watchlist integration
        ↓
Control Center UI
        ↓
Paper Trading expansion
        ↓
Live Trading only after independent safety approval
```

## 10. Governance Rule

No implementation may change the current fail-closed Production behavior merely to satisfy this future policy document.

Any future change from:

```text
EXTREME → hard block before directional intelligence
```

to a model such as:

```text
EXTREME → signal visible but execution blocked
```

requires a separately reviewed architectural/contract change with dedicated tests and explicit approval.

## Status

`DOCUMENTED — DEFERRED — NO PRODUCTION SEMANTICS CHANGED`
