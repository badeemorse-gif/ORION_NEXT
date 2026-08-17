import unittest
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from enums import DataHealth, Timeframe
from engines.indicator_calculator import IndicatorCalculator
from engines.indicator_engine import IndicatorEngine, IndicatorEngineError
from engines.profile_builder import ProfileBuilder
from models.indicators import IndicatorResult
from models.market import MarketDataset, MarketMetadata, TimeframeData


CRITICAL = (
    "ema_9", "ema_20", "ema_50", "ema_100", "ema_200",
    "adx_14", "rsi_14", "momentum_5", "momentum_10", "mfi_14", "atr_14",
)


def make_ohlcv(rows: int = 250) -> pd.DataFrame:
    index = pd.date_range(
        "2026-01-01",
        periods=rows,
        freq="h",
        tz="UTC",
    )
    close = np.linspace(100.0, 200.0, rows)
    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.full(rows, 1000.0),
        },
        index=index,
    )


class TestIndicatorMetadataHandoffContract(unittest.TestCase):
    def _timeframe_data(self, dataframe: pd.DataFrame) -> TimeframeData:
        return TimeframeData(
            timeframe=Timeframe.H1,
            dataframe=dataframe,
            data_health=DataHealth.EXCELLENT,
            candles_count=len(dataframe),
            first_timestamp=dataframe.index[0].to_pydatetime(),
            last_timestamp=dataframe.index[-1].to_pydatetime(),
        )

    def test_successful_engine_publishes_indicator_result_metadata(self):
        timeframe_data = self._timeframe_data(make_ohlcv())
        result = IndicatorEngine().calculate_timeframe(timeframe_data, symbol="BTCUSDT")

        metadata = result.dataframe.attrs.get("indicator_result")
        self.assertIsInstance(metadata, IndicatorResult)
        self.assertEqual(metadata.quality, "SUFFICIENT")
        self.assertEqual(metadata.failed_indicators, [])
        self.assertTrue(set(CRITICAL).issubset(metadata.calculated_indicators))
        self.assertIs(result.dataframe.attrs["indicator_result"], metadata)
        self.assertTrue(np.isfinite(float(result.dataframe.iloc[-1]["ema_200"])))

    def test_profile_builder_consumes_handoff_naturally(self):
        timeframe_data = self._timeframe_data(make_ohlcv())
        result = IndicatorEngine().calculate_timeframe(timeframe_data, symbol="BTCUSDT")
        profile = ProfileBuilder().build(result.dataframe)
        self.assertIsNotNone(profile)

    def test_calculation_failure_publishes_insufficient_metadata(self):
        class FailingCalculator:
            def apply_all(self, dataframe):
                raise RuntimeError("boom")

            def validate_required_indicators(self, dataframe):
                raise AssertionError("must not be reached after calculation failure")

        dataframe = make_ohlcv()
        timeframe_data = self._timeframe_data(dataframe)
        with self.assertRaises(IndicatorEngineError):
            IndicatorEngine(FailingCalculator()).calculate_timeframe(timeframe_data, symbol="BTCUSDT")

        metadata = dataframe.attrs.get("indicator_result")
        self.assertIsInstance(metadata, IndicatorResult)
        self.assertNotEqual(metadata.quality, "SUFFICIENT")
        self.assertTrue(set(CRITICAL).issubset(metadata.failed_indicators))
        self.assertTrue(metadata.warnings)

    def test_market_models_do_not_receive_profile_state(self):
        dataframe = make_ohlcv()
        timeframe_data = self._timeframe_data(dataframe)
        dataset = MarketDataset(
            metadata=MarketMetadata(
                symbol="BTCUSDT",
                exchange="BINANCE",
                source="test",
                cache_version="test",
                downloaded_at=datetime.now(timezone.utc),
                last_updated_at=datetime.now(timezone.utc),
            ),
            timeframes={Timeframe.H1: timeframe_data},
        )
        IndicatorEngine().execute(dataset)
        self.assertFalse(hasattr(dataset, "profile"))
        self.assertFalse(hasattr(timeframe_data, "profile"))
        self.assertFalse(hasattr(timeframe_data, "profile_result"))


if __name__ == "__main__":
    unittest.main()
