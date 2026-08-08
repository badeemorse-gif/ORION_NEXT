"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : tests.test_market_models_contract
Version      : 1.0.0
===============================================================================

Contract tests for the canonical MarketDataset domain model.

===============================================================================
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

import pandas as pd

from enums import DataHealth, Timeframe
from models.market import (
    MarketDataset,
    MarketMetadata,
    TimeframeData,
)


class TestMarketDatasetContract(unittest.TestCase):
    """Verify the canonical market-domain contract."""

    def _build_dataset(self) -> MarketDataset:
        now = datetime.now(timezone.utc)

        metadata = MarketMetadata(
            symbol="BTCUSDT",
            exchange="BINANCE",
            source="TEST",
            cache_version="1.0.0",
            downloaded_at=now,
            last_updated_at=now,
        )

        dataframe = pd.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [102.0, 103.0],
                "low": [99.0, 100.0],
                "close": [101.0, 102.0],
                "volume": [10.0, 11.0],
            },
            index=pd.date_range(
                "2026-01-01",
                periods=2,
                freq="1h",
                tz="UTC",
            ),
        )

        timeframe_data = TimeframeData(
            timeframe=Timeframe.H1,
            dataframe=dataframe,
            data_health=DataHealth.POOR,
            candles_count=2,
            first_timestamp=dataframe.index[0].to_pydatetime(),
            last_timestamp=dataframe.index[-1].to_pydatetime(),
        )

        dataset = MarketDataset(
            metadata=metadata,
        )

        dataset.add_timeframe(
            timeframe_data
        )

        return dataset

    def test_dataset_contains_market_data_only(self) -> None:
        dataset = self._build_dataset()

        self.assertEqual(
            dataset.symbol,
            "BTCUSDT",
        )

        self.assertEqual(
            dataset.exchange,
            "BINANCE",
        )

        self.assertTrue(
            dataset.has_timeframe(Timeframe.H1)
        )

        self.assertIsNotNone(
            dataset.get_timeframe(Timeframe.H1)
        )

    def test_timeframe_contract(self) -> None:
        dataset = self._build_dataset()

        timeframe_data = dataset.get_timeframe(
            Timeframe.H1
        )

        self.assertIsNotNone(
            timeframe_data
        )

        assert timeframe_data is not None

        self.assertEqual(
            timeframe_data.timeframe,
            Timeframe.H1,
        )

        self.assertEqual(
            timeframe_data.candles_count,
            2,
        )

        self.assertEqual(
            timeframe_data.data_health,
            DataHealth.POOR,
        )

        self.assertIsInstance(
            timeframe_data.dataframe,
            pd.DataFrame,
        )

    def test_downstream_results_are_not_dataset_state(self) -> None:
        dataset = self._build_dataset()

        self.assertFalse(
            hasattr(dataset, "profile")
        )

        self.assertFalse(
            hasattr(dataset, "score")
        )

        self.assertFalse(
            hasattr(dataset, "decision")
        )

        self.assertFalse(
            hasattr(dataset, "report")
        )

    def test_available_timeframes(self) -> None:
        dataset = self._build_dataset()

        self.assertEqual(
            dataset.available_timeframes(),
            (Timeframe.H1,),
        )


if __name__ == "__main__":
    unittest.main()