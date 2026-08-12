import unittest

from models.opportunity import (
    Opportunity,
    OpportunityDirection,
    OpportunityRisk,
)
from models.opportunity_candidate_set import OpportunityCandidateSet


class TestOpportunityCandidateSetContract(unittest.TestCase):
    @staticmethod
    def _candidate(symbol: str, timeframe: str = "5m") -> Opportunity:
        return Opportunity(
            symbol=symbol,
            timeframe=timeframe,
            direction=OpportunityDirection.LONG,
            confidence=80.0,
            setup_quality=75.0,
            risk=OpportunityRisk(state="ACCEPTABLE", invalidation="setup invalidation"),
        )

    def test_valid_candidates_are_preserved_in_order(self) -> None:
        first = self._candidate("BTCUSDT")
        second = self._candidate("ETHUSDT")

        result = OpportunityCandidateSet((first, second))

        self.assertEqual(result.opportunities, (first, second))
        self.assertEqual(len(result), 2)
        self.assertEqual(tuple(result), (first, second))

    def test_empty_candidate_set_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OpportunityCandidateSet(())

    def test_non_opportunity_member_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OpportunityCandidateSet((self._candidate("BTCUSDT"), "invalid"))

    def test_duplicate_identity_is_rejected(self) -> None:
        first = self._candidate("BTCUSDT")
        duplicate = self._candidate("BTCUSDT")

        with self.assertRaises(ValueError):
            OpportunityCandidateSet((first, duplicate))

    def test_same_symbol_with_different_timeframe_is_allowed(self) -> None:
        five_minute = self._candidate("BTCUSDT", "5m")
        fifteen_minute = self._candidate("BTCUSDT", "15m")

        result = OpportunityCandidateSet((five_minute, fifteen_minute))

        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
