# PHASE A — D6 TASK

Role: Reporting / Auditability

Baseline: `c54dc67792776da905a3efb1f667c1869c15db3d`

Objective: define the signal journal that records every observation and later market outcome so score/confidence calibration can be measured objectively.

Scope:
- define canonical signal observation record
- preserve raw score, confidence, decision, context and reasons
- record forward outcomes at 1h, 4h and 24h
- record MFE/MAE and outcome timestamps
- preserve enough metadata to audit exactly what the bot knew at signal time
- distinguish observed evidence from retrospective labels

Forbidden:
- no live trading
- no modification of accepted Integration branch
- no silent changes to existing ReportResult semantics unless separately approved

Definition of Done:
- signal journal schema documented
- field meanings and provenance explicit
- forward outcome and evidence semantics documented
- no accidental leakage of future information into signal-time records
- final GitHub report only