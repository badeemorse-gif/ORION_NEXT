from __future__ import annotations

import unittest
from datetime import datetime, timezone

from core.intelligence_contract import (
    IntelligenceContractError,
    validate_analysis,
    validate_decision,
    validate_profile,
    validate_score,
)
from models.analysis import AnalysisResult
from models.decision import DecisionResult
from models.profile import (
    MarketCharacteristics,
    ProfileResult,
    ProfileStatistics,
    TimeframeProfile,
)
from models.score import ScoreResult


class TestIntelligenceContract(unittest.TestCase):
    def _profile(self, *, warnings: tuple[str, ...] = ()) -> ProfileResult:
        now = datetime.now(timezone.utc)
        characteristics = MarketCharacteristics(
            trend="Bullish",
            trend_strength="Strong",
            momentum="Buy",
            volume_strength="Strong",
            volatility_level="Normal",
            ema_alignment="Bullish",
            market_phase="Markup",
            risk_level="Medium",
            confidence=80.0,
            trend_score=80.0,
            momentum_score=80.0,
            volume_score=80.0,
            volatility_score=40.0,
        )
        statistics = ProfileStatistics(
            health_score=80.0,
            confidence_limit=80.0,
            completion_ratio=1.0,
            total_candles=100,
            missing_candles=0,
        )
        timeframe = TimeframeProfile(
            timeframe="1h",
            characteristics=characteristics,
            candles_count=100,
            first_timestamp=now,
            last_timestamp=now,
            missing_candles=0,
        )
        return ProfileResult(
            symbol="BTCUSDT",
            market=characteristics,
            statistics=statistics,
            timeframes=(timeframe,),
            warnings=warnings,
            is_tradeable=True,
        )

    def test_directional_analysis_cannot_carry_fail_closed_warning(self):
        analysis = AnalysisResult(
            market_state="BULLISH",
            strength=80.0,
            warnings=["MISSING_REQUIRED_INDICATORS"],
        )
        with self.assertRaises(IntelligenceContractError):
            validate_analysis(analysis)

    def test_warning_bearing_profile_is_not_actionable(self):
        with self.assertRaises(IntelligenceContractError):
            validate_profile(self._profile(warnings=("PROFILE_WARNING",)))

    def test_score_category_must_match_score(self):
        score = ScoreResult(
            score=70.0,
            category="NEUTRAL",
            factors=[],
            warnings=[],
        )
        with self.assertRaises(IntelligenceContractError):
            validate_score(score)

    def test_wait_decision_requires_zero_actionable_confidence(self):
        analysis = AnalysisResult(market_state="NEUTRAL", strength=50.0)
        score = ScoreResult(score=0.0, category="NEUTRAL", factors=[], warnings=[])
        decision = DecisionResult(decision="WAIT", confidence=80.0)
        with self.assertRaises(IntelligenceContractError):
            validate_decision(analysis, score, decision)

    def test_favorable_decision_requires_strong_bullish_analysis_and_score(self):
        analysis = AnalysisResult(market_state="BULLISH", strength=80.0)
        score = ScoreResult(score=40.0, category="BULLISH", factors=[], warnings=[])
        decision = DecisionResult(decision="FAVORABLE", confidence=40.0)
        with self.assertRaises(IntelligenceContractError):
            validate_decision(analysis, score, decision)


if __name__ == "__main__":
    unittest.main()
