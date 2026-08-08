"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : tests.test_indicator_contract
Version      : 1.0.0
===============================================================================

Canonical indicator contract tests.

===============================================================================
"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from enums import DataHealth, Timeframe
from engines.indicator_calculator import IndicatorCalculator
from engines.indicator_engine import IndicatorEngine
from models.market import (
    MarketDataset,
    MarketMetadata,
    TimeframeData,
)


class TestIndicatorContract(unittest.TestCase):
    """Verify the canonical Indicator layer."""

    def _build_dataframe(
        self,
        rows: int = 250,
    ) -> pd.DataFrame:
        index = pd.date_range(
            "2026-01-01",
            periods=rows,
            freq="1h",
            tz="UTC",
        )

        base = np.linspace(
            100.0,
            150.0,
            rows,
        )

        return pd.DataFrame(
            {
                "open": base,
                "high": base + 2.0,
                "low": base - 2.0,
                "close": base + 1.0,
                "volume": np.linspace(
                    1000.0,
                    2000.0,
                    rows,
                ),
            },
            index=index,
        )

    def _build_timeframe_data(self) -> TimeframeData:
        dataframe = self._build_dataframe()

        return TimeframeData(
            timeframe=Timeframe.H1,
            dataframe=dataframe,
            data_health=DataHealth.GOOD,
            candles_count=len(dataframe),
            first_timestamp=(
                dataframe.index[0].to_pydatetime()
            ),
            last_timestamp=(
                dataframe.index[-1].to_pydatetime()
            ),
        )

    def test_canonical_indicators_are_present(self) -> None:
        calculator = IndicatorCalculator()

        dataframe = calculator.apply_all(
            self._build_dataframe()
        )

        for column in (
            "ema_9",
            "ema_20",
            "ema_50",
            "rsi_14",
            "adx_14",
            "momentum_5",
        ):
            self.assertIn(
                column,
                dataframe.columns,
            )

        calculator.validate_required_indicators(
            dataframe
        )

    def test_indicator_engine_does_not_add_runtime_state(
        self,
    ) -> None:
        timeframe_data = (
            self._build_timeframe_data()
        )

        engine = IndicatorEngine()

        result = engine.calculate_timeframe(
            timeframe_data,
            symbol="BTCUSDT",
        )

        self.assertIs(
            result,
            timeframe_data,
        )

        self.assertFalse(
            hasattr(
                result,
                "indicators_ready",
            )
        )

        self.assertFalse(
            hasattr(
                result,
                "profile_ready",
            )
        )

    def test_clear_indicators_restores_ohlcv_contract(
        self,
    ) -> None:
        timeframe_data = (
            self._build_timeframe_data()
        )

        engine = IndicatorEngine()

        engine.calculate_timeframe(
            timeframe_data,
            symbol="BTCUSDT",
        )

        engine.clear_indicators(
            timeframe_data
        )

        self.assertEqual(
            list(
                timeframe_data.dataframe.columns
            ),
            [
                "open",
                "high",
                "low",
                "close",
                "volume",
            ],
        )

        self.assertFalse(
            hasattr(
                timeframe_data,
                "indicators_ready",
            )
        )

    def test_dataset_calculation_preserves_domain_contract(
        self,
    ) -> None:
        timeframe_data = (
            self._build_timeframe_data()
        )

        metadata = MarketMetadata(
            symbol="BTCUSDT",
            exchange="BINANCE",
            source="TEST",
            cache_version="1.0.0",
            downloaded_at=(
                timeframe_data.first_timestamp
            ),
            last_updated_at=(
                timeframe_data.last_timestamp
            ),
        )

        dataset = MarketDataset(
            metadata=metadata,
        )

        dataset.add_timeframe(
            timeframe_data
        )

        IndicatorEngine().calculate_dataset(
            dataset
        )

        self.assertTrue(
            dataset.has_timeframe(
                Timeframe.H1
            )
        )

        calculated = dataset.get_timeframe(
            Timeframe.H1
        )

        self.assertIsNotNone(
            calculated
        )

        assert calculated is not None

        self.assertIn(
            "ema_9",
            calculated.dataframe.columns,
        )

        self.assertFalse(
            hasattr(
                calculated,
                "indicators_ready",
            )
        )


if __name__ == "__main__":
    unittest.main()