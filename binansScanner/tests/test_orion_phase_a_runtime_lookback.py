from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pandas as pd

from enums import Timeframe
from tools.orion_phase_a_runtime_observer import CLOSED_CANDLE_LOOKBACK, CRITICAL_PROFILE_INDICATORS, LOOKBACK_REQUEST_BUFFER, _ClosedLookbackMarketSource


class FakeSource:
    def __init__(self, frame):
        self.frame = frame
        self._mapper = object()
        self.calls = []

    def download_timeframe(self, symbol, timeframe, limit=1000):
        self.calls.append((symbol, timeframe, limit))
        return self.frame.copy()


class TestPhaseARuntimeLookback(unittest.TestCase):
    def _frame(self, rows=252):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        index = pd.date_range(end=now, periods=rows, freq="h", tz="UTC")
        return pd.DataFrame({"open": [100.0] * rows, "high": [101.0] * rows, "low": [99.0] * rows, "close": [100.0] * rows, "volume": [100.0] * rows}, index=index)

    def test_requests_buffer_and_returns_250_closed(self):
        source = FakeSource(self._frame(252))
        adapter = _ClosedLookbackMarketSource(source, CLOSED_CANDLE_LOOKBACK)
        now = source.frame.index[-1].to_pydatetime()
        with patch("tools.orion_phase_a_runtime_observer._now", return_value=now):
            result = adapter.download_timeframe("BTCUSDT", Timeframe.H1)
        self.assertEqual(source.calls[0][2], CLOSED_CANDLE_LOOKBACK + LOOKBACK_REQUEST_BUFFER)
        self.assertEqual(len(result), CLOSED_CANDLE_LOOKBACK)
        self.assertTrue((result.index + timedelta(hours=1) <= now).all())
        self.assertEqual(result.index[-1], now - timedelta(hours=1))

    def test_insufficient_closed_history_fails_closed(self):
        source = FakeSource(self._frame(251))
        adapter = _ClosedLookbackMarketSource(source, CLOSED_CANDLE_LOOKBACK)
        now = source.frame.index[-1].to_pydatetime()
        with patch("tools.orion_phase_a_runtime_observer._now", return_value=now):
            with self.assertRaisesRegex(RuntimeError, "INSUFFICIENT_CLOSED_LOOKBACK"):
                adapter.download_timeframe("ETHUSDT", Timeframe.H4)

    def test_critical_indicator_contract_is_exactly_eleven(self):
        self.assertEqual(CRITICAL_PROFILE_INDICATORS, ("ema_9", "ema_20", "ema_50", "ema_100", "ema_200", "adx_14", "rsi_14", "momentum_5", "momentum_10", "mfi_14", "atr_14"))
        self.assertEqual(len(CRITICAL_PROFILE_INDICATORS), 11)

    def test_execution_boundary_is_observation_only(self):
        from tools.orion_phase_a_runtime_observer import create_runtime_config
        config = create_runtime_config(baseline_commit="c54dc67792776da905a3efb1f667c1869c15db3d", symbols=("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"), timeframes=("1h", "4h", "1d"), configuration={"execution": {"paper": False, "live": False}})
        self.assertFalse(config.configuration["execution"]["paper"])
        self.assertFalse(config.configuration["execution"]["live"])


if __name__ == "__main__": unittest.main()
