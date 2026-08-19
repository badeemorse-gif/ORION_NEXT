from datetime import datetime
import unittest

from models.opportunity_evaluation import OpportunityEvaluation, OpportunityEvaluationStatus
from models.opportunity import FreshnessStatus, Opportunity, OpportunityDirection, OpportunityRisk, OpportunityStatus, RiskState


class TestOpportunityEvaluationContract(unittest.TestCase):
    def _eligible(self) -> Opportunity:
        return Opportunity(symbol="BTCUSDT", timeframe="5m", direction=OpportunityDirection.LONG, entry_candidate=100.0, confidence=82.0, setup_quality=78.0, risk=OpportunityRisk(state=RiskState.ACCEPTABLE, invalidation="setup invalidation"), expected_move=1.5, supporting_evidence=("trend alignment",), market_context=("liquid",), freshness=FreshnessStatus.FRESH, status=OpportunityStatus.ACTIVE)

    def test_eligible_opportunity_can_be_accepted(self) -> None:
        evaluation = OpportunityEvaluation(opportunity=self._eligible(), status=OpportunityEvaluationStatus.ACCEPTED)
        self.assertTrue(evaluation.accepted)
        self.assertEqual(evaluation.reasons, ())

    def test_ineligible_opportunity_cannot_be_accepted(self) -> None:
        opportunity = Opportunity(symbol="BTCUSDT", timeframe="5m", direction=OpportunityDirection.LONG, freshness=FreshnessStatus.FRESH, status=OpportunityStatus.ACTIVE)
        with self.assertRaises(ValueError):
            OpportunityEvaluation(opportunity=opportunity, status=OpportunityEvaluationStatus.ACCEPTED)

    def test_rejected_evaluation_requires_reason(self) -> None:
        with self.assertRaises(ValueError):
            OpportunityEvaluation(opportunity=self._eligible(), status=OpportunityEvaluationStatus.REJECTED)

    def test_rejected_evaluation_preserves_reason(self) -> None:
        evaluation = OpportunityEvaluation(opportunity=self._eligible(), status=OpportunityEvaluationStatus.REJECTED, reasons=("candidate excluded by future ranking policy",))
        self.assertFalse(evaluation.accepted)
        self.assertEqual(evaluation.reasons, ("candidate excluded by future ranking policy",))

    def test_naive_evaluation_timestamp_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OpportunityEvaluation(opportunity=self._eligible(), status=OpportunityEvaluationStatus.ACCEPTED, evaluated_at=datetime(2026, 8, 11, 12, 0))


if __name__ == "__main__":
    unittest.main()
