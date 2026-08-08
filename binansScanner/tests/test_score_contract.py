"""
ORION — Score Contract Tests

Purpose:
    Lock the canonical ScoreResult / ScoreEngine contract before
    proceeding to Decision.

This test must remain independent from:
    - Binance
    - MarketDataset
    - DataFrame access
    - Execution
    - Reporting
"""

from __future__ import annotations

import unittest

from engines.score_engine import InvalidScoreData, ScoreEngine
from models.analysis import AnalysisResult
from models.score import ScoreResult


class TestScoreContract(unittest.TestCase):

    def _bullish_analysis(self) -> AnalysisResult:
        return AnalysisResult(
            market_state="BULLISH",
            strength=80.0,
            signals=[
                "EMA_ALIGNMENT_BULLISH",
                "MOMENTUM_POSITIVE",
                "STRONG_TREND",
            ],
            warnings=[],
        )

    def _bearish_analysis(self) -> AnalysisResult:
        return AnalysisResult(
            market_state="BEARISH",
            strength=20.0,
            signals=[
                "EMA_ALIGNMENT_BEARISH",
                "MOMENTUM_NEGATIVE",
                "WEAK_TREND",
            ],
            warnings=[],
        )

    def test_score_engine_returns_canonical_result(self) -> None:
        engine = ScoreEngine()

        result = engine.calculate(self._bullish_analysis())

        self.assertIsInstance(result, ScoreResult)
        self.assertIsInstance(result.score, float)
        self.assertIsInstance(result.category, str)
        self.assertIsInstance(result.factors, list)
        self.assertIsInstance(result.warnings, list)

    def test_score_is_bounded(self) -> None:
        engine = ScoreEngine()

        bullish = engine.calculate(self._bullish_analysis())
        bearish = engine.calculate(self._bearish_analysis())

        self.assertGreaterEqual(bullish.score, -100.0)
        self.assertLessEqual(bullish.score, 100.0)

        self.assertGreaterEqual(bearish.score, -100.0)
        self.assertLessEqual(bearish.score, 100.0)

    def test_bullish_analysis_produces_bullish_direction(self) -> None:
        engine = ScoreEngine()

        result = engine.calculate(self._bullish_analysis())

        self.assertIn(
            result.category,
            {
                "BULLISH",
                "STRONG_BULLISH",
            },
        )

    def test_bearish_analysis_produces_bearish_direction(self) -> None:
        engine = ScoreEngine()

        result = engine.calculate(self._bearish_analysis())

        self.assertIn(
            result.category,
            {
                "BEARISH",
                "STRONG_BEARISH",
            },
        )

    def test_score_preserves_analysis_factors(self) -> None:
        analysis = self._bullish_analysis()
        result = ScoreEngine().calculate(analysis)

        self.assertEqual(result.factors, analysis.signals)

    def test_score_preserves_analysis_warnings(self) -> None:
        analysis = self._bullish_analysis()
        analysis.warnings.append("TEST_WARNING")

        result = ScoreEngine().calculate(analysis)

        self.assertEqual(result.warnings, analysis.warnings)

    def test_score_rejects_none_analysis(self) -> None:
        with self.assertRaises(InvalidScoreData):
            ScoreEngine().calculate(None)

    def test_score_rejects_invalid_market_state(self) -> None:
        analysis = self._bullish_analysis()
        analysis.market_state = "INVALID"

        with self.assertRaises(InvalidScoreData):
            ScoreEngine().calculate(analysis)

    def test_score_rejects_strength_below_zero(self) -> None:
        analysis = self._bullish_analysis()
        analysis.strength = -1.0

        with self.assertRaises(InvalidScoreData):
            ScoreEngine().calculate(analysis)

    def test_score_rejects_strength_above_hundred(self) -> None:
        analysis = self._bullish_analysis()
        analysis.strength = 101.0

        with self.assertRaises(InvalidScoreData):
            ScoreEngine().calculate(analysis)

    def test_score_engine_does_not_require_market_dataset(self) -> None:
        """
        Architectural boundary:
        Score must consume AnalysisResult, not MarketDataset.
        """
        engine = ScoreEngine()
        result = engine.calculate(self._bullish_analysis())

        self.assertIsInstance(result, ScoreResult)


if __name__ == "__main__":
    unittest.main()