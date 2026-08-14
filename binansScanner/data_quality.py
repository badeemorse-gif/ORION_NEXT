"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : data_quality.py
Version      : 1.0.2
Status       : ORION Market Data Quality Contract
===============================================================================

Dataset-level integrity validation.
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Iterable, Optional

import numpy as np
import pandas as pd

from enums import Timeframe
from models.market import MarketDataset


class DataQualityError(ValueError):
    """Raised when a dataset cannot satisfy the canonical quality contract."""


class DataQualityStatus(Enum):
    """Explicit data-quality states exposed to downstream callers."""

    VALID = "valid"
    MISSING = "missing"
    STALE = "stale"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    """Deterministic result of a dataset integrity check."""

    status: DataQualityStatus
    checked_at: datetime
    issues: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        """Return True only for a fully valid dataset."""
        return self.status is DataQualityStatus.VALID


class MarketDatasetQualityValidator:
    """Validate structure, provenance, timeframe integrity, and freshness."""

    EXPECTED_INTERVALS = {
        Timeframe.M1: timedelta(minutes=1),
        Timeframe.M5: timedelta(minutes=5),
        Timeframe.M15: timedelta(minutes=15),
        Timeframe.H1: timedelta(hours=1),
        Timeframe.H4: timedelta(hours=4),
        Timeframe.D1: timedelta(days=1),
    }

    def validate(
        self,
        dataset: MarketDataset,
        *,
        required_timeframes: Iterable[Timeframe] = (),
        now: Optional[datetime] = None,
        max_age: Optional[timedelta] = None,
    ) -> DataQualityReport:
        """Validate a MarketDataset without repairing or fabricating data."""

        if not isinstance(dataset, MarketDataset):
            raise DataQualityError("dataset must be a MarketDataset")
        if max_age is not None and max_age < timedelta(0):
            raise DataQualityError("max_age must be non-negative")

        checked_at = self._normalize_now(now)
        issues: list[str] = []
        missing_required = [
            timeframe
            for timeframe in required_timeframes
            if not dataset.has_timeframe(timeframe)
        ]

        if missing_required:
            issues.extend(
                f"missing required timeframe: {timeframe.value}"
                for timeframe in missing_required
            )

        issues.extend(self._validate_metadata(dataset))

        for timeframe, timeframe_data in dataset.timeframes.items():
            issues.extend(self._validate_timeframe(timeframe, timeframe_data))

            if max_age is not None and timeframe_data.last_timestamp is not None:
                try:
                    age = checked_at - self._ensure_aware(
                        timeframe_data.last_timestamp,
                        "last_timestamp",
                    )
                    if age > max_age:
                        issues.append(
                            f"stale timeframe: {timeframe.value} "
                            f"(age={age}, max_age={max_age})"
                        )
                except DataQualityError as exc:
                    issues.append(str(exc))

        if missing_required:
            status = DataQualityStatus.MISSING
        elif issues and not all(
            issue.startswith("stale timeframe:") for issue in issues
        ):
            status = DataQualityStatus.INVALID
        elif issues:
            status = DataQualityStatus.STALE
        else:
            status = DataQualityStatus.VALID

        return DataQualityReport(
            status=status,
            checked_at=checked_at,
            issues=tuple(issues),
        )

    def assert_valid(
        self,
        dataset: MarketDataset,
        *,
        required_timeframes: Iterable[Timeframe] = (),
        now: Optional[datetime] = None,
        max_age: Optional[timedelta] = None,
    ) -> DataQualityReport:
        """Fail closed when the dataset does not satisfy the contract."""

        report = self.validate(
            dataset,
            required_timeframes=required_timeframes,
            now=now,
            max_age=max_age,
        )
        if not report.is_valid:
            details = "; ".join(report.issues) or report.status.value
            raise DataQualityError(
                f"MarketDataset failed quality contract: {details}"
            )
        return report

    def _validate_metadata(self, dataset: MarketDataset) -> list[str]:
        metadata = dataset.metadata
        issues: list[str] = []

        for field_name in ("symbol", "exchange", "source", "cache_version"):
            value = getattr(metadata, field_name, None)
            if not isinstance(value, str) or not value.strip():
                issues.append(f"invalid provenance field: {field_name}")

        try:
            downloaded_at = self._ensure_aware(metadata.downloaded_at, "downloaded_at")
            last_updated_at = self._ensure_aware(metadata.last_updated_at, "last_updated_at")
            if last_updated_at < downloaded_at:
                issues.append(
                    "invalid provenance chronology: last_updated_at before downloaded_at"
                )
        except DataQualityError as exc:
            issues.append(str(exc))

        if metadata.is_valid is not True:
            issues.append("dataset metadata is marked invalid")

        return issues

    def _validate_timeframe(self, timeframe: Timeframe, timeframe_data) -> list[str]:
        issues: list[str] = []
        dataframe = timeframe_data.dataframe

        if timeframe_data.timeframe is not timeframe:
            issues.append(
                f"timeframe key mismatch: key={timeframe.value}, "
                f"payload={timeframe_data.timeframe.value}"
            )

        if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
            issues.append(f"invalid or empty dataframe: {timeframe.value}")
            return issues

        required_columns = ("open", "high", "low", "close", "volume")
        missing_columns = [
            column for column in required_columns if column not in dataframe.columns
        ]
        if missing_columns:
            issues.append(
                f"missing OHLCV columns for {timeframe.value}: {missing_columns}"
            )
            return issues

        if not isinstance(dataframe.index, pd.DatetimeIndex):
            issues.append(f"invalid timestamp index: {timeframe.value}")
            return issues
        if dataframe.index.tz is None:
            issues.append(f"timestamp index is timezone-naive: {timeframe.value}")
            return issues
        if dataframe.index.duplicated().any():
            issues.append(f"duplicate timestamps: {timeframe.value}")
        if not dataframe.index.is_monotonic_increasing:
            issues.append(f"timestamps not ordered: {timeframe.value}")

        required_data = dataframe[list(required_columns)]
        try:
            numeric_values = required_data.to_numpy(dtype=float)
            if not np.isfinite(numeric_values).all():
                issues.append(f"non-finite OHLCV values: {timeframe.value}")
        except (TypeError, ValueError):
            issues.append(f"non-numeric OHLCV values: {timeframe.value}")

        if (dataframe["volume"] < 0).any():
            issues.append(f"negative volume: {timeframe.value}")

        invalid_ohlc = (
            (dataframe["high"] < dataframe["low"])
            | (dataframe["high"] < dataframe["open"])
            | (dataframe["high"] < dataframe["close"])
            | (dataframe["low"] > dataframe["open"])
            | (dataframe["low"] > dataframe["close"])
        )
        if invalid_ohlc.any():
            issues.append(f"invalid OHLC relationship: {timeframe.value}")

        expected_interval = self.EXPECTED_INTERVALS.get(timeframe)
        if expected_interval is None:
            issues.append(f"unsupported timeframe: {timeframe}")
        elif len(dataframe.index) > 1:
            deltas = dataframe.index.to_series().diff().dropna()
            if not (deltas == expected_interval).all():
                issues.append(
                    f"timeframe cadence/gap violation: {timeframe.value} "
                    f"expected {expected_interval}"
                )

        if timeframe_data.candles_count != len(dataframe):
            issues.append(
                f"candles_count mismatch: {timeframe.value} "
                f"metadata={timeframe_data.candles_count}, actual={len(dataframe)}"
            )

        try:
            first_timestamp = self._ensure_aware(timeframe_data.first_timestamp, "first_timestamp")
            last_timestamp = self._ensure_aware(timeframe_data.last_timestamp, "last_timestamp")
            if first_timestamp != dataframe.index[0].to_pydatetime():
                issues.append(f"first_timestamp mismatch: {timeframe.value}")
            if last_timestamp != dataframe.index[-1].to_pydatetime():
                issues.append(f"last_timestamp mismatch: {timeframe.value}")
        except DataQualityError as exc:
            issues.append(str(exc))

        return issues

    @staticmethod
    def _normalize_now(now: Optional[datetime]) -> datetime:
        value = now if now is not None else datetime.now(timezone.utc)
        if value.tzinfo is None or value.utcoffset() is None:
            raise DataQualityError("now must be timezone-aware")
        return value

    @staticmethod
    def _ensure_aware(value: Optional[datetime], field_name: str) -> datetime:
        if value is None or value.tzinfo is None or value.utcoffset() is None:
            raise DataQualityError(f"{field_name} must be a timezone-aware datetime")
        return value
