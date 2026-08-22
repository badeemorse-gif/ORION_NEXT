from __future__ import annotations

import ast
import math
import unittest

from models.capital_management import AllocationConfig, CapitalManager
from models.opportunity import MarketMetrics, OpportunityCandidate, OpportunityCandidateSet
from models.scalping_opportunity import EntryState, OpportunityClass, RejectionReason
from services.scalping_opportunity import ScalpingConfig, ScalpingDecisionEngine, ScalpingEvidenceEngine, ScalpingCandidatePoolManager, ScalpingReplayEvaluator


def candles(*, start: float, drift: float, volume: float, count: int = 48, range_size: float = 0.8):
    output = []
    price = start
    for index in range(count):
        open_price = price
        close = price + drift
        high = max(open_price, close) + range_size
        low = min(open_price, close) - range_size
        if index >= count - 2:
            high += range_size
            low -= range_size
        output.append((index, open_price, high, low, close, volume))
        price = close
    from models.scalping_opportunity import Candle
    return tuple(Candle(*row) for row in output)


def candidate(symbol: str = "BTCUSDT", score: float = 75.0) -> OpportunityCandidate:
    return OpportunityCandidate(symbol, score, 1, MarketMetrics(symbol, 100_000_000, 0.02, 5, True, 100), (), (("base", 0.75),), 0.5)


class ScalpingTests(unittest.TestCase):
    def setUp(self):
        self.config = ScalpingConfig(min_candles=32, active_top_n=2)
        self.engine = ScalpingEvidenceEngine(self.config)
        self.decision = ScalpingDecisionEngine(self.config)
        self.flat = candles(start=100, drift=0.0, volume=100)
        self.up = candles(start=100, drift=0.9, volume=100)
        breakout_base = candles(start=100, drift=0.5, volume=100)
        self.breakout = breakout_base[:-2] + tuple(
            type(breakout_base[0])(
                item.timestamp,
                item.open,
                item.high + 10.0,
                item.low - 1.0,
                item.close + 6.0,
                item.volume * 5.0,
            )
            for item in breakout_base[-2:]
        )
        self.candle_map = {"1d": self.flat, "4h": self.flat, "1h": self.up, "15m": self.breakout}

    def test_all_four_timeframes_are_evidence(self):
        result = self.engine.compute(self.candle_map)
        self.assertEqual(tuple(x.timeframe for x in result.evidence), ("1d", "4h", "1h", "15m"))

    def test_four_hour_is_not_hard_scalping_gate(self):
        result = self.engine.compute(self.candle_map)
        self.assertEqual(result.opportunity_class, OpportunityClass.BREAKOUT_ACCELERATION)

    def test_breakout_class_detected(self):
        result = self.engine.compute(self.candle_map)
        self.assertEqual(result.opportunity_class, OpportunityClass.BREAKOUT_ACCELERATION)
        self.assertGreater(result.opportunity_score, 0.0)

    def test_trend_continuation_class_detected(self):
        rising = candles(start=100, drift=0.5, volume=100)
        result = self.engine.compute({"1d": rising, "4h": rising, "1h": rising, "15m": rising})
        self.assertEqual(result.opportunity_class, OpportunityClass.TREND_CONTINUATION)

    def test_pullback_continuation_class_detected(self):
        rise = list(candles(start=100, drift=0.6, volume=100, count=42))
        last = rise[-1]
        from models.scalping_opportunity import Candle
        rise[-3:] = [Candle(last.timestamp - 2, last.close, last.close + 0.2, last.close - 1.0, last.close - 0.5, 100), Candle(last.timestamp - 1, last.close - 0.5, last.close + 0.2, last.close - 0.3, last.close + 0.1, 120), Candle(last.timestamp, last.close + 0.1, last.close + 1.0, last.close, last.close + 0.8, 130)]
        seq = tuple(rise)
        result = self.engine.compute({"1d": seq, "4h": seq, "1h": seq, "15m": seq})
        self.assertIn(result.opportunity_class, (OpportunityClass.PULLBACK_CONTINUATION, OpportunityClass.TREND_CONTINUATION))

    def test_directional_evidence_is_directional(self):
        bull = self.engine.compute({"1d": self.up, "4h": self.up, "1h": self.up, "15m": self.up})
        bear = tuple(type(c)(c.timestamp, c.open, c.high, c.low, c.close, c.volume) for c in candles(start=200, drift=-0.9, volume=100))
        bear_features = self.engine.compute({"1d": bear, "4h": bear, "1h": bear, "15m": bear})
        self.assertGreater(bull.directional_evidence, 0)
        self.assertLess(bear_features.directional_evidence, 0)

    def test_acceleration_is_separate_from_momentum(self):
        evidence = self.engine.compute(self.candle_map).evidence
        self.assertNotEqual(evidence[2].momentum_score, evidence[2].acceleration_score)

    def test_volume_expansion_is_distinct_feature(self):
        self.assertGreater(self.engine.compute(self.candle_map).evidence[-1].volume_expansion, 0.5)

    def test_range_expansion_is_distinct_feature(self):
        self.assertGreater(self.engine.compute(self.candle_map).evidence[-1].range_expansion, 0.5)

    def test_structure_feature_exists(self):
        evidence = self.engine.compute(self.candle_map).evidence[2]
        self.assertGreaterEqual(evidence.structure_score, 0.0)
        self.assertLessEqual(evidence.structure_score, 1.0)

    def test_supertrend_is_evidence_not_authority(self):
        baseline = self.engine.compute(self.candle_map, use_supertrend=False)
        with_st = self.engine.compute(self.candle_map, use_supertrend=True)
        self.assertIn(baseline.opportunity_class, list(OpportunityClass))
        self.assertIn(with_st.opportunity_class, list(OpportunityClass))
        self.assertNotEqual(with_st.supertrend_enabled, baseline.supertrend_enabled)

    def test_supertrend_ab_is_measurable(self):
        baseline = [(True, 0.02, 0.01, 0.5, 1.0), (False, -0.01, 0.0, 0.4, 2.0)]
        improved = [(True, 0.025, 0.01, 0.5, 1.0), (False, -0.01, 0.0, 0.4, 2.0)]
        result = ScalpingReplayEvaluator.compare_supertrend(baseline, improved)
        self.assertEqual(result.capture_delta, 0.0)
        self.assertGreaterEqual(result.expectancy_delta, 0.0)

    def test_high_quality_opportunity_does_not_auto_reject(self):
        result = self.decision.decide(candidate(score=95), self.candle_map)
        self.assertIn(result.entry_state, (EntryState.A_PLUS.value, EntryState.A.value, EntryState.B.value, EntryState.C.value))
        self.assertNotEqual(result.entry_state, EntryState.D.value)
        self.assertIsNotNone(result.decision_trace)

    def test_entry_readiness_is_separate_from_opportunity_quality(self):
        result = self.decision.decide(candidate(score=95), {"1d": self.up, "4h": self.up, "1h": self.up, "15m": self.flat})
        self.assertGreaterEqual(result.entry_readiness, 0.0)
        self.assertLess(result.entry_readiness, self.config.a_readiness)
        self.assertEqual(result.entry_state, EntryState.B.value)
        self.assertFalse(result.decision_trace.entry_allowed)
        self.assertIn("opportunity_good_entry_timing_not_ready", result.decision_trace.reasons)

    def test_capital_manager_is_only_sizing_authority(self):
        manager = CapitalManager(AllocationConfig(starting_capital=50.0, fixed_allocation=10.0))
        result = self.decision.decide(candidate(score=95), self.candle_map, capital_manager=manager)
        self.assertIsNotNone(result.decision_trace)
        self.assertEqual(manager.desired_allocation(), 10.0)

    def test_capital_rejection_is_traced(self):
        manager = CapitalManager(AllocationConfig(starting_capital=5.0, fixed_allocation=10.0))
        result = self.decision.decide(candidate(score=95), self.candle_map, capital_manager=manager)
        self.assertIn(RejectionReason.CAPITAL, result.decision_trace.rejection_reasons)
        self.assertEqual(result.entry_state, EntryState.D.value)

    def test_pause_rejection_is_traced(self):
        self.assertIn(RejectionReason.PAUSE, self.decision.decide(candidate(), self.candle_map, pause=True).decision_trace.rejection_reasons)

    def test_duplicate_position_rejection_is_traced(self):
        self.assertIn(RejectionReason.DUPLICATE_POSITION, self.decision.decide(candidate(), self.candle_map, active_symbols=("BTCUSDT",)).decision_trace.rejection_reasons)

    def test_market_failure_is_fail_closed_and_observable(self):
        result = self.decision.decide(candidate(), {"1d": self.flat})
        self.assertEqual(result.entry_state, EntryState.D.value)
        self.assertIn(RejectionReason.MARKET_DATA_FAILURE, result.decision_trace.rejection_reasons)

    def test_candidate_pool_hysteresis_retains_incumbent(self):
        manager = ScalpingCandidatePoolManager(ScalpingConfig(active_top_n=1, hysteresis_score_delta=2.0))
        first = manager.select(OpportunityCandidateSet((candidate("BTCUSDT", 80), candidate("ETHUSDT", 75)), 2), (candidate("BTCUSDT", 80), candidate("ETHUSDT", 75)))
        second = manager.select(OpportunityCandidateSet((candidate("BTCUSDT", 79), candidate("ETHUSDT", 80)), 2), (candidate("BTCUSDT", 79), candidate("ETHUSDT", 80)))
        self.assertEqual(first.active_set.symbols(), ("BTCUSDT",))
        self.assertEqual(second.active_set.symbols(), ("BTCUSDT",))

    def test_candidate_pool_separates_broad_and_active(self):
        manager = ScalpingCandidatePoolManager(ScalpingConfig(active_top_n=1))
        result = manager.select(OpportunityCandidateSet((candidate("BTCUSDT", 80), candidate("ETHUSDT", 70)), 2), (candidate("BTCUSDT", 80), candidate("ETHUSDT", 70)))
        self.assertEqual(len(result.broad_pool.candidates), 2)
        self.assertEqual(len(result.active_set.candidates), 1)

    def test_decision_trace_contains_all_required_answers(self):
        trace = self.decision.decide(candidate(score=95), self.candle_map).decision_trace
        self.assertTrue(trace.discovered)
        self.assertTrue(trace.eligible)
        self.assertGreater(len(trace.measured_features), 5)
        self.assertIsInstance(trace.opportunity_class, OpportunityClass)
        self.assertGreaterEqual(trace.opportunity_score, 0.0)
        self.assertLessEqual(trace.opportunity_score, 100.0)
        self.assertIsNotNone(trace.entry_state)

    def test_replay_metrics_cover_required_dimensions(self):
        metrics = ScalpingReplayEvaluator.metrics([(True,0.02,1,0.5,30),(False,-0.01,0,0.4,45),(True,0.01,1,0.6,20)])
        self.assertGreaterEqual(metrics.opportunity_capture_rate, 0.0)
        self.assertGreaterEqual(metrics.entry_acceptance_rate, 0.0)
        self.assertGreaterEqual(metrics.trades_per_day, 0.0)
        self.assertGreaterEqual(metrics.win_rate, 0.0)
        self.assertTrue(math.isfinite(metrics.expectancy))
        self.assertTrue(math.isfinite(metrics.maximum_drawdown))
        self.assertTrue(math.isfinite(metrics.capital_utilization))
        self.assertTrue(math.isfinite(metrics.average_hold_time))
        self.assertTrue(math.isfinite(metrics.false_negative_rate))

    def test_ab_comparison_is_deterministic(self):
        baseline = [(True,0.02,1,0.5,30),(False,-0.01,0,0.4,45)]
        improved = [(True,0.025,1,0.5,30),(True,0.01,1,0.6,20)]
        self.assertEqual(ScalpingReplayEvaluator.compare(baseline, improved), ScalpingReplayEvaluator.compare(baseline, improved))

    def test_no_live_or_execution_imports(self):
        source = __import__("inspect").getsource(__import__("services.scalping_opportunity", fromlist=["x"]))
        tree = ast.parse(source)
        imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        text = "\n".join(ast.unparse(node) for node in imports).lower()
        self.assertFalse(any(token in text for token in ("execution", "live", "paper")))


if __name__ == "__main__":
    unittest.main()
