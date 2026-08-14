import unittest
from datetime import datetime, timezone

import pandas as pd

from enums import DataHealth, Timeframe
from engines.opportunity_intelligence import CoreOpportunityEvidence, OpportunityCandidateGenerator
from models.analysis import AnalysisResult
from models.market import MarketDataset, MarketMetadata, TimeframeData
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics, TimeframeProfile
from models.score import ScoreResult


class TestOpportunityConfidenceContract(unittest.TestCase):
    def _evidence(self, analysis_strength: float, profile_confidence: float) -> CoreOpportunityEvidence:
        now = datetime.now(timezone.utc)
        dataset = MarketDataset(metadata=MarketMetadata(
            symbol="BTCUSDT", exchange="TEST", source="TEST", cache_version="TEST",
            downloaded_at=now, last_updated_at=now, is_valid=True,
        ))
        dataset.add_timeframe(TimeframeData(
            timeframe=Timeframe.M5,
            dataframe=pd.DataFrame({"close": [100.0, 101.0]}),
            data_health=DataHealth.GOOD,
            candles_count=2,
            first_timestamp=now,
            last_timestamp=now,
        ))
        timeframe_profile = TimeframeProfile(
            timeframe="5m",
            characteristics=MarketCharacteristics(
                trend="Bullish", ema_alignment="Bullish", momentum="Buy",
                volatility_level="Normal", risk_level="Medium", confidence=profile_confidence,
            ),
            candles_count=2, first_timestamp=now, last_timestamp=now,
        )
        profile = ProfileResult(
            symbol="BTCUSDT",
            market=MarketCharacteristics(trend="Sideways", confidence=5.0),
            statistics=ProfileStatistics(completion_ratio=1.0, total_candles=2),
            timeframes=(timeframe_profile,), is_tradeable=True, generated_at=now,
        )
        return CoreOpportunityEvidence(
            dataset=dataset,
            analysis=AnalysisResult(market_state="BULLISH", strength=analysis_strength,
                                    signals=("EMA_ALIGNMENT_BULLISH",)),
            profile=profile,
            score=ScoreResult(score=40.0, category="BULLISH",
                              factors=("EMA_ALIGNMENT_BULLISH",)),
            timeframe="5m",
        )

    def test_confidence_uses_canonical_timeframe_profile_only(self):
        evidence = self._evidence(analysis_strength=10.0, profile_confidence=80.0)
        candidate = OpportunityCandidateGenerator().generate(evidence).opportunities[0]
        self.assertEqual(candidate.confidence, 80.0)

    def test_analysis_strength_is_not_used_as_opportunity_confidence(self):
        evidence = self._evidence(analysis_strength=95.0, profile_confidence=30.0)
        candidate = OpportunityCandidateGenerator().generate(evidence).opportunities[0]
        self.assertEqual(candidate.confidence, 30.0)
        self.assertNotEqual(candidate.confidence, evidence.analysis.strength)


if __name__ == "__main__":
    unittest.main()
