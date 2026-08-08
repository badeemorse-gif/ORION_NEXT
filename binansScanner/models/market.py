"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : models.market
Version      : 1.0.0
===============================================================================

Market domain models.
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
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(slots=True)
class MarketMetadata:
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
    timeframe: Timeframe
    dataframe: pd.DataFrame
    data_health: DataHealth
    candles_count: int
    first_timestamp: Optional[datetime]
    last_timestamp: Optional[datetime]
    indicators_ready: bool = False
    profile_ready: bool = False


@dataclass(slots=True)
class MarketDataset:
    metadata: MarketMetadata
    timeframes: dict[Timeframe, TimeframeData] = field(default_factory=dict)

    profile = None
    score = None
    decision = None
    report = None

    def add_timeframe(self, timeframe_data: TimeframeData) -> None:
        self.timeframes[timeframe_data.timeframe] = timeframe_data

    def get_timeframe(self, timeframe: Timeframe) -> Optional[TimeframeData]:
        return self.timeframes.get(timeframe)

    def has_timeframe(self, timeframe: Timeframe) -> bool:
        return timeframe in self.timeframes

    def available_timeframes(self) -> tuple[Timeframe, ...]:
        return tuple(self.timeframes.keys())

    @property
    def symbol(self) -> str:
        return self.metadata.symbol

    @property
    def exchange(self) -> str:
        return self.metadata.exchange

    @property
    def is_valid(self) -> bool:
        return self.metadata.is_valid
