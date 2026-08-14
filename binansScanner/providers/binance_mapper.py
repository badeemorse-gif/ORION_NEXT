"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : providers.binance_mapper
Version      : 3.1.1
Status       : ORION Canonical Market Contract
===============================================================================

Responsible for converting Binance raw kline payloads into canonical pandas
DataFrames and constructing the canonical MarketDataset domain model.

This module must not contain analytical logic.
===============================================================================
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from data_quality import DataQualityError, MarketDatasetQualityValidator
from enums import DataHealth, Timeframe
from models.market import MarketDataset, MarketMetadata, TimeframeData


class BinanceMapperError(Exception):
    """Base exception for mapper errors."""


class InvalidKlinesData(BinanceMapperError):
    """Raised when Binance kline data is invalid or empty."""


class BinanceMapper:
    """Canonical Binance-to-domain mapper."""

    REQUIRED_COLUMNS = (
        "open",
        "high",
        "low",
        "close",
        "volume",
    )

    RAW_COLUMNS = (
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
    )

    def convert_klines_to_dataframe(self, raw_klines: list[list[Any]]) -> pd.DataFrame:
        """Convert raw Binance klines into a validated OHLCV DataFrame."""

        if not raw_klines:
            raise InvalidKlinesData("Received empty klines data from Binance API.")

        try:
            dataframe = pd.DataFrame(raw_klines, columns=self.RAW_COLUMNS)
        except Exception as exc:
            raise InvalidKlinesData(
                f"Unable to construct kline DataFrame: {exc}"
            ) from exc

        for column in self.REQUIRED_COLUMNS:
            dataframe[column] = pd.to_numeric(dataframe[column], errors="raise")
        dataframe["open_time"] = pd.to_numeric(
            dataframe["open_time"],
            errors="raise",
        )
        dataframe = dataframe[list(self.REQUIRED_COLUMNS) + ["open_time"]]
        dataframe.index = pd.to_datetime(dataframe["open_time"], unit="ms", utc=True)
        dataframe.index.name = "timestamp"
        dataframe.drop(columns=["open_time"], inplace=True)
        dataframe = dataframe.sort_index()

        self._validate_dataframe(dataframe)
        return dataframe

    def create_market_dataset(
        self,
        symbol: str,
        timeframe_data: dict[Any, pd.DataFrame],
        exchange: str = "BINANCE",
        source: str = "BINANCE_API",
        cache_version: str = "1.0.0",
    ) -> MarketDataset:
        """Construct and quality-validate the canonical MarketDataset."""

        if not symbol or not isinstance(symbol, str):
            raise BinanceMapperError("symbol must be a non-empty string.")
        if not timeframe_data:
            raise BinanceMapperError(
                f"No timeframe data supplied for symbol '{symbol}'."
            )

        now = datetime.now(timezone.utc)
        metadata = MarketMetadata(
            symbol=symbol,
            exchange=exchange,
            source=source,
            cache_version=cache_version,
            downloaded_at=now,
            last_updated_at=now,
            is_valid=True,
            validation_message=None,
        )
        dataset = MarketDataset(metadata=metadata)

        for raw_timeframe, dataframe in timeframe_data.items():
            timeframe = self._normalize_timeframe(raw_timeframe)
            self._validate_dataframe(dataframe)
            data_health = self._classify_data_health(dataframe)

            timeframe_data_model = TimeframeData(
                timeframe=timeframe,
                dataframe=dataframe,
                data_health=data_health,
                candles_count=len(dataframe),
                first_timestamp=dataframe.index[0].to_pydatetime(),
                last_timestamp=dataframe.index[-1].to_pydatetime(),
            )
            dataset.add_timeframe(timeframe_data_model)

        try:
            MarketDatasetQualityValidator().assert_valid(dataset)
        except DataQualityError as exc:
            raise InvalidKlinesData(str(exc)) from exc

        return dataset

    def _normalize_timeframe(self, timeframe: Any) -> Timeframe:
        """Normalize a timeframe value into the canonical Timeframe enum."""

        if isinstance(timeframe, Timeframe):
            return timeframe
        try:
            return Timeframe(str(timeframe))
        except ValueError as exc:
            raise BinanceMapperError(
                f"Unsupported timeframe: {timeframe!r}"
            ) from exc

    def _validate_dataframe(self, dataframe: pd.DataFrame) -> None:
        """Validate the canonical OHLCV DataFrame."""

        if not isinstance(dataframe, pd.DataFrame):
            raise InvalidKlinesData("Expected pandas.DataFrame.")
        if dataframe.empty:
            raise InvalidKlinesData("DataFrame is empty.")

        missing_columns = [
            column for column in self.REQUIRED_COLUMNS
            if column not in dataframe.columns
        ]
        if missing_columns:
            raise InvalidKlinesData(
                f"Missing required columns: {missing_columns}"
            )
        if not isinstance(dataframe.index, pd.DatetimeIndex):
            raise InvalidKlinesData("DataFrame index must be a DatetimeIndex.")
        if dataframe.index.tz is None:
            raise InvalidKlinesData("DataFrame index must be timezone-aware.")
        if dataframe.index.duplicated().any():
            raise InvalidKlinesData("DataFrame contains duplicate timestamps.")
        if not dataframe.index.is_monotonic_increasing:
            raise InvalidKlinesData(
                "DataFrame index must be chronologically sorted."
            )

        required_data = dataframe[list(self.REQUIRED_COLUMNS)]
        try:
            numeric_data = required_data.to_numpy(dtype=float)
        except (TypeError, ValueError) as exc:
            raise InvalidKlinesData(
                "DataFrame contains non-numeric OHLCV values."
            ) from exc

        if not np.isfinite(numeric_data).all():
            raise InvalidKlinesData("DataFrame contains non-finite values.")
        if (dataframe["volume"] < 0).any():
            raise InvalidKlinesData(
                "DataFrame contains negative volume values."
            )

        invalid_ohlc = (
            (dataframe["high"] < dataframe["low"])
            | (dataframe["high"] < dataframe["open"])
            | (dataframe["high"] < dataframe["close"])
            | (dataframe["low"] > dataframe["open"])
            | (dataframe["low"] > dataframe["close"])
        )
        if invalid_ohlc.any():
            raise InvalidKlinesData(
                "DataFrame contains invalid OHLC relationships."
            )

    def _classify_data_health(self, dataframe: pd.DataFrame) -> DataHealth:
        """Classify basic market-data quantity without analysis semantics."""

        candles_count = len(dataframe)
        if candles_count <= 0:
            return DataHealth.INVALID
        if candles_count >= 1000:
            return DataHealth.EXCELLENT
        if candles_count >= 500:
            return DataHealth.GOOD
        if candles_count >= 100:
            return DataHealth.ACCEPTABLE
        return DataHealth.POOR
