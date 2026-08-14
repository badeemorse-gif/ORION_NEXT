import unittest
from dataclasses import FrozenInstanceError

from models.opportunity import (
    Opportunity,
    OpportunityDirection,
    OpportunityRisk,
    RiskState,
)
from models.opportunity_candidate_set import OpportunityCandidateSet


class TestOpportunityCandidateSetContract(unittest.TestCase):
    @staticmethod
    def _candidate(
        symbol: str,
        timeframe: str = "5m",
        direction: OpportunityDirection = OpportunityDirection.LONG,
    ) -> Opportunity:
        return Opportunity(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            confidence=80.0,
            setup_quality=75.0,
            risk=OpportunityRisk(
                state=RiskState.ACCEPTABLE,
                invalidation="setup invalidation",
            ),
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

    def test_same_symbol_and_timeframe_with_opposite_direction_is_allowed(self) -> None:
        long_candidate = self._candidate(
            "BTCUSDT", direction=OpportunityDirection.LONG
        )
        short_candidate = self._candidate(
            "BTCUSDT", direction=OpportunityDirection.SHORT
        )

        result = OpportunityCandidateSet((long_candidate, short_candidate))

        self.assertEqual(result.opportunities, (long_candidate, short_candidate))

    def test_input_sequence_is_snapshotted_as_immutable_tuple(self) -> None:
        first = self._candidate("BTCUSDT")
        second = self._candidate("ETHUSDT")
        source = [first]

        result = OpportunityCandidateSet(source)
        source.append(second)

        self.assertIsInstance(result.opportunities, tuple)
        self.assertEqual(result.opportunities, (first,))

    def test_candidate_set_is_immutable(self) -> None:
        result = OpportunityCandidateSet((self._candidate("BTCUSDT"),))

        with self.assertRaises(FrozenInstanceError):
            result.opportunities = ()


if __name__ == "__main__":
    unittest.main()
