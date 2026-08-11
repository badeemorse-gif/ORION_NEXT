import unittest
from datetime import datetime, timezone

from core.profile_intelligence import (
    ProfileIntelligence,
    ProfileIntelligenceResult,
    ProfileRecommendation,
)
from models.profile import (
    MarketCharacteristics,
    ProfileResult,
    ProfileStatistics,
    TimeframeProfile,
)


class TestProfileIntelligence(unittest.TestCase):
    def _profile(
        self,
        *,
        trend="Bullish",
        momentum="Buy",
        risk="Medium",
        confidence=80.0,
        completion_ratio=1.0,
        timeframes=True,
        is_tradeable=True,
    ) -> ProfileResult:
        market = MarketCharacteristics(
            trend=trend,
            momentum=momentum,
            risk_level=risk,
            confidence=confidence,
            trend_score=80.0,
            momentum_score=75.0,
            volume_score=60.0,
            volatility_score=40.0,
        )

        statistics = ProfileStatistics(
            health_score=80.0,
            confidence_limit=confidence,
            completion_ratio=completion_ratio,
            total_candles=100,
            missing_candles=0,
        )

        profiles = ()
        if timeframes:
            profiles = (
                TimeframeProfile(
                    timeframe="1h",
                    characteristics=market,
                    candles_count=100,
                    first_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    last_timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
                ),
            )

        return ProfileResult(
            symbol="BTCUSDT",
            market=market,
            statistics=statistics,
            timeframes=profiles,
            is_tradeable=is_tradeable,
        )

    def setUp(self):
        self.intelligence = ProfileIntelligence()

    def test_bullish_profile_is_deterministic(self):
        profile = self._profile(trend="Bullish", momentum="Buy")

        first = self.intelligence.evaluate(profile)
        second = self.intelligence.evaluate(profile)

        self.assertEqual(first, second)
        self.assertEqual(first.recommendation, ProfileRecommendation.BULLISH.value)
        self.assertEqual(first.confidence, 80.0)
        self.assertFalse(first.blocked)
        self.assertTrue(first.is_directional)

    def test_bearish_profile_is_deterministic(self):
        profile = self._profile(trend="Bearish", momentum="Sell")

        result = self.intelligence.evaluate(profile)

        self.assertEqual(result.recommendation, ProfileRecommendation.BEARISH.value)
        self.assertEqual(result.confidence, 80.0)
        self.assertFalse(result.blocked)

    def test_missing_profile_fails_closed(self):
        result = self.intelligence.evaluate(None)

        self.assertIsInstance(result, ProfileIntelligenceResult)
        self.assertEqual(result.recommendation, ProfileRecommendation.BLOCKED.value)
        self.assertEqual(result.confidence, 0.0)
        self.assertTrue(result.blocked)
        self.assertFalse(result.is_directional)

    def test_empty_profile_fails_closed(self):
        profile = self._profile(timeframes=False, is_tradeable=False)

        result = self.intelligence.evaluate(profile)

        self.assertEqual(result.recommendation, ProfileRecommendation.BLOCKED.value)
        self.assertEqual(result.confidence, 0.0)
        self.assertTrue(result.blocked)

    def test_malformed_profile_fails_closed(self):
        profile = self._profile(trend="NOT_A_TREND")

        result = self.intelligence.evaluate(profile)

        self.assertEqual(result.recommendation, ProfileRecommendation.BLOCKED.value)
        self.assertEqual(result.confidence, 0.0)
        self.assertTrue(result.blocked)
        self.assertIn("invalid trend", result.reasons[0])

    def test_mixed_valid_profile_is_neutral_not_directional(self):
        profile = self._profile(trend="Bullish", momentum="Neutral")

        result = self.intelligence.evaluate(profile)

        self.assertEqual(result.recommendation, ProfileRecommendation.NEUTRAL.value)
        self.assertFalse(result.blocked)
        self.assertFalse(result.is_directional)
        self.assertEqual(result.confidence, 80.0)

    def test_extreme_risk_blocks_directional_intelligence(self):
        profile = self._profile(
            trend="Bullish",
            momentum="Strong Buy",
            risk="Extreme",
        )

        result = self.intelligence.evaluate(profile)

        self.assertEqual(result.recommendation, ProfileRecommendation.NEUTRAL.value)
        self.assertTrue(result.blocked)
        self.assertEqual(result.confidence, 0.0)
        self.assertFalse(result.is_directional)


if __name__ == "__main__":
    unittest.main()
