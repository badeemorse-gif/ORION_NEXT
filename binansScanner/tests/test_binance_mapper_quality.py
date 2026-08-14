"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : tests.test_binance_mapper_quality
Version      : 1.0.0
===============================================================================

Integration tests proving the Binance mapper cannot emit invalid datasets.
===============================================================================
"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from providers.binance_mapper import BinanceMapper, InvalidKlinesData


class TestBinanceMapperQuality(unittest.TestCase):
    def setUp(self) -> None:
        self.mapper = BinanceMapper()

    def _frame(self, *, gap: bool = False) -> pd.DataFrame:
        timestamps = [
            "2026-08-14 09:00+00:00",
            "2026-08-14 10:00+00:00",
            "2026-08-14 12:00+00:00" if gap else "2026-08-14 11:00+00:00",
        ]
        return pd.DataFrame(
            {
                "open": [100.0, 101.0, 102.0],
                "high": [102.0, 103.0, 104.0],
                "low": [99.0, 100.0, 101.0],
                "close": [101.0, 102.0, 103.0],
                "volume": [10.0, 11.0, 12.0],
            },
            index=pd.DatetimeIndex(timestamps),
        )

    def test_mapper_returns_only_quality_valid_dataset(self) -> None:
        dataset = self.mapper.create_market_dataset(
            symbol="BTCUSDT",
            timeframe_data={"1h": self._frame()},
        )
        self.assertTrue(dataset.is_valid)
        self.assertEqual(len(dataset.timeframes), 1)

    def test_mapper_rejects_timeframe_gap(self) -> None:
        with self.assertRaises(InvalidKlinesData):
            self.mapper.create_market_dataset(
                symbol="BTCUSDT",
                timeframe_data={"1h": self._frame(gap=True)},
            )

    def test_mapper_rejects_non_finite_values(self) -> None:
        frame = self._frame()
        frame.loc[frame.index[0], "close"] = np.inf
        with self.assertRaises(InvalidKlinesData):
            self.mapper.create_market_dataset(
                symbol="BTCUSDT",
                timeframe_data={"1h": frame},
            )


if __name__ == "__main__":
    unittest.main()
