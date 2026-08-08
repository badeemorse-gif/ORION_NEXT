"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : providers.binance_mapper
Version      : 2.0.0
Status       : ORION Production Mapper Component
===============================================================================

Handles JSON klines conversion to strictly typed, UTC-indexed, and validated
pandas DataFrames, along with MarketDataset container creation.
===============================================================================
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any

from models.market import MarketDataset


# =============================================================================
# Custom Exceptions
# =============================================================================

class BinanceMapperError(Exception):
    """Base exception for mapper errors."""
    pass


class InvalidKlinesData(BinanceMapperError):
    """Raised when klines data is invalid or empty."""
    pass


# =============================================================================
# Binance Mapper Component
# =============================================================================

class BinanceMapper:
    """
    Responsible for JSON klines conversion, OHLCV column mapping, timestamp
    conversion, data cleaning, validation, and MarketDataset container creation.
    """

    def __init__(self) -> None:
        pass

    def convert_klines_to_dataframe(self, raw_klines: list[list[Any]]) -> pd.DataFrame:
        """
        Convert raw Binance klines list into a strictly typed, UTC indexed, sorted pandas DataFrame,
        using correct open_time column mapping and rigorous OHLC validation.
        """
        if not raw_klines:
            raise InvalidKlinesData("Received empty klines data from Binance API.")

        columns = [
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_asset_volume",
            "number_of_trades",
            "taker_buy_base_asset_volume",
            "taker_buy_quote_asset_volume",
            "ignore",
        ]

        df = pd.DataFrame(raw_klines, columns=columns)

        required_cols = ["open", "high", "low", "close", "volume"]
        for col in required_cols:
            df[col] = pd.to_numeric(df[col], errors="raise")

        df = df[required_cols + ["open_time"]]

        df.index = pd.to_datetime(
            df["open_time"],
            unit="ms",
            utc=True,
        )
        df.index.name = "timestamp"
        
        df.drop(columns=["open_time"], inplace=True)
        df = df.sort_index()

        if df.empty:
            raise InvalidKlinesData("Converted DataFrame is empty.")

        if not isinstance(df.index, pd.DatetimeIndex) or df.index.tz is None:
            raise InvalidKlinesData("DataFrame index must be a timezone-aware DatetimeIndex.")

        if df.index.duplicated().any():
            raise InvalidKlinesData("DataFrame contains duplicate index timestamps.")

        if not df.index.is_monotonic_increasing:
            raise InvalidKlinesData("DataFrame index must be chronologically sorted.")

        sub_df = df[required_cols]
        if sub_df.isna().any().any():
            raise InvalidKlinesData("DataFrame contains NaN values.")

        if np.isinf(sub_df.to_numpy()).any():
            raise InvalidKlinesData("DataFrame contains INF values.")

        if (df["volume"] < 0).any():
            raise InvalidKlinesData("DataFrame contains negative volume values.")

        invalid_ohlc = (
            (df["high"] < df["low"]) |
            (df["high"] < df["open"]) |
            (df["high"] < df["close"]) |
            (df["low"] > df["open"]) |
            (df["low"] > df["close"])
        )
        if invalid_ohlc.any():
            raise InvalidKlinesData("DataFrame contains invalid OHLC relationships.")

        return df

    def create_market_dataset(self, symbol: str, timeframe_data: dict[Any, pd.DataFrame], exchange: str = "binance") -> MarketDataset:
        """
        Create and populate a MarketDataset container from mapped timeframe dataframes.
        """
        dataset = MarketDataset(symbol=symbol, exchange=exchange)
        for tf, df in timeframe_data.items():
            dataset.set_dataframe(tf, df)
        return dataset