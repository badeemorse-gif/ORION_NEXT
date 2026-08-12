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
        timeframe_characteristics=None,
        missing_candles=0,
        timeframe_candles_count=100,
        timeframe_missing_candles=None,
        timeframe_name="1h",
        total_candles=100,
        statistics_missing_candles=None,
        symbol="BTCUSDT",
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

        if statistics_missing_candles is None:
            statistics_missing_candles = missing_candles
        if timeframe_missing_candles is None:
            timeframe_missing_candles = missing_candles

        statistics = ProfileStatistics(
            health_score=80.0,
            confidence_limit=confidence,
            completion_ratio=completion_ratio,
            total_candles=total_candles,
            missing_candles=statistics_missing_candles,
        )

        profiles = ()
        if timeframes:
            profiles = (
                TimeframeProfile(
                    timeframe=timeframe_name,
                    characteristics=timeframe_characteristics or market,
                    candles_count=timeframe_candles_count,
                    first_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    last_timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
                    missing_candles=timeframe_missing_candles,
                ),
            )

        return ProfileResult(
            symbol=symbol,
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
        self.assertIn("invalid market trend", result.reasons[0])

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

    def test_extreme_timeframe_risk_blocks_directional_intelligence(self):
        timeframe_risk = MarketCharacteristics(
            trend="Bullish",
            momentum="Buy",
            risk_level="Extreme",
            confidence=80.0,
            trend_score=80.0,
            momentum_score=75.0,
            volume_score=60.0,
            volatility_score=40.0,
        )
        profile = self._profile(timeframe_characteristics=timeframe_risk)

        result = self.intelligence.evaluate(profile)

        self.assertEqual(result.recommendation, ProfileRecommendation.NEUTRAL.value)
        self.assertTrue(result.blocked)
        self.assertEqual(result.confidence, 0.0)
        self.assertIn("one or more timeframes", result.reasons[0])

    def test_malformed_timeframe_characteristics_fail_closed(self):
        malformed = MarketCharacteristics(
            trend="NOT_A_TREND",
            momentum="Buy",
            risk_level="Medium",
            confidence=80.0,
        )
        profile = self._profile(timeframe_characteristics=malformed)

        result = self.intelligence.evaluate(profile)

        self.assertEqual(result.recommendation, ProfileRecommendation.BLOCKED.value)
        self.assertTrue(result.blocked)
        self.assertFalse(result.is_directional)
        self.assertIn("timeframe 1h trend", result.reasons[0])

    def test_non_finite_timeframe_confidence_fails_closed(self):
        malformed = MarketCharacteristics(
            trend="Bullish",
            momentum="Buy",
            risk_level="Medium",
            confidence=float("nan"),
        )
        profile = self._profile(timeframe_characteristics=malformed)

        result = self.intelligence.evaluate(profile)

        self.assertEqual(result.recommendation, ProfileRecommendation.BLOCKED.value)
        self.assertTrue(result.blocked)
        self.assertEqual(result.confidence, 0.0)
        self.assertIn("non-finite timeframe 1h confidence", result.reasons[0])

    def test_zero_timeframe_confidence_blocks_directional_intelligence(self):
        low_confidence = MarketCharacteristics(
            trend="Bullish",
            momentum="Buy",
            risk_level="Medium",
            confidence=0.0,
            trend_score=80.0,
            momentum_score=75.0,
            volume_score=60.0,
            volatility_score=40.0,
        )
        profile = self._profile(timeframe_characteristics=low_confidence)

        result = self.intelligence.evaluate(profile)

        self.assertEqual(result.recommendation, ProfileRecommendation.BLOCKED.value)
        self.assertTrue(result.blocked)
        self.assertFalse(result.is_directional)
        self.assertEqual(result.confidence, 0.0)
        self.assertIn("positive confidence across the complete profile", result.reasons[0])

    def test_empty_timeframe_coverage_fails_closed(self):
        profile = self._profile(timeframe_candles_count=0)

        result = self.intelligence.evaluate(profile)

        self.assertEqual(result.recommendation, ProfileRecommendation.BLOCKED.value)
        self.assertTrue(result.blocked)
        self.assertFalse(result.is_directional)
        self.assertIn("no candle coverage in timeframe 1h", result.reasons[0])

    def test_incomplete_timeframe_coverage_fails_closed(self):
        profile = self._profile(
            timeframe_candles_count=100,
            timeframe_missing_candles=100,
        )

        result = self.intelligence.evaluate(profile)

        self.assertEqual(result.recommendation, ProfileRecommendation.BLOCKED.value)
        self.assertTrue(result.blocked)
        self.assertFalse(result.is_directional)
        self.assertIn("incomplete candle coverage in timeframe 1h", result.reasons[0])

    def test_invalid_timeframe_name_fails_closed(self):
        profile = self._profile(timeframe_name="2h")

        result = self.intelligence.evaluate(profile)

        self.assertEqual(result.recommendation, ProfileRecommendation.BLOCKED.value)
        self.assertTrue(result.blocked)
        self.assertFalse(result.is_directional)
        self.assertIn("unsupported timeframe", result.reasons[0])

    def test_non_integer_timeframe_coverage_fails_closed(self):
        profile = self._profile(timeframe_candles_count=100.5)

        result = self.intelligence.evaluate(profile)

        self.assertEqual(result.recommendation, ProfileRecommendation.BLOCKED.value)
        self.assertTrue(result.blocked)
        self.assertFalse(result.is_directional)
        self.assertIn("invalid candles_count", result.reasons[0])

    def test_empty_aggregate_coverage_fails_closed(self):
        profile = self._profile(total_candles=0)

        result = self.intelligence.evaluate(profile)

        self.assertEqual(result.recommendation, ProfileRecommendation.BLOCKED.value)
        self.assertTrue(result.blocked)
        self.assertFalse(result.is_directional)
        self.assertIn("no aggregate candle coverage", result.reasons[0])

    def test_impossible_aggregate_coverage_fails_closed(self):
        profile = self._profile(
            missing_candles=101,
            statistics_missing_candles=101,
            timeframe_missing_candles=0,
        )

        result = self.intelligence.evaluate(profile)

        self.assertEqual(result.recommendation, ProfileRecommendation.BLOCKED.value)
        self.assertTrue(result.blocked)
        self.assertIn("incomplete aggregate candle coverage", result.reasons[0])

    def test_inconsistent_aggregate_completion_ratio_fails_closed(self):
        profile = self._profile(
            completion_ratio=0.5,
            total_candles=100,
            statistics_missing_candles=0,
        )

        result = self.intelligence.evaluate(profile)

        self.assertEqual(result.recommendation, ProfileRecommendation.BLOCKED.value)
        self.assertTrue(result.blocked)
        self.assertFalse(result.is_directional)
        self.assertIn("inconsistent aggregate completion ratio", result.reasons[0])

    def test_non_string_market_category_fails_closed_without_exception(self):
        profile = self._profile(trend=["Bullish"])

        result = self.intelligence.evaluate(profile)

        self.assertEqual(result.recommendation, ProfileRecommendation.BLOCKED.value)
        self.assertTrue(result.blocked)
        self.assertFalse(result.is_directional)
        self.assertIn("invalid market trend", result.reasons[0])

    def test_invalid_tradeable_state_fails_closed(self):
        profile = self._profile(is_tradeable=1)

        result = self.intelligence.evaluate(profile)

        self.assertEqual(result.recommendation, ProfileRecommendation.BLOCKED.value)
        self.assertTrue(result.blocked)
        self.assertFalse(result.is_directional)
        self.assertIn("tradeable-state flag", result.reasons[0])

    def test_invalid_symbol_fails_closed(self):
        profile = self._profile(symbol="   ")

        result = self.intelligence.evaluate(profile)

        self.assertEqual(result.recommendation, ProfileRecommendation.BLOCKED.value)
        self.assertTrue(result.blocked)
        self.assertFalse(result.is_directional)
        self.assertIn("invalid symbol", result.reasons[0])


if __name__ == "__main__":
    unittest.main()
