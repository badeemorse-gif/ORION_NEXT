import unittest
from datetime import datetime, timezone

import pandas as pd

from enums import DataHealth, Timeframe
from engines.opportunity_intelligence import (
    CoreOpportunityEvidence,
    OpportunityCandidateGenerator,
    OpportunityIntelligenceError,
    OpportunitySelectionPolicy,
)
from models.analysis import AnalysisResult
from models.market import MarketDataset, MarketMetadata, TimeframeData
from models.opportunity import FreshnessStatus, OpportunityDirection
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics, TimeframeProfile
from models.score import ScoreResult


class TestOpportunityIntelligence(unittest.TestCase):
    @staticmethod
    def _evidence(
        market_state="BULLISH",
        trend="Bullish",
        alignment="Bullish",
        category="BULLISH",
        freshness=FreshnessStatus.FRESH,
        risk_level="Medium",
        is_tradeable=True,
    ) -> CoreOpportunityEvidence:
        now = datetime.now(timezone.utc)
        metadata = MarketMetadata(
            symbol="BTCUSDT",
            exchange="BINANCE",
            source="TEST",
            cache_version="TEST",
            downloaded_at=now,
            last_updated_at=now,
            is_valid=True,
        )
        dataset = MarketDataset(metadata=metadata)
        frame = pd.DataFrame({"close": [100.0, 101.0]})
        dataset.add_timeframe(
            TimeframeData(
                timeframe=Timeframe.M5,
                dataframe=frame,
                data_health=DataHealth.GOOD,
                candles_count=2,
                first_timestamp=now,
                last_timestamp=now,
            )
        )
        characteristics = MarketCharacteristics(
            trend=trend,
            ema_alignment=alignment,
            momentum="Buy" if trend == "Bullish" else "Sell",
            volatility_level="Normal",
            risk_level=risk_level,
            confidence=80.0,
            trend_score=80.0,
            momentum_score=80.0,
        )
        timeframe_profile = TimeframeProfile(
            timeframe="5m",
            characteristics=characteristics,
            candles_count=2,
            first_timestamp=now,
            last_timestamp=now,
        )
        profile = ProfileResult(
            symbol="BTCUSDT",
            market=characteristics,
            statistics=ProfileStatistics(
                health_score=100.0,
                confidence_limit=80.0,
                completion_ratio=1.0,
                total_candles=2,
                newest_candle=now,
                oldest_candle=now,
            ),
            timeframes=(timeframe_profile,),
            is_tradeable=is_tradeable,
            generated_at=now,
        )
        analysis = AnalysisResult(
            market_state=market_state,
            strength=80.0,
            signals=("EMA_ALIGNMENT_BULLISH", "MOMENTUM_POSITIVE"),
        )
        score = ScoreResult(score=40.0, category=category, factors=("EMA_ALIGNMENT_BULLISH",))
        return CoreOpportunityEvidence(
            dataset=dataset,
            analysis=analysis,
            profile=profile,
            score=score,
            timeframe="5m",
            freshness=freshness,
        )

    def test_generation_uses_core_evidence_and_creates_candidate(self):
        evidence = self._evidence()
        result = OpportunityCandidateGenerator().generate(evidence)
        self.assertEqual(len(result), 1)
        candidate = result.opportunities[0]
        self.assertEqual(candidate.symbol, "BTCUSDT")
        self.assertEqual(candidate.direction, OpportunityDirection.LONG)
        self.assertEqual(candidate.entry_candidate, 101.0)
        self.assertIn("EMA_ALIGNMENT_BULLISH", candidate.supporting_evidence)
        self.assertIsNone(candidate.expected_move)

    def test_neutral_core_evidence_does_not_create_direction(self):
        with self.assertRaises(OpportunityIntelligenceError):
            OpportunityCandidateGenerator().generate(self._evidence(market_state="NEUTRAL"))

    def test_selection_accepts_only_consistent_core_evidence(self):
        evidence = self._evidence()
        candidates = OpportunityCandidateGenerator().generate(evidence)
        result = OpportunitySelectionPolicy().select(candidates, evidence)
        self.assertIsNotNone(result.selected)
        self.assertTrue(result.readiness.eligible)
        self.assertEqual(result.selected.direction, OpportunityDirection.LONG)

    def test_stale_candidate_is_rejected_without_invented_threshold(self):
        evidence = self._evidence(freshness=FreshnessStatus.STALE)
        candidates = OpportunityCandidateGenerator().generate(evidence)
        result = OpportunitySelectionPolicy().select(candidates, evidence)
        self.assertIsNone(result.selected)
        self.assertFalse(result.readiness.eligible)
        self.assertTrue(any("freshness gate" in reason for reason in result.evaluations[0].reasons))

    def test_extreme_profile_risk_blocks_candidate_generation(self):
        with self.assertRaises(OpportunityIntelligenceError):
            OpportunityCandidateGenerator().generate(self._evidence(risk_level="Extreme"))

    def test_profile_direction_mismatch_is_rejected(self):
        evidence = self._evidence(trend="Bearish", alignment="Bearish")
        candidates = OpportunityCandidateGenerator().generate(evidence)
        result = OpportunitySelectionPolicy().select(candidates, evidence)
        self.assertIsNone(result.selected)
        self.assertTrue(result.evaluations[0].reasons)

    def test_score_direction_mismatch_is_rejected(self):
        evidence = self._evidence(category="BEARISH")
        candidates = OpportunityCandidateGenerator().generate(evidence)
        result = OpportunitySelectionPolicy().select(candidates, evidence)
        self.assertIsNone(result.selected)
        self.assertTrue(any("score category" in reason for reason in result.evaluations[0].reasons))


if __name__ == "__main__":
    unittest.main()
