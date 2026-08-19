# ORION — Signal Journal Contract

**Phase:** A — Signal Accuracy / Score Calibration  
**Owner:** Developer 6 — Reporting / Auditability / Diagnostics  
**Status:** ACTIVE — Experimental Evidence Boundary  
**Baseline:** `c54dc67792776da905a3efb1f667c1869c15db3d`

## 1. Purpose

The Signal Journal is the experimental source of truth for evaluating signal accuracy and score calibration.

For every observed signal, the journal must make it possible to answer:

- What did ORION observe?
- What did ORION say?
- Why did ORION say it?
- What happened afterward?

The journal is an evidence and audit boundary. It does not modify `ReportResult` semantics and does not participate in live trading or decision generation.

## 2. Canonical record shape

A journal entry contains two explicitly separated sections:

```text
SignalJournalEntry
├── observation   ← signal-time evidence only
└── outcome       ← retrospective label/measurement, optional and later
```

### Signal-time observation

The observation schema is `models.signal_journal.SignalObservation` and contains exactly the following evidence fields:

| Field | Provenance | Meaning |
|---|---|---|
| `timestamp` | SIGNAL_TIME_OBSERVED | Time at which the observation is recorded |
| `symbol` | SIGNAL_TIME_OBSERVED | Instrument observed |
| `timeframe` | SIGNAL_TIME_OBSERVED | Signal timeframe |
| `raw_score` | SIGNAL_TIME_OBSERVED | Score value available at signal time |
| `confidence` | SIGNAL_TIME_OBSERVED | Confidence value available at signal time |
| `decision` | SIGNAL_TIME_OBSERVED | Decision available at signal time |
| `market_regime` | SIGNAL_TIME_OBSERVED | Regime evidence available at signal time |
| `volume` | SIGNAL_TIME_OBSERVED | Volume evidence available at signal time |
| `relative_volume` | SIGNAL_TIME_OBSERVED | Relative-volume evidence available at signal time |
| `volatility` | SIGNAL_TIME_OBSERVED | Volatility evidence available at signal time |
| `relative_volatility` | SIGNAL_TIME_OBSERVED | Relative-volatility evidence available at signal time |
| `liquidity` | SIGNAL_TIME_OBSERVED | Liquidity evidence available at signal time |
| `momentum` | SIGNAL_TIME_OBSERVED | Momentum evidence available at signal time |
| `multi_timeframe_alignment` | SIGNAL_TIME_OBSERVED | Alignment evidence available at signal time |
| `reasons` | SIGNAL_TIME_OBSERVED | Evidence explanations available at signal time |

A value may be `None` when the corresponding evidence is unavailable. The schema does not substitute fabricated defaults.

## 3. Retrospective outcome

The outcome schema is `models.signal_journal.SignalOutcome`.

It contains:

- `outcome_1h`
- `outcome_4h`
- `outcome_24h`
- `mfe`
- `mae`
- `metric_unit`
- `outcome_timestamp`

All outcome fields have provenance `RETROSPECTIVE_LABEL`.

Outcome labels are intentionally opaque strings. The journal does **not** invent a win/loss rule, return formula, threshold, forecast target, or calibration policy.

`mfe` and `mae` are scalar retrospective measurements. Their unit must be supplied explicitly through `metric_unit`; this contract does not define a calculation formula or a unit conversion.

`outcome_timestamp` identifies when the retrospective label/measurement set was recorded. It must not precede the signal observation timestamp.

## 4. No future leakage

The core invariant is:

```text
Observed Evidence
≠
Retrospective Label
```

`SignalObservation.to_dict()` contains only signal-time observation fields. Outcome fields are structurally absent from that representation.

A later outcome may be attached through `SignalJournalEntry.outcome`, but that outcome remains explicitly separated from the original observation.

The journal rejects an outcome whose `outcome_timestamp` precedes the observation timestamp.

The observation model is immutable so signal-time evidence cannot be rewritten after the fact.

## 5. Auditability

`SignalJournalEntry.to_dict()` serializes the observation and retrospective outcome as separate objects:

```json
{
  "observation": {"...": "signal-time evidence"},
  "outcome": {"...": "retrospective evidence"}
}
```

This separation preserves provenance during later calibration analysis.

## 6. Scope boundaries

This contract does not:

- modify `ReportResult` semantics;
- generate new Core Intelligence;
- alter Score / Decision formulas;
- introduce ranking thresholds;
- perform live trading;
- connect the journal to execution;
- infer outcome labels from future data during signal creation.

The journal is a data/evidence contract only. Integration into a live pipeline or automatic persistence layer requires a separate approved change.

## 7. Contract tests

`binansScanner/tests/test_signal_journal_contract.py` proves:

- all required observation fields exist;
- signal-time provenance is explicit;
- retrospective provenance is explicit;
- outcome data stays separate from observation data;
- future timestamps cannot be attached backward in time;
- MFE/MAE require an explicit unit;
- signal observations are immutable.

END
