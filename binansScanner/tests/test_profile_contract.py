import inspect
import unittest
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from enums import DataHealth, Timeframe

from engines.profile_builder import ProfileBuilder
from engines.profile_engine import ProfileEngine
from models.indicators import IndicatorResult
from models.market import MarketDataset, MarketMetadata, TimeframeData
from models.profile import ProfileResult


class TestProfileContract(unittest.TestCase):
    def _empty_dataset(self) -> MarketDataset:
        metadata = MarketMetadata(
            symbol="BTCUSDT",
            exchange="BINANCE",
            source="TEST",
            cache_version="TEST",
            downloaded_at=datetime.now(timezone.utc),
            last_updated_at=datetime.now(timezone.utc),
            is_valid=True,
        )
        return MarketDataset(metadata=metadata)

    def _prepared_timeframe(self) -> TimeframeData:
        index = pd.date_range("2026-01-01", periods=250, freq="1h", tz="UTC")
        base = np.linspace(100.0, 150.0, len(index))
        df = pd.DataFrame({
            "open": base, "high": base + 2.0, "low": base - 2.0,
            "close": base + 1.0, "volume": np.linspace(1000.0, 2000.0, len(index)),
        }, index=index)
        for name in ("ema_9", "ema_20", "ema_50", "ema_100", "ema_200", "adx_14", "rsi_14", "momentum_5", "momentum_10", "mfi_14", "atr_14"):
            df[name] = 1.0
        df["ema_20"] = np.linspace(110.0, 120.0, len(index))
        df["ema_50"] = np.linspace(105.0, 115.0, len(index))
        df["ema_100"] = np.linspace(102.0, 112.0, len(index))
        df["ema_200"] = np.linspace(101.0, 111.0, len(index))
        df["ema_9"] = np.linspace(112.0, 122.0, len(index))
        df["adx_14"] = 30.0
        df["rsi_14"] = 60.0
        df["mfi_14"] = 60.0
        df["atr_14"] = 1.0
        df["momentum_5"] = 1.0
        df["momentum_10"] = 1.0
        df.attrs["indicator_result"] = IndicatorResult(quality="SUFFICIENT", calculated_indicators=["ema_9", "ema_20", "ema_50", "ema_100", "ema_200", "adx_14", "rsi_14", "momentum_5", "momentum_10", "mfi_14", "atr_14"])
        return TimeframeData(timeframe=Timeframe.H1, dataframe=df, data_health=DataHealth.GOOD, candles_count=len(df), first_timestamp=df.index[0].to_pydatetime(), last_timestamp=df.index[-1].to_pydatetime())

    def _profile_result(self, timeframe_data: TimeframeData) -> ProfileResult:
        dataset = self._empty_dataset()
        dataset.add_timeframe(timeframe_data)
        return ProfileEngine().build_profile(dataset)

    def test_missing_critical_indicator_fails_closed(self):
        timeframe_data = self._prepared_timeframe()
        timeframe_data.dataframe = timeframe_data.dataframe.drop(columns=["ema_20"])
        result = self._profile_result(timeframe_data)
        self.assertFalse(result.is_tradeable)
        self.assertTrue(any("missing critical indicators" in block for block in result.blocks))

    def test_nan_critical_indicator_fails_closed(self):
        timeframe_data = self._prepared_timeframe()
        timeframe_data.dataframe.loc[timeframe_data.dataframe.index[-1], "rsi_14"] = np.nan
        result = self._profile_result(timeframe_data)
        self.assertFalse(result.is_tradeable)
        self.assertTrue(any("invalid critical indicators" in block for block in result.blocks))

    def test_failed_indicator_metadata_fails_closed(self):
        timeframe_data = self._prepared_timeframe()
        timeframe_data.dataframe.attrs["indicator_result"] = IndicatorResult(quality="FAILED", failed_indicators=["rsi_14"])
        result = self._profile_result(timeframe_data)
        self.assertFalse(result.is_tradeable)
        self.assertTrue(any("indicator metadata reports failed" in block for block in result.blocks))

    def test_missing_indicator_metadata_fails_closed(self):
        timeframe_data = self._prepared_timeframe()
        timeframe_data.dataframe.attrs.pop("indicator_result", None)
        with self.assertRaisesRegex(ValueError, "indicator metadata is missing"):
            ProfileBuilder().build(timeframe_data.dataframe)

    def test_incomplete_indicator_metadata_fails_closed(self):
        timeframe_data = self._prepared_timeframe()
        timeframe_data.dataframe.attrs["indicator_result"] = IndicatorResult(
            quality="SUFFICIENT",
            calculated_indicators=[
                "ema_9", "ema_20", "ema_50", "ema_100", "ema_200",
                "adx_14", "rsi_14", "momentum_5", "momentum_10",
                "mfi_14",
            ],
        )
        with self.assertRaisesRegex(ValueError, "calculated critical indicators are incomplete"):
            ProfileBuilder().build(timeframe_data.dataframe)

    def test_valid_complete_indicators_produce_tradeable_profile(self):
        result = self._profile_result(self._prepared_timeframe())
        self.assertTrue(result.is_tradeable)
        self.assertEqual(len(result.blocks), 0)
        self.assertEqual(len(result.timeframes), 1)

    def test_profile_builder_rejects_invalid_indicator_metadata(self):
        timeframe_data = self._prepared_timeframe()
        timeframe_data.dataframe.attrs["indicator_result"] = IndicatorResult(quality="FAILED", failed_indicators=["ema_20"])
        with self.assertRaises(ValueError):
            ProfileBuilder().build(timeframe_data.dataframe)

    def test_profile_engine_exposes_canonical_result_boundary(self):
        method = getattr(ProfileEngine, "build_profile", None)

        self.assertIsNotNone(
            method,
            "ProfileEngine must expose build_profile().",
        )

        signature = inspect.signature(method)

        self.assertIn("dataset", signature.parameters)

    def test_profile_engine_returns_profile_result_for_empty_dataset(self):
        engine = ProfileEngine()
        dataset = self._empty_dataset()

        result = engine.build_profile(dataset)

        self.assertIsInstance(result, ProfileResult)
        self.assertEqual(result.symbol, "BTCUSDT")

    def test_profile_result_does_not_require_market_dataset(self):
        fields = {
            field.name
            for field in getattr(ProfileResult, "__dataclass_fields__", {}).values()
        }

        self.assertNotIn("dataset", fields)
        self.assertNotIn("market_dataset", fields)

    def test_profile_engine_does_not_store_profile_on_market_dataset(self):
        engine = ProfileEngine()
        dataset = self._empty_dataset()

        engine.build_profile(dataset)

        self.assertFalse(
            hasattr(dataset, "profile"),
            "MarketDataset must not contain ProfileResult state.",
        )

    def test_profile_engine_does_not_store_profile_state_on_timeframe_data(self):
        engine = ProfileEngine()
        dataset = self._empty_dataset()

        engine.build_profile(dataset)

        for timeframe_data in dataset.timeframes.values():
            self.assertFalse(hasattr(timeframe_data, "profile"))
            self.assertFalse(hasattr(timeframe_data, "profile_ready"))


if __name__ == "__main__":
    unittest.main()