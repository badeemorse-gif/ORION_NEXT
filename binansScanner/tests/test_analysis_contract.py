"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : tests.test_analysis_contract
Version      : 1.1.0
===============================================================================

Canonical Analysis Contract tests.

===============================================================================
"""

from __future__ import annotations

import unittest
from datetime import datetime

import numpy as np
import pandas as pd

from enums import DataHealth, Timeframe
from engines.analysis_engine import AnalysisEngine
from models.analysis import AnalysisResult
from models.market import MarketDataset, MarketMetadata, TimeframeData


class TestAnalysisContract(unittest.TestCase):
    """Verify the canonical Analysis layer."""

    def _build_dataframe(
        self,
        *,
        bullish: bool = True,
        include_indicators: bool = True,
        rows: int = 250,
    ) -> pd.DataFrame:
        index = pd.date_range("2026-01-01", periods=rows, freq="1h", tz="UTC")
        close = np.linspace(100.0, 150.0, rows)
        dataframe = pd.DataFrame(
            {
                "open": close - 0.5,
                "high": close + 2.0,
                "low": close - 2.0,
                "close": close,
                "volume": np.linspace(1000.0, 2000.0, rows),
            },
            index=index,
        )

        if not include_indicators:
            return dataframe

        if bullish:
            dataframe["ema_9"] = close + 3.0
            dataframe["ema_20"] = close + 2.0
            dataframe["ema_50"] = close + 1.0
        else:
            dataframe["ema_9"] = close - 3.0
            dataframe["ema_20"] = close - 2.0
            dataframe["ema_50"] = close - 1.0

        dataframe["rsi_14"] = 60.0
        dataframe["adx_14"] = 30.0
        dataframe["momentum_5"] = 2.0
        return dataframe

    def _build_dataset(
        self,
        dataframe: pd.DataFrame,
        timeframe: Timeframe = Timeframe.H1,
    ) -> MarketDataset:
        first_timestamp = dataframe.index[0].to_pydatetime()
        last_timestamp = dataframe.index[-1].to_pydatetime()
        metadata = MarketMetadata(
            symbol="BTCUSDT",
            exchange="BINANCE",
            source="TEST",
            cache_version="1.0.0",
            downloaded_at=first_timestamp,
            last_updated_at=last_timestamp,
        )
        timeframe_data = TimeframeData(
            timeframe=timeframe,
            dataframe=dataframe,
            data_health=DataHealth.GOOD,
            candles_count=len(dataframe),
            first_timestamp=first_timestamp,
            last_timestamp=last_timestamp,
        )
        dataset = MarketDataset(metadata=metadata)
        dataset.add_timeframe(timeframe_data)
        return dataset

    def test_analysis_returns_analysis_result(self) -> None:
        result = AnalysisEngine().analyze(self._build_dataset(self._build_dataframe()))
        self.assertIsInstance(result, AnalysisResult)

    def test_analysis_reads_canonical_dataframe(self) -> None:
        result = AnalysisEngine().analyze(self._build_dataset(self._build_dataframe()))
        self.assertEqual(result.market_state, "BULLISH")
        self.assertIn("EMA_ALIGNMENT_BULLISH", result.signals)

    def test_analysis_supports_canonical_timeframe_enum(self) -> None:
        dataset = self._build_dataset(self._build_dataframe(), timeframe=Timeframe.H1)
        result = AnalysisEngine(default_timeframe=Timeframe.H1).analyze(dataset)
        self.assertEqual(result.market_state, "BULLISH")

    def test_analysis_supports_timeframe_value(self) -> None:
        dataset = self._build_dataset(self._build_dataframe(), timeframe=Timeframe.H1)
        result = AnalysisEngine(default_timeframe="1h").analyze(dataset)
        self.assertEqual(result.market_state, "BULLISH")

    def test_missing_indicators_are_reported(self) -> None:
        dataset = self._build_dataset(self._build_dataframe(include_indicators=False))
        result = AnalysisEngine().analyze(dataset)
        self.assertIn("MISSING_REQUIRED_INDICATORS", result.warnings)
        self.assertIn("LOW_CONFIDENCE_DATA", result.signals)

    def test_missing_indicators_fail_closed_to_neutral_zero_strength(self) -> None:
        """Incomplete indicator input must never produce directional intelligence."""
        dataset = self._build_dataset(self._build_dataframe(include_indicators=False))
        result = AnalysisEngine().analyze(dataset)
        self.assertEqual(result.market_state, "NEUTRAL")
        self.assertEqual(result.strength, 0.0)

    def test_nan_required_indicator_fails_closed(self) -> None:
        dataframe = self._build_dataframe()
        dataframe.loc[dataframe.index[-1], "rsi_14"] = np.nan
        result = AnalysisEngine().analyze(self._build_dataset(dataframe))
        self.assertEqual(result.market_state, "NEUTRAL")
        self.assertEqual(result.strength, 0.0)
        self.assertIn("INVALID_REQUIRED_INDICATORS", result.warnings)
        self.assertIn("LOW_CONFIDENCE_DATA", result.signals)

    def test_infinite_required_indicator_fails_closed(self) -> None:
        dataframe = self._build_dataframe()
        dataframe.loc[dataframe.index[-1], "adx_14"] = np.inf
        result = AnalysisEngine().analyze(self._build_dataset(dataframe))
        self.assertEqual(result.market_state, "NEUTRAL")
        self.assertEqual(result.strength, 0.0)
        self.assertIn("INVALID_REQUIRED_INDICATORS", result.warnings)

    def test_non_numeric_required_indicator_fails_closed(self) -> None:
        dataframe = self._build_dataframe()
        dataframe.loc[dataframe.index[-1], "momentum_5"] = "invalid"
        result = AnalysisEngine().analyze(self._build_dataset(dataframe))
        self.assertEqual(result.market_state, "NEUTRAL")
        self.assertEqual(result.strength, 0.0)
        self.assertIn("INVALID_REQUIRED_INDICATORS", result.warnings)

    def test_empty_dataset_is_safe(self) -> None:
        metadata = MarketMetadata(
            symbol="BTCUSDT",
            exchange="BINANCE",
            source="TEST",
            cache_version="1.0.0",
            downloaded_at=datetime(2026, 1, 1),
            last_updated_at=datetime(2026, 1, 1),
        )
        result = AnalysisEngine().analyze(MarketDataset(metadata=metadata))
        self.assertEqual(result.market_state, "NEUTRAL")
        self.assertEqual(result.strength, 0.0)
        self.assertIn("EMPTY_DATASET", result.warnings)

    def test_analysis_does_not_add_state_to_market_dataset(self) -> None:
        dataframe = self._build_dataframe()
        dataset = self._build_dataset(dataframe)
        timeframe_data = dataset.get_timeframe(Timeframe.H1)
        self.assertIsNotNone(timeframe_data)
        assert timeframe_data is not None
        before_columns = list(timeframe_data.dataframe.columns)
        AnalysisEngine().analyze(dataset)
        self.assertEqual(before_columns, list(timeframe_data.dataframe.columns))
        self.assertFalse(hasattr(timeframe_data, "analysis_ready"))
        self.assertFalse(hasattr(timeframe_data, "profile_ready"))
        self.assertFalse(hasattr(dataset, "analysis_result"))

    def test_bearish_alignment_is_detected(self) -> None:
        dataset = self._build_dataset(self._build_dataframe(bullish=False))
        result = AnalysisEngine().analyze(dataset)
        self.assertEqual(result.market_state, "BEARISH")
        self.assertIn("EMA_ALIGNMENT_BEARISH", result.signals)

    def test_strength_is_bounded(self) -> None:
        result = AnalysisEngine().analyze(self._build_dataset(self._build_dataframe()))
        self.assertGreaterEqual(result.strength, 0.0)
        self.assertLessEqual(result.strength, 100.0)


if __name__ == "__main__":
    unittest.main()
