"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : models.market
Version      : 2.0.0
===============================================================================

Canonical market-domain models.

This module represents market data only.

Downstream processing results such as:
    - profile
    - score
    - decision
    - execution
    - report

must NOT be stored inside MarketDataset.

===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd

from enums import DataHealth, Timeframe


@dataclass(slots=True)
class Candle:
    """Canonical single-candle representation."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(slots=True)
class MarketMetadata:
    """Metadata describing the origin and validity of a market dataset."""

    symbol: str
    exchange: str
    source: str
    cache_version: str
    downloaded_at: datetime
    last_updated_at: datetime
    is_valid: bool = True
    validation_message: Optional[str] = None


@dataclass(slots=True)
class TimeframeData:
    """
    Canonical market data for one timeframe.

    This object contains market data and data-quality metadata only.

    Processing state such as:
        indicators_ready
        profile_ready

    does not belong here.
    """

    timeframe: Timeframe
    dataframe: pd.DataFrame
    data_health: DataHealth
    candles_count: int
    first_timestamp: Optional[datetime]
    last_timestamp: Optional[datetime]


@dataclass(slots=True)
class MarketDataset:
    """
    Canonical market dataset.

    MarketDataset is intentionally limited to market information.

    It must not be used as a mutable container for downstream results.
    """

    metadata: MarketMetadata
    timeframes: dict[Timeframe, TimeframeData] = field(default_factory=dict)

    def add_timeframe(self, timeframe_data: TimeframeData) -> None:
        """Add or replace market data for a timeframe."""
        self.timeframes[timeframe_data.timeframe] = timeframe_data

    def get_timeframe(
        self,
        timeframe: Timeframe,
    ) -> Optional[TimeframeData]:
        """Return timeframe data when available."""
        return self.timeframes.get(timeframe)

    def has_timeframe(self, timeframe: Timeframe) -> bool:
        """Return whether the dataset contains the requested timeframe."""
        return timeframe in self.timeframes

    def available_timeframes(self) -> tuple[Timeframe, ...]:
        """Return all available timeframes in insertion order."""
        return tuple(self.timeframes.keys())

    @property
    def symbol(self) -> str:
        """Return the market symbol."""
        return self.metadata.symbol

    @property
    def exchange(self) -> str:
        """Return the exchange identifier."""
        return self.metadata.exchange

    @property
    def is_valid(self) -> bool:
        """Return the dataset-level validity state."""
        return self.metadata.is_valid