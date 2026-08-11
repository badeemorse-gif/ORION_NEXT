"""
===============================================================================
ORION — Decision Contract Tests
===============================================================================

Canonical contract tests for the Decision layer.

DecisionEngine consumes:
    AnalysisResult
    ScoreResult

DecisionEngine returns:
    DecisionResult

The engine must:
    - remain independent from MarketDataset;
    - never execute trades;
    - preserve analysis warnings;
    - preserve relevant reasons/signals;
    - reject invalid inputs;
    - reject non-finite score values;
    - produce deterministic decision states.

===============================================================================
"""

from __future__ import annotations

import math
import unittest

from engines.decision_engine import (
    DecisionEngine,
    InvalidDecisionData,
    InvalidScoreData,
)
from models.analysis import AnalysisResult
from models.decision import DecisionResult
from models.score import ScoreResult


class TestDecisionContract(unittest.TestCase):
    """Canonical DecisionEngine contract tests."""

    def setUp(self) -> None:
        self.engine = DecisionEngine()

    def test_decision_engine_returns_canonical_result(self) -> None:
        analysis = AnalysisResult(
            market_state="BULLISH",
            strength=90.0,
            signals=["EMA_ALIGNMENT_BULLISH"],
            warnings=[],
        )

        score = ScoreResult(
            score=80.0,
            category="STRONG_BULLISH",
            factors=["EMA_ALIGNMENT_BULLISH"],
            warnings=[],
        )

        result = self.engine.decide(
            analysis,
            score,
        )

        self.assertIsInstance(
            result,
            DecisionResult,
        )

    def test_strong_bullish_analysis_produces_favorable_decision(self) -> None:
        analysis = AnalysisResult(
            market_state="BULLISH",
            strength=90.0,
            signals=[
                "EMA_ALIGNMENT_BULLISH",
                "STRONG_TREND",
            ],
            warnings=[],
        )

        score = ScoreResult(
            score=80.0,
            category="STRONG_BULLISH",
            factors=[
                "EMA_ALIGNMENT_BULLISH",
                "STRONG_TREND",
            ],
            warnings=[],
        )

        result = self.engine.decide(
            analysis,
            score,
        )

        self.assertEqual(
            result.decision,
            "FAVORABLE",
        )

    def test_strong_bearish_analysis_produces_unfavorable_decision(self) -> None:
        analysis = AnalysisResult(
            market_state="BEARISH",
            strength=90.0,
            signals=[
                "EMA_ALIGNMENT_BEARISH",
                "STRONG_TREND",
            ],
            warnings=[],
        )

        score = ScoreResult(
            score=-80.0,
            category="STRONG_BEARISH",
            factors=[
                "EMA_ALIGNMENT_BEARISH",
                "STRONG_TREND",
            ],
            warnings=[],
        )

        result = self.engine.decide(
            analysis,
            score,
        )

        self.assertEqual(
            result.decision,
            "UNFAVORABLE",
        )

    def test_neutral_conditions_produce_wait(self) -> None:
        analysis = AnalysisResult(
            market_state="NEUTRAL",
            strength=50.0,
            signals=[],
            warnings=[],
        )

        score = ScoreResult(
            score=0.0,
            category="NEUTRAL",
            factors=[],
            warnings=[],
        )

        result = self.engine.decide(
            analysis,
            score,
        )

        self.assertEqual(
            result.decision,
            "WAIT",
        )

    def test_non_strong_bullish_conditions_do_not_force_favorable(self) -> None:
        analysis = AnalysisResult(
            market_state="BULLISH",
            strength=70.0,
            signals=["EMA_ALIGNMENT_BULLISH"],
            warnings=[],
        )

        score = ScoreResult(
            score=35.0,
            category="BULLISH",
            factors=["EMA_ALIGNMENT_BULLISH"],
            warnings=[],
        )

        result = self.engine.decide(
            analysis,
            score,
        )

        self.assertEqual(
            result.decision,
            "WAIT",
        )

    def test_non_strong_bearish_conditions_do_not_force_unfavorable(self) -> None:
        analysis = AnalysisResult(
            market_state="BEARISH",
            strength=70.0,
            signals=["EMA_ALIGNMENT_BEARISH"],
            warnings=[],
        )

        score = ScoreResult(
            score=-35.0,
            category="BEARISH",
            factors=["EMA_ALIGNMENT_BEARISH"],
            warnings=[],
        )

        result = self.engine.decide(
            analysis,
            score,
        )

        self.assertEqual(
            result.decision,
            "WAIT",
        )

    def test_analysis_warnings_are_preserved(self) -> None:
        analysis = AnalysisResult(
            market_state="NEUTRAL",
            strength=50.0,
            signals=[],
            warnings=["MISSING_REQUIRED_INDICATORS"],
        )

        score = ScoreResult(
            score=0.0,
            category="NEUTRAL",
            factors=[],
            warnings=[],
        )

        result = self.engine.decide(
            analysis,
            score,
        )

        self.assertIn(
            "MISSING_REQUIRED_INDICATORS",
            result.warnings,
        )

    def test_score_factors_and_analysis_signals_are_preserved(self) -> None:
        analysis = AnalysisResult(
            market_state="BULLISH",
            strength=90.0,
            signals=["EMA_ALIGNMENT_BULLISH"],
            warnings=[],
        )

        score = ScoreResult(
            score=80.0,
            category="STRONG_BULLISH",
            factors=["STRONG_SCORE_FACTOR"],
            warnings=[],
        )

        result = self.engine.decide(
            analysis,
            score,
        )

        self.assertIn(
            "STRONG_SCORE_FACTOR",
            result.reasons,
        )

        self.assertIn(
            "EMA_ALIGNMENT_BULLISH",
            result.reasons,
        )

    def test_score_state_conflict_is_reported(self) -> None:
        analysis = AnalysisResult(
            market_state="BEARISH",
            strength=70.0,
            signals=["EMA_ALIGNMENT_BEARISH"],
            warnings=[],
        )

        score = ScoreResult(
            score=80.0,
            category="STRONG_BULLISH",
            factors=[],
            warnings=[],
        )

        result = self.engine.decide(
            analysis,
            score,
        )

        self.assertIn(
            "CONFLICT_SCORE_BULLISH_STATE_BEARISH",
            result.warnings,
        )

    def test_score_below_negative_hundred_is_rejected(self) -> None:
        analysis = AnalysisResult(
            market_state="BEARISH",
            strength=80.0,
            signals=[],
            warnings=[],
        )

        score = ScoreResult(
            score=-101.0,
            category="STRONG_BEARISH",
            factors=[],
            warnings=[],
        )

        with self.assertRaises(
            InvalidScoreData,
        ):
            self.engine.decide(
                analysis,
                score,
            )

    def test_score_above_hundred_is_rejected(self) -> None:
        analysis = AnalysisResult(
            market_state="BULLISH",
            strength=80.0,
            signals=[],
            warnings=[],
        )

        score = ScoreResult(
            score=101.0,
            category="STRONG_BULLISH",
            factors=[],
            warnings=[],
        )

        with self.assertRaises(
            InvalidScoreData,
        ):
            self.engine.decide(
                analysis,
                score,
            )

    def test_score_nan_is_rejected(self) -> None:
        analysis = AnalysisResult(
            market_state="BULLISH",
            strength=80.0,
            signals=[],
            warnings=[],
        )

        score = ScoreResult(
            score=math.nan,
            category="STRONG_BULLISH",
            factors=[],
            warnings=[],
        )

        with self.assertRaises(InvalidScoreData):
            self.engine.decide(analysis, score)

    def test_score_positive_infinity_is_rejected(self) -> None:
        analysis = AnalysisResult(
            market_state="BULLISH",
            strength=80.0,
            signals=[],
            warnings=[],
        )

        score = ScoreResult(
            score=math.inf,
            category="STRONG_BULLISH",
            factors=[],
            warnings=[],
        )

        with self.assertRaises(InvalidScoreData):
            self.engine.decide(analysis, score)

    def test_score_negative_infinity_is_rejected(self) -> None:
        analysis = AnalysisResult(
            market_state="BEARISH",
            strength=80.0,
            signals=[],
            warnings=[],
        )

        score = ScoreResult(
            score=-math.inf,
            category="STRONG_BEARISH",
            factors=[],
            warnings=[],
        )

        with self.assertRaises(InvalidScoreData):
            self.engine.decide(analysis, score)

    def test_invalid_market_state_is_rejected(self) -> None:
        analysis = AnalysisResult(
            market_state="INVALID",
            strength=50.0,
            signals=[],
            warnings=[],
        )

        score = ScoreResult(
            score=0.0,
            category="NEUTRAL",
            factors=[],
            warnings=[],
        )

        with self.assertRaises(
            InvalidDecisionData,
        ):
            self.engine.decide(
                analysis,
                score,
            )

    def test_none_analysis_is_rejected(self) -> None:
        score = ScoreResult(
            score=0.0,
            category="NEUTRAL",
            factors=[],
            warnings=[],
        )

        with self.assertRaises(
            InvalidDecisionData,
        ):
            self.engine.decide(
                None,
                score,
            )

    def test_none_score_is_rejected(self) -> None:
        analysis = AnalysisResult(
            market_state="NEUTRAL",
            strength=50.0,
            signals=[],
            warnings=[],
        )

        with self.assertRaises(
            InvalidDecisionData,
        ):
            self.engine.decide(
                analysis,
                None,
            )

    def test_decision_confidence_is_bounded(self) -> None:
        analysis = AnalysisResult(
            market_state="BULLISH",
            strength=80.0,
            signals=[],
            warnings=[],
        )

        score = ScoreResult(
            score=75.0,
            category="STRONG_BULLISH",
            factors=[],
            warnings=[],
        )

        result = self.engine.decide(
            analysis,
            score,
        )

        self.assertGreaterEqual(
            result.confidence,
            0.0,
        )

        self.assertLessEqual(
            result.confidence,
            100.0,
        )
        self.assertTrue(math.isfinite(result.confidence))


if __name__ == "__main__":
    unittest.main()
