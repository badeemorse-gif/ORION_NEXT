import unittest

from core.profile_intelligence import ProfileIntelligence
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics, TimeframeProfile


class TestProfileIntelligenceCompletionContract(unittest.TestCase):
    def _profile(self, names):
        characteristics = MarketCharacteristics(trend="Bullish", momentum="Buy", confidence=80.0, trend_score=80.0, momentum_score=70.0, volume_score=70.0, volatility_score=20.0)
        timeframes = tuple(TimeframeProfile(timeframe=name, characteristics=characteristics, candles_count=100, missing_candles=0) for name in names)
        statistics = ProfileStatistics(health_score=80.0, confidence_limit=80.0, completion_ratio=1.0, total_candles=100 * len(timeframes), missing_candles=0)
        return ProfileResult(symbol="BTCUSDT", market=characteristics, statistics=statistics, timeframes=timeframes, is_tradeable=True)
    def test_missing_required_timeframe_blocks(self):
        result=ProfileIntelligence().evaluate(self._profile(["1d","4h"])); self.assertTrue(result.blocked); self.assertEqual(result.recommendation,"Blocked")
    def test_duplicate_timeframe_blocks(self): self.assertTrue(ProfileIntelligence().evaluate(self._profile(["1d","4h","1h","1h"])).blocked)
    def test_complete_required_timeframes_can_be_actionable(self):
        result=ProfileIntelligence().evaluate(self._profile(["1d","4h","1h"])); self.assertFalse(result.blocked); self.assertTrue(result.is_directional)
if __name__ == "__main__": unittest.main()
