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


METRIC_UNIT = "%"


def to_signal_outcome(
    record: ForwardOutcomeRecord,
    observation_timestamp: datetime,
) -> "SignalOutcome":
    """Map an experimental D5 record to the existing D6 SignalOutcome.

    D6 has one MFE/MAE pair and one outcome timestamp, so the canonical
    handoff aggregates MFE/MAE across the three forward horizons and uses
    the 24h measurement timestamp. Detailed per-horizon values remain
    available on the original D5 record.
    """
    one_hour = record.outcome("1h")
    four_hour = record.outcome("4h")
    outcome_24h = record.outcome("24h")

    if outcome_24h.as_of <= observation_timestamp:
        raise ValueError("outcome_timestamp must be strictly after observation timestamp")

    canonical_mfe = max(
        one_hour.mfe_pct,
        four_hour.mfe_pct,
        outcome_24h.mfe_pct,
    )
    canonical_mae = max(
        one_hour.mae_pct,
        four_hour.mae_pct,
        outcome_24h.mae_pct,
    )

    signal_journal = import_module("binansScanner.models.signal_journal")
    signal_outcome_cls: Any = getattr(signal_journal, "SignalOutcome")
    return signal_outcome_cls(
        outcome_1h=one_hour.return_pct,
        outcome_4h=four_hour.return_pct,
        outcome_24h=outcome_24h.return_pct,
        mfe=canonical_mfe,
        mae=canonical_mae,
        outcome_timestamp=outcome_24h.as_of,
        metric_unit=METRIC_UNIT,
    )


__all__ = ["METRIC_UNIT", "to_signal_outcome"]
