import unittest

from core.profile_intelligence import ProfileIntelligence
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics, TimeframeProfile


class TestProfileIntelligenceCompletionContract(unittest.TestCase):
    REQUIRED_TIMEFRAMES = ("1d", "4h", "1h")

    def _profile(self, names):
        characteristics = MarketCharacteristics(
            trend="Bullish",
            momentum="Buy",
            confidence=80.0,
            trend_score=80.0,
            momentum_score=70.0,
            volume_score=70.0,
            volatility_score=20.0,
        )
        timeframes = tuple(
            TimeframeProfile(timeframe=name, characteristics=characteristics, candles_count=100, missing_candles=0)
            for name in names
        )
        statistics = ProfileStatistics(
            health_score=80.0,
            confidence_limit=80.0,
            completion_ratio=1.0,
            total_candles=100 * len(timeframes),
            missing_candles=0,
        )
        return ProfileResult(
            symbol="BTCUSDT",
            market=characteristics,
            statistics=statistics,
            timeframes=timeframes,
            is_tradeable=True,
        )

    def test_each_required_timeframe_is_contractually_mandatory(self):
        for missing in self.REQUIRED_TIMEFRAMES:
            with self.subTest(missing=missing):
                supplied = [name for name in self.REQUIRED_TIMEFRAMES if name != missing]
                result = ProfileIntelligence().evaluate(self._profile(supplied))
                self.assertTrue(result.blocked)
                self.assertEqual(result.recommendation, "Blocked")
                self.assertIn(missing, result.reasons[0])

    def test_duplicate_timeframe_blocks(self):
        result = ProfileIntelligence().evaluate(self._profile(["1d", "4h", "1h", "1h"]))
        self.assertTrue(result.blocked)

    def test_complete_required_timeframes_can_be_actionable(self):
        result = ProfileIntelligence().evaluate(self._profile(list(self.REQUIRED_TIMEFRAMES)))
        self.assertFalse(result.blocked)
        self.assertTrue(result.is_directional)


if __name__ == "__main__":
    unittest.main()
