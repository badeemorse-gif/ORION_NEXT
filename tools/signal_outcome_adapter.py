"""Experimental D5 adapter to the existing D6 SignalOutcome contract.

This module defines no new SignalOutcome type. It only projects the
experimental ForwardOutcome/ForwardOutcomeRecord data into the canonical
D6 class when that contract is available at integration time.
"""

from __future__ import annotations

from datetime import datetime
from importlib import import_module
from typing import TYPE_CHECKING, Any

from tools.forward_outcome_validation import ForwardOutcomeRecord

if TYPE_CHECKING:
    from binansScanner.models.signal_journal import SignalOutcome


METRIC_UNIT = "PCT"


def to_signal_outcome(
    record: ForwardOutcomeRecord,
    observation_timestamp: datetime,
) -> "SignalOutcome":
    """Map an experimental D5 record to the existing D6 SignalOutcome.

    D6 has one MFE/MAE pair and one outcome timestamp, so the canonical
    handoff uses the 24h measurement for those fields. Detailed per-horizon
    values remain available on the original D5 record.
    """
    outcome_24h = record.outcome("24h")
    if outcome_24h.as_of <= observation_timestamp:
        raise ValueError("outcome_timestamp must be strictly after observation timestamp")

    signal_journal = import_module("binansScanner.models.signal_journal")
    signal_outcome_cls: Any = getattr(signal_journal, "SignalOutcome")
    return signal_outcome_cls(
        outcome_1h=record.outcome("1h").return_pct,
        outcome_4h=record.outcome("4h").return_pct,
        outcome_24h=outcome_24h.return_pct,
        mfe=outcome_24h.mfe_pct,
        mae=outcome_24h.mae_pct,
        outcome_timestamp=outcome_24h.as_of,
        metric_unit=METRIC_UNIT,
    )


__all__ = ["METRIC_UNIT", "to_signal_outcome"]
