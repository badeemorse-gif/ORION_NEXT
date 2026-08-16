import unittest
from datetime import datetime, timezone

import pandas as pd

from enums import DataHealth, Timeframe
from engines.opportunity_intelligence import CoreOpportunityEvidence, OpportunityCandidateGenerator, OpportunityIntelligenceError, OpportunitySelectionPolicy
from models.analysis import AnalysisResult
from models.market import MarketDataset, MarketMetadata, TimeframeData
from models.opportunity import FreshnessStatus, OpportunityDirection, RiskState
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics, TimeframeProfile
from models.score import ScoreResult


class TestOpportunityIntegrationFixes(unittest.TestCase):
    def evidence(self, *, requested_timeframe="5m", dataset_timeframes=(Timeframe.M5,), profiles=None,
                 aggregate_trend="Sideways", risk_level="Medium", category="BULLISH",
                 freshness=FreshnessStatus.FRESH, analysis_strength=80.0):
        now = datetime.now(timezone.utc)
        dataset = MarketDataset(metadata=MarketMetadata(
            symbol="BTCUSDT", exchange="BINANCE", source="TEST", cache_version="TEST",
            downloaded_at=now, last_updated_at=now, is_valid=True,
        ))
        for timeframe in dataset_timeframes:
            start = 100.0 if timeframe is Timeframe.M5 else 200.0
            dataset.add_timeframe(TimeframeData(
                timeframe=timeframe, dataframe=pd.DataFrame({"close": [start, start + 1.0]}),
                data_health=DataHealth.GOOD, candles_count=2,
                first_timestamp=now, last_timestamp=now,
            ))
        profiles = profiles or {"5m": ("Bullish", "Bullish", risk_level, 80.0)}
        timeframe_profiles = []
        for name, (trend, alignment, risk, confidence) in profiles.items():
            timeframe_profiles.append(TimeframeProfile(
                timeframe=name,
                characteristics=MarketCharacteristics(
                    trend=trend, ema_alignment=alignment,
                    momentum="Buy" if trend == "Bullish" else "Sell",
                    volatility_level="Normal", risk_level=risk, confidence=confidence,
                ),
                candles_count=2, first_timestamp=now, last_timestamp=now,
            ))
        profile = ProfileResult(
            symbol="BTCUSDT",
            market=MarketCharacteristics(trend=aggregate_trend, confidence=20.0),
            statistics=ProfileStatistics(completion_ratio=1.0, total_candles=2),
            timeframes=tuple(timeframe_profiles), is_tradeable=True, generated_at=now,
        )
        analysis = AnalysisResult(market_state="BULLISH", strength=analysis_strength,
                                  signals=("EMA_ALIGNMENT_BULLISH",))
        score = ScoreResult(score=40.0, category=category, factors=("EMA_ALIGNMENT_BULLISH",))
        return CoreOpportunityEvidence(dataset=dataset, analysis=analysis, profile=profile,
                                       score=score, timeframe=requested_timeframe,
                                       freshness=freshness)

    def test_risk_contract_low_medium_high_extreme_unknown(self):
        expected = {"Low": RiskState.ACCEPTABLE, "Medium": RiskState.ACCEPTABLE,
                    "High": RiskState.ELEVATED, "Extreme": RiskState.UNACCEPTABLE,
                    "Unknown": RiskState.UNKNOWN}
        for level, state in expected.items():
            evidence = self.evidence(risk_level=level)
            candidate = OpportunityCandidateGenerator().generate(evidence).opportunities[0]
            self.assertEqual(candidate.risk.state, state, level)
            result = OpportunitySelectionPolicy().select(
                OpportunityCandidateGenerator().generate(evidence), evidence
            )
            if state is not RiskState.ACCEPTABLE:
                self.assertIsNone(result.selected)
                self.assertFalse(result.readiness.eligible)
                self.assertTrue(any("risk gate" in r for r in result.evaluations[0].reasons))

    def test_matching_timeframe_uses_timeframe_profile(self):
        evidence = self.evidence(
            aggregate_trend="Bearish",
            profiles={"5m": ("Bullish", "Bullish", "Medium", 80.0),
                      "15m": ("Bearish", "Bearish", "High", 10.0)},
            analysis_strength=10.0,
        )
        candidate = OpportunityCandidateGenerator().generate(evidence).opportunities[0]
        self.assertEqual(candidate.direction, OpportunityDirection.LONG)
        self.assertEqual(candidate.confidence, 80.0)
        self.assertNotEqual(candidate.confidence, evidence.analysis.strength)
        self.assertIn("trend=Bullish", candidate.market_context)

    def test_missing_timeframe_fails_closed(self):
        evidence = self.evidence(profiles={"15m": ("Bullish", "Bullish", "Medium", 80.0)})
        with self.assertRaises(OpportunityIntelligenceError):
            OpportunityCandidateGenerator().generate(evidence)

    def test_dataset_timeframe_mismatch_fails_closed(self):
        evidence = self.evidence(dataset_timeframes=(Timeframe.M15,))
        with self.assertRaises(OpportunityIntelligenceError):
            OpportunityCandidateGenerator().generate(evidence)

    def test_same_symbol_different_timeframes_use_requested_profile(self):
        evidence = self.evidence(
            requested_timeframe="15m", dataset_timeframes=(Timeframe.M5, Timeframe.M15),
            profiles={"5m": ("Bullish", "Bullish", "Medium", 80.0),
                      "15m": ("Bearish", "Bearish", "Low", 90.0)},
            analysis_strength=10.0,
        )
        candidate = OpportunityCandidateGenerator().generate(evidence).opportunities[0]
        self.assertEqual(candidate.timeframe, "15m")
        self.assertEqual(candidate.entry_candidate, 201.0)
        self.assertEqual(candidate.confidence, 90.0)
        self.assertNotEqual(candidate.confidence, evidence.analysis.strength)
        self.assertIn("trend=Bearish", candidate.market_context)

    def test_setup_quality_is_unavailable_and_selection_fails_closed(self):
        evidence = self.evidence()
        candidates = OpportunityCandidateGenerator().generate(evidence)
        self.assertIsNone(candidates.opportunities[0].setup_quality)
        result = OpportunitySelectionPolicy().select(candidates, evidence)
        self.assertIsNone(result.selected)
        self.assertFalse(result.readiness.eligible)
        self.assertFalse(result.readiness.confidence_acceptable)
        self.assertTrue(any("setup quality evidence is unavailable in Core" in r
                            for r in result.evaluations[0].reasons))

    def test_freshness_still_fails_closed_without_age_threshold(self):
        evidence = self.evidence(freshness=FreshnessStatus.STALE)
        result = OpportunitySelectionPolicy().select(
            OpportunityCandidateGenerator().generate(evidence), evidence
        )
        self.assertIsNone(result.selected)
        self.assertTrue(any("freshness gate" in r for r in result.evaluations[0].reasons))


if __name__ == "__main__":
    unittest.main()
