from __future__ import annotations

import unittest

from models.opportunity import MarketMetrics, OpportunityCandidate
from models.scalping_opportunity import DecisionTrace, EntryState, OpportunityClass, RejectionReason
from services.scalping_opportunity import ScalpingConfig
from services.scalping_pipeline import FastRecall, ScalpingOpportunityPipeline


class FastRecallTests(unittest.TestCase):
    def _candidate(self, symbol: str, score: float, **kwargs) -> OpportunityCandidate:
        return OpportunityCandidate(
            symbol,
            score,
            0,
            MarketMetrics(symbol, 100_000_000.0, 0.02, 5.0, True, 100.0, **kwargs),
            (),
        )

    def test_strong_mover_is_recalled_below_composite_cutoff(self):
        candidates = [self._candidate("LEADER", 95.0), self._candidate("HOT", 10.0, price_change_pct_24h=42.0)]
        result = FastRecall(lane_top_n=1, composite_top_n=1).recall(candidates, broad_limit=2)
        self.assertIn("HOT", tuple(item.symbol for item in result.candidates))
        self.assertIn("high_mover", dict(result.provenance)["HOT"])

    def test_short_term_acceleration_lane(self):
        candidates = [self._candidate("QUIET", 95.0), self._candidate("ACCEL", 5.0, short_term_acceleration=9.0)]
        result = FastRecall(lane_top_n=1, composite_top_n=1).recall(candidates, broad_limit=2)
        self.assertIn("ACCEL", tuple(item.symbol for item in result.candidates))
        self.assertIn("short_term_acceleration", dict(result.provenance)["ACCEL"])

    def test_volume_expansion_lane(self):
        candidates = [self._candidate("QUIET", 95.0), self._candidate("VOLUME", 5.0, volume_expansion=8.0)]
        result = FastRecall(lane_top_n=1, composite_top_n=1).recall(candidates, broad_limit=2)
        self.assertIn("VOLUME", tuple(item.symbol for item in result.candidates))
        self.assertIn("volume_expansion", dict(result.provenance)["VOLUME"])

    def test_breakout_range_expansion_lane(self):
        candidates = [self._candidate("QUIET", 95.0), self._candidate("BREAK", 5.0, range_expansion=7.0)]
        result = FastRecall(lane_top_n=1, composite_top_n=1).recall(candidates, broad_limit=2)
        self.assertIn("BREAK", tuple(item.symbol for item in result.candidates))
        self.assertIn("breakout_range_expansion", dict(result.provenance)["BREAK"])

    def test_duplicate_symbol_is_recalled_once_with_multiple_lanes(self):
        candidate = self._candidate(
            "HOT",
            5.0,
            price_change_pct_24h=50.0,
            short_term_acceleration=10.0,
            volume_expansion=10.0,
            range_expansion=10.0,
        )
        result = FastRecall(lane_top_n=1, composite_top_n=1).recall([candidate], broad_limit=10)
        self.assertEqual(tuple(item.symbol for item in result.candidates), ("HOT",))
        self.assertEqual(
            dict(result.provenance)["HOT"],
            ("composite_opportunity", "high_mover", "short_term_acceleration", "volume_expansion", "breakout_range_expansion"),
        )

    def test_quiet_market_hot_symbols_survive_recall(self):
        candidates = [self._candidate(f"FLAT{i}", 90.0 - i) for i in range(8)]
        candidates.extend([
            self._candidate("HOT1", 20.0, price_change_pct_24h=30.0),
            self._candidate("HOT2", 19.0, short_term_acceleration=11.0),
        ])
        result = FastRecall(lane_top_n=1, composite_top_n=3).recall(candidates, broad_limit=5)
        symbols = tuple(item.symbol for item in result.candidates)
        self.assertIn("HOT1", symbols)
        self.assertIn("HOT2", symbols)

    def test_downstream_ordering_remains_composite_order(self):
        candidates = [
            self._candidate("HIGH", 100.0),
            self._candidate("MID", 50.0, price_change_pct_24h=30.0),
            self._candidate("LOW", 10.0, short_term_acceleration=20.0),
        ]
        result = FastRecall(lane_top_n=1, composite_top_n=1).recall(candidates, broad_limit=3)
        self.assertEqual(tuple(item.symbol for item in result.candidates), ("HIGH", "MID", "LOW"))

    def test_recall_provenance_is_deterministic_and_counts_are_observable(self):
        candidates = [self._candidate("A", 80.0, price_change_pct_24h=20.0), self._candidate("B", 60.0)]
        recall = FastRecall(lane_top_n=1, composite_top_n=1)
        first = recall.recall(candidates, broad_limit=2)
        second = recall.recall(candidates, broad_limit=2)
        self.assertEqual(first.provenance, second.provenance)
        self.assertEqual(first.counts, second.counts)
        self.assertTrue(all(count >= 0 for _, count in first.counts))

    def test_31_day_context_is_not_required_for_recall(self):
        candidate = self._candidate("HOT", 1.0, price_change_pct_24h=44.0)
        result = FastRecall(lane_top_n=1, composite_top_n=1).recall([candidate], broad_limit=10)
        self.assertEqual(result.candidates[0].symbol, "HOT")


class ClassificationIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pipeline = ScalpingOpportunityPipeline.__new__(ScalpingOpportunityPipeline)
        self.pipeline.decision_engine = type("Engine", (), {"config": ScalpingConfig()})()

    @staticmethod
    def _candidate(
        state: EntryState,
        allowed: bool,
        *,
        score: float = 75.0,
        readiness: float = 0.70,
        directional: float = 0.30,
        evidence_count: int = 4,
    ) -> OpportunityCandidate:
        evidence = tuple(object() for _ in range(evidence_count))
        trace = DecisionTrace(
            True,
            True,
            ("trend", "momentum"),
            OpportunityClass.UNCLASSIFIED,
            score,
            directional,
            state,
            allowed,
            (),
            ("unclassified",),
        )
        return OpportunityCandidate(
            "TESTUSDT",
            score,
            1,
            MarketMetrics("TESTUSDT", 100_000_000.0, 0.02),
            (),
            (),
            directional,
            OpportunityClass.UNCLASSIFIED.value,
            state.value,
            readiness,
            None,
            evidence,
            trace,
        )

    def test_c_never_produces_entry_allowed_true(self):
        result = self.pipeline._classification_integrity(self._candidate(EntryState.C, True))
        self.assertFalse(result.decision_trace.entry_allowed)
        self.assertIn(RejectionReason.ENTRY_STATE_CONFLICT, result.decision_trace.rejection_reasons)

    def test_d_never_produces_entry_allowed_true(self):
        result = self.pipeline._classification_integrity(self._candidate(EntryState.D, True))
        self.assertFalse(result.decision_trace.entry_allowed)
        self.assertIn(RejectionReason.ENTRY_STATE_CONFLICT, result.decision_trace.rejection_reasons)

    def test_high_quality_opportunity_is_not_silently_left_unclassified(self):
        result = self.pipeline._classification_integrity(self._candidate(EntryState.A, False))
        self.assertNotEqual(result.opportunity_class, OpportunityClass.UNCLASSIFIED.value)
        self.assertIn("classification_fallback_trend_continuation", result.decision_trace.reasons)

    def test_insufficient_classification_is_explicit_and_deterministic(self):
        candidate = self._candidate(EntryState.C, False, score=20.0, readiness=0.10, evidence_count=0, directional=0.0)
        first = self.pipeline._classification_integrity(candidate)
        second = self.pipeline._classification_integrity(candidate)
        self.assertEqual(first.opportunity_class, OpportunityClass.UNCLASSIFIED.value)
        self.assertEqual(first.entry_state, EntryState.C.value)
        self.assertFalse(first.decision_trace.entry_allowed)
        self.assertIn(RejectionReason.CLASSIFICATION_INSUFFICIENT, first.decision_trace.rejection_reasons)
        self.assertEqual(first.decision_trace.reasons, second.decision_trace.reasons)


if __name__ == "__main__":
    unittest.main()
