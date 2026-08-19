import math
import unittest
from core.intelligence_contract import IntelligenceContractError, validate_analysis, validate_decision, validate_score
from models.analysis import AnalysisResult
from models.decision import DecisionResult
from models.score import ScoreResult

class TestCoreIntelligenceCompletionContract(unittest.TestCase):
    def test_directional_analysis_with_fail_closed_warning_is_rejected(self):
        with self.assertRaises(IntelligenceContractError): validate_analysis(AnalysisResult(market_state="BULLISH", strength=100.0, warnings=["INVALID_REQUIRED_INDICATORS"]))
    def test_score_category_must_match_numeric_score(self):
        with self.assertRaises(IntelligenceContractError): validate_score(ScoreResult(score=-80.0, category="STRONG_BULLISH"))
    def test_wait_must_have_zero_actionable_confidence(self):
        with self.assertRaises(IntelligenceContractError): validate_decision(AnalysisResult(market_state="NEUTRAL", strength=100.0), ScoreResult(score=0.0, category="NEUTRAL"), DecisionResult(decision="WAIT", confidence=85.0))
    def test_favorable_requires_bullish_strong_score(self):
        with self.assertRaises(IntelligenceContractError): validate_decision(AnalysisResult(market_state="BULLISH", strength=100.0), ScoreResult(score=45.0, category="BULLISH"), DecisionResult(decision="FAVORABLE", confidence=45.0))
    def test_unfavorable_requires_bearish_strong_score(self):
        with self.assertRaises(IntelligenceContractError): validate_decision(AnalysisResult(market_state="BEARISH", strength=100.0), ScoreResult(score=-45.0, category="BEARISH"), DecisionResult(decision="UNFAVORABLE", confidence=45.0))
    def test_non_finite_score_is_rejected(self):
        with self.assertRaises(IntelligenceContractError): validate_score(ScoreResult(score=math.nan, category="NEUTRAL"))
if __name__ == "__main__": unittest.main()
