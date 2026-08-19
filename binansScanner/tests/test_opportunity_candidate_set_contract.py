import unittest
from dataclasses import FrozenInstanceError
from models.opportunity import Opportunity, OpportunityDirection, OpportunityRisk, RiskState
from models.opportunity_candidate_set import OpportunityCandidateSet
class TestOpportunityCandidateSetContract(unittest.TestCase):
    @staticmethod
    def _candidate(symbol, timeframe="5m", direction=OpportunityDirection.LONG):
        return Opportunity(symbol=symbol,timeframe=timeframe,direction=direction,confidence=80.0,setup_quality=75.0,risk=OpportunityRisk(state=RiskState.ACCEPTABLE,invalidation="setup invalidation"))
    def test_valid_candidates_are_preserved_in_order(self):
        a,b=self._candidate("BTCUSDT"),self._candidate("ETHUSDT"); result=OpportunityCandidateSet((a,b)); self.assertEqual(result.opportunities,(a,b)); self.assertEqual(len(result),2); self.assertEqual(tuple(result),(a,b))
    def test_empty_candidate_set_is_rejected(self):
        with self.assertRaises(ValueError): OpportunityCandidateSet(())
    def test_non_opportunity_member_is_rejected(self):
        with self.assertRaises(ValueError): OpportunityCandidateSet((self._candidate("BTCUSDT"),"invalid"))
    def test_duplicate_identity_is_rejected(self):
        a=self._candidate("BTCUSDT");
        with self.assertRaises(ValueError): OpportunityCandidateSet((a,self._candidate("BTCUSDT")))
    def test_same_symbol_with_different_timeframe_is_allowed(self): self.assertEqual(len(OpportunityCandidateSet((self._candidate("BTCUSDT","5m"),self._candidate("BTCUSDT","15m")))),2)
    def test_same_symbol_and_timeframe_with_opposite_direction_is_allowed(self):
        a=self._candidate("BTCUSDT",direction=OpportunityDirection.LONG); b=self._candidate("BTCUSDT",direction=OpportunityDirection.SHORT); self.assertEqual(OpportunityCandidateSet((a,b)).opportunities,(a,b))
    def test_input_sequence_is_snapshotted_as_immutable_tuple(self):
        a,b=self._candidate("BTCUSDT"),self._candidate("ETHUSDT"); source=[a]; result=OpportunityCandidateSet(source); source.append(b); self.assertEqual(result.opportunities,(a,)); self.assertIsInstance(result.opportunities,tuple)
    def test_candidate_set_is_immutable(self):
        result=OpportunityCandidateSet((self._candidate("BTCUSDT"),));
        with self.assertRaises(FrozenInstanceError): result.opportunities=()
if __name__ == "__main__": unittest.main()
