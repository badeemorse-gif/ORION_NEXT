# ORION — Real-Time Market, Order Lifecycle, and Signal Revalidation Specification

**Status:** Forward architecture requirement; not yet an implementation approval.
**Baseline:** `main@0359ee7435c7372077e861ad89d36f4f96fb879f`
**Scope:** Paper Bot first, then Real Bot parity.

## 1. Purpose

The Paper Bot is the operational rehearsal for the future Real Bot. Therefore, after the intelligence layer is considered accurate enough, the Paper Bot must model the same order-lifecycle semantics that the Real Bot will use, with the execution adapter being the boundary that changes between paper and real environments.

A successful Paper Bot must not be considered sufficient merely because the pipeline can produce `BUY`/`SELL` decisions. It must prove correct behavior for pending orders, fills, open positions, exits, cancellation/replacement, and continuous signal revalidation.

## 2. Current Phase A boundary

The current Phase A composition root is paper-only. `paper_trading_enabled == false` fails closed, and the current `PaperExecutionAdapter` creates synthetic `PAPER-ORD-*` executions without contacting a live exchange. This current safety boundary remains unchanged during the present integration/6-hour verification activity.

This document does **not** authorize Live execution and does **not** change the current Phase A execution boundary.

## 3. Real-time market ingestion requirement

The final trading architecture shall be **event-driven / real-time**, not dependent on a long polling interval for safety-critical decisions.

Requirements:

- Market data shall be ingested continuously from an appropriate real-time stream or equivalent low-latency source.
- Safety-sensitive order and position state shall be re-evaluated on relevant market events without waiting for a five-minute scanner cycle.
- The system shall not blindly recompute every intelligence stage on every tick. Event routing and timeframe-aware recomputation shall determine what must be recalculated.
- Candle/timeframe intelligence may continue to operate on timeframe semantics (for example, 1h analysis), while order/position supervision remains continuously responsive.

The current scanner default of `refresh_interval_seconds=300` is therefore an integration/test setting and is not the target real-time execution architecture.

## 4. Signal lifecycle

Every actionable signal shall carry a versioned/snapshotted identity sufficient to determine whether a pending order is still valid.

Minimum conceptual state:

`SIGNAL_SNAPSHOT → ENTRY_PLAN → PENDING_ORDER → FILL → OPEN_POSITION → EXIT → CLOSED`

A signal snapshot shall be treated as stale when the market context, entry price, decision state, or signal validity window has changed enough that the original entry no longer represents the current opportunity.

## 5. Pending-order revalidation

A pending entry order must be revalidated whenever relevant market or signal events arrive.

Rules:

1. **Signal remains valid and materially consistent:** retain the pending order.
2. **Signal remains the same direction but the entry price materially changes:** cancel the stale order and replace it with the new entry, subject to repricing limits.
3. **Signal changes to `WAIT`, opposite direction, or otherwise invalid:** cancel the pending order; do not allow the stale order to survive.
4. **Signal validity window expires:** cancel the pending order.
5. **Risk guard is breached:** cancel the pending order immediately.
6. **A pending order must not be duplicated by a newer signal for the same symbol/position intent.**

The canonical stale-order rule is therefore:

`OLD PENDING ORDER + NEW MATERIAL SIGNAL CHANGE → CANCEL/REPLACE OR CANCEL`.

## 6. No blind price chasing

Signal revalidation must not turn into unlimited repricing.

The implementation shall define and test explicit controls for:

- maximum repricing count,
- maximum cumulative entry drift,
- minimum signal/confidence change required to reprice,
- signal validity window,
- maximum distance between the proposed entry and current market price.

If the opportunity has moved too far, the correct result may be **NO TRADE** rather than continuously chasing price.

## 7. Entry semantics

The final Paper Bot must distinguish at least:

- marketable execution,
- pending/limit-style entry,
- cancellation,
- replacement.

For a pending/limit-style example:

`BUY LIMIT @ 100`

If price moves `105 → 120` without touching `100`, the order remains unfilled unless invalidated by the revalidation rules.

If price later returns to `100`, it may fill **only if the order is still valid**.

If the signal has become stale before the return to `100`, the old order must already have been cancelled and must not fill.

## 8. Position lifecycle

Once an entry is filled, it is no longer a pending-order problem. The system shall transition to explicit position management:

`OPEN POSITION → HOLD / REDUCE / EXIT / REVERSE`

A new signal must not blindly create another entry against an already-open position. Position policy must determine whether the new information causes hold, resize, exit, or reversal.

## 9. Exit protection

An open position shall have explicit, testable exit semantics, including as applicable:

- stop loss,
- take profit,
- signal-reversal exit,
- risk exit,
- time-based exit.

Exit logic must remain continuously supervised and must not depend solely on a slow intelligence polling interval.

## 10. Single-order / single-intent invariant

For a symbol and strategy intent, the system shall prevent simultaneous stale and replacement entries from coexisting unintentionally.

Example:

`BUY @ 100`

followed by a materially updated `BUY @ 118` must result in:

`cancel 100 → create 118`

not:

`pending 100 + pending 118`.

The invariant must be enforced by tests and by the runtime state model, not only by caller discipline.

## 11. Paper-to-Real parity requirement

The future Real Bot shall preserve the same order-lifecycle and signal-revalidation state machine proven in Paper.

The expected architecture is:

`Signal/Market State → Order/Position State Machine → Execution Boundary`

The Paper and Real implementations may differ in exchange I/O, credentials, and broker/exchange adapter details, but they must preserve the same externally observable lifecycle semantics and safety invariants.

A Real Bot shall **not** be created by bypassing Paper lifecycle logic or by adding live execution directly to the existing Phase A composition root.

## 12. Mandatory test cases before Real Bot approval

At minimum, the Paper Bot must test and prove:

1. Pending BUY remains pending when price has not touched the entry.
2. Price touches a still-valid entry → exactly one fill.
3. Price crosses the entry after signal expiry → no fill from the stale order.
4. New BUY signal with materially changed entry → old pending cancelled and replacement created.
5. New `WAIT`/SELL signal → old pending BUY cancelled.
6. No duplicate pending orders for the same intent.
7. Filled position receives stop-loss/take-profit/reversal handling.
8. New signals do not create uncontrolled duplicate positions.
9. Repricing limits prevent unlimited price chasing.
10. Runtime remains responsive to market events without waiting for the scanner's long polling interval.

## 13. Release gate

The following are release blockers for a Real Bot:

- no proven pending-order lifecycle,
- no proven stale-signal cancellation/replacement,
- no proven single-intent invariant,
- no proven position/exit lifecycle,
- no real-time supervision for safety-sensitive order/position state,
- any path that can activate Live execution by configuration alone.

This document is a design/verification requirement. Implementation must be delivered as a separately reviewed package and must not be inferred as complete merely because these requirements are documented.
