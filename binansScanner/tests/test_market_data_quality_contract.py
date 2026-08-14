"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : tests.test_market_data_quality_contract
Version      : 1.0.0
===============================================================================

Contract tests for MarketDataset integrity, provenance, cadence, and freshness.
===============================================================================
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from data_quality import (
    DataQualityError,
    DataQualityStatus,
    MarketDatasetQualityValidator,
)
from enums import DataHealth, Timeframe
from models.market import MarketDataset, MarketMetadata, TimeframeData


class TestMarketDatasetQualityContract(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = MarketDatasetQualityValidator()

    def _build_dataset(
        self,
        *,
        timeframe: Timeframe = Timeframe.H1,
        index: pd.DatetimeIndex | None = None,
    ) -> MarketDataset:
        now = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)
        if index is None:
            index = pd.date_range(
                "2026-08-14 09:00",
                periods=3,
                freq="1h",
                tz="UTC",
            )

        dataframe = pd.DataFrame(
            {
                "open": [100.0, 101.0, 102.0],
                "high": [102.0, 103.0, 104.0],
                "low": [99.0, 100.0, 101.0],
                "close": [101.0, 102.0, 103.0],
                "volume": [10.0, 11.0, 12.0],
            },
            index=index,
        )

        metadata = MarketMetadata(
            symbol="BTCUSDT",
            exchange="BINANCE",
            source="BINANCE_API",
            cache_version="1.0.0",
            downloaded_at=now - timedelta(minutes=1),
            last_updated_at=now,
        )

        timeframe_data = TimeframeData(
            timeframe=timeframe,
            dataframe=dataframe,
            data_health=DataHealth.POOR,
            candles_count=len(dataframe),
            first_timestamp=dataframe.index[0].to_pydatetime(),
            last_timestamp=dataframe.index[-1].to_pydatetime(),
        )
        dataset = MarketDataset(metadata=metadata)
        dataset.add_timeframe(timeframe_data)
        return dataset

    def test_valid_dataset_is_accepted(self) -> None:
        dataset = self._build_dataset()
        report = self.validator.validate(
            dataset,
            required_timeframes=(Timeframe.H1,),
            now=datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(report.status, DataQualityStatus.VALID)
        self.assertTrue(report.is_valid)
        self.assertEqual(report.issues, ())

    def test_missing_required_timeframe_is_fail_closed(self) -> None:
        dataset = self._build_dataset()
        report = self.validator.validate(
            dataset,
            required_timeframes=(Timeframe.H1, Timeframe.M15),
            now=datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(report.status, DataQualityStatus.MISSING)
        self.assertFalse(report.is_valid)
        with self.assertRaises(DataQualityError):
            self.validator.assert_valid(
                dataset,
                required_timeframes=(Timeframe.H1, Timeframe.M15),
                now=datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc),
            )

    def test_timeframe_gap_is_invalid(self) -> None:
        index = pd.DatetimeIndex(
            [
                "2026-08-14 09:00+00:00",
                "2026-08-14 10:00+00:00",
                "2026-08-14 12:00+00:00",
            ]
        )
        dataset = self._build_dataset(index=index)
        report = self.validator.validate(dataset)
        self.assertEqual(report.status, DataQualityStatus.INVALID)
        self.assertTrue(any("cadence/gap" in issue for issue in report.issues))

    def test_nan_and_infinity_are_invalid(self) -> None:
        dataset = self._build_dataset()
        timeframe_data = dataset.get_timeframe(Timeframe.H1)
        assert timeframe_data is not None
        timeframe_data.dataframe.loc[timeframe_data.dataframe.index[0], "close"] = np.nan
        timeframe_data.dataframe.loc[timeframe_data.dataframe.index[1], "open"] = np.inf

        report = self.validator.validate(dataset)
        self.assertEqual(report.status, DataQualityStatus.INVALID)
        self.assertFalse(report.is_valid)

    def test_staleness_requires_an_explicit_caller_threshold(self) -> None:
        dataset = self._build_dataset()
        checked_at = datetime(2026, 8, 14, 15, 0, tzinfo=timezone.utc)

        without_threshold = self.validator.validate(dataset, now=checked_at)
        self.assertEqual(without_threshold.status, DataQualityStatus.VALID)

        with_threshold = self.validator.validate(
            dataset,
            now=checked_at,
            max_age=timedelta(minutes=30),
        )
        self.assertEqual(with_threshold.status, DataQualityStatus.STALE)
        self.assertTrue(any("stale timeframe" in issue for issue in with_threshold.issues))

    def test_provenance_chronology_is_enforced(self) -> None:
        dataset = self._build_dataset()
        dataset.metadata.last_updated_at = dataset.metadata.downloaded_at - timedelta(seconds=1)
        report = self.validator.validate(dataset)
        self.assertEqual(report.status, DataQualityStatus.INVALID)
        self.assertTrue(any("provenance chronology" in issue for issue in report.issues))


if __name__ == "__main__":
    unittest.main()
