from __future__ import annotations

import ast
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.orchestrator import OrchestratorResult, PipelineError, PipelineStage, PipelineStatistics  # noqa: E402
from enums import DataHealth, Timeframe  # noqa: E402
from models.analysis import AnalysisResult  # noqa: E402
from models.decision import DecisionResult  # noqa: E402
from models.market import MarketDataset, MarketMetadata, TimeframeData  # noqa: E402
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics, TimeframeProfile  # noqa: E402
from models.score import ScoreResult  # noqa: E402
from models.signal_journal import SignalJournal, SignalJournalEntry  # noqa: E402
from tools.orion_phase_a_runtime_observer import (  # noqa: E402
    REQUIRED_SYMBOLS,
    REQUIRED_TIMEFRAMES,
    UNAVAILABLE_AT_BOUNDARY,
    PhaseARuntimeObserver,
    create_runtime_config,
    extract_observation,
    extract_wait_observation,
)


class TestPhaseARuntimeObserver(unittest.TestCase):
    @staticmethod
    def _result(symbol="BTCUSDT", decision="FAVORABLE", score=31.5):
        import pandas as pd

        now = datetime(2026, 8, 17, 20, 0, tzinfo=timezone.utc)
        dataset = MarketDataset(MarketMetadata(symbol, "BINANCE", "BINANCE_API", "1.0.0", now, now))
        frame = pd.DataFrame(
            {
                "open": [100.0, 101.0, 102.0],
                "high": [101.0, 102.0, 103.0],
                "low": [99.0, 100.0, 101.0],
                "close": [100.5, 101.5, 102.5],
                "volume": [100.0, 100.0, 150.0],
            },
            index=pd.date_range(now, periods=3, freq="h", tz="UTC"),
        )
        for timeframe in (Timeframe.H1, Timeframe.H4, Timeframe.D1):
            dataset.add_timeframe(TimeframeData(timeframe, frame, DataHealth.GOOD, 3, now, now))
        characteristics = MarketCharacteristics(
            trend="Bullish", trend_strength="Strong", momentum="Buy", volume_strength="Strong",
            volatility=0.02, volatility_level="Normal", liquidity=0.9, market_phase="Markup", confidence=80.0,
        )
        profile = ProfileResult(
            symbol,
            characteristics,
            ProfileStatistics(confidence_limit=80.0, completion_ratio=1.0, total_candles=9),
            tuple(TimeframeProfile(tf, characteristics, 3, now, now, DataHealth.GOOD) for tf in REQUIRED_TIMEFRAMES),
            is_tradeable=True,
            generated_at=now,
        )
        return OrchestratorResult(
            dataset=dataset,
            analysis=AnalysisResult("BULLISH", 20.0, ["TEST_SIGNAL"]),
            profile=profile,
            score=ScoreResult(score, "BULLISH", ["TEST_FACTOR"]),
            decision=DecisionResult(decision, abs(score) if decision != "WAIT" else 0.0, ["TEST_REASON"]),
            statistics=PipelineStatistics(finished_at=now, current_stage=PipelineStage.FINISHED, completed_stage_count=8, success=True),
        )

    def _config(self, runtime_commit="5db73bfb079655fd32e2127289f181938006a167"):
        return create_runtime_config(
            baseline_commit="c54dc67792776da905a3efb1f667c1869c15db3d",
            symbols=REQUIRED_SYMBOLS,
            timeframes=REQUIRED_TIMEFRAMES,
            configuration={"execution": {"paper": False, "live": False}},
            session_id="EXP-20260817T200000Z-abcdef123456",
            runtime_commit=runtime_commit,
        )

    def _stubbed_run(self, decision="WAIT", symbol_factory=None):
        class Stub:
            def __init__(self):
                self.result = None

            def run(self, symbol, timeframes):
                symbol_factory_value = symbol_factory(symbol) if symbol_factory else None
                self.result = TestPhaseARuntimeObserver._result(symbol=symbol, decision=decision)
                if symbol_factory_value is not None:
                    self.result = symbol_factory_value
                return self.result

            def last_result(self):
                return self.result

        observer = PhaseARuntimeObserver(self._config(), orchestrator_factory=Stub)
        return observer.run(REQUIRED_SYMBOLS, REQUIRED_TIMEFRAMES)

    def test_required_universe_and_binding(self):
        self.assertEqual(REQUIRED_SYMBOLS, ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"))
        self.assertEqual(REQUIRED_TIMEFRAMES, ("1h", "4h", "1d"))
        config = self._config("ce97cb6064dc0d0cfd02e15d4f30f1d80b824c2c")
        self.assertEqual(config.baseline_commit, "c54dc67792776da905a3efb1f667c1869c15db3d")
        self.assertEqual(len(config.configuration_fingerprint), 64)
        self.assertTrue(config.universe_identity.startswith("UNIV-"))

    def test_observation_preserves_orion_outputs(self):
        extraction = extract_observation(self._result(decision="FAVORABLE", score=31.5), "1h", timestamp=datetime(2026, 8, 17, 20, 0, tzinfo=timezone.utc))
        self.assertEqual(extraction.status, "OBSERVED")
        self.assertIsNotNone(extraction.observation)
        observation = extraction.observation
        assert observation is not None
        self.assertEqual(observation.raw_score, 31.5)
        self.assertEqual(observation.decision, "FAVORABLE")
        self.assertEqual(observation.market_regime, "Markup")
        self.assertEqual(observation.timeframe, "1h")
        self.assertIsNone(observation.directional_raw_strength)
        self.assertIsNone(observation.context_score)
        self.assertIsNone(observation.composite)
        self.assertIsNone(observation.relative_rank)
        self.assertIsNone(observation.relative_percentile)
        self.assertNotIn("outcome_1h", observation.__dataclass_fields__)

    def test_d6_journal_compatibility_and_no_outcome(self):
        observation = extract_observation(self._result(), "1h", timestamp=datetime(2026, 8, 17, 20, 0, tzinfo=timezone.utc)).observation
        assert observation is not None
        journal = SignalJournal().record(SignalJournalEntry(observation=observation))
        self.assertEqual(len(journal), 1)
        self.assertIsNone(journal.entries[0].outcome)

    def test_missing_boundary_is_not_guessed(self):
        result = self._result()
        result.profile.market.market_phase = ""
        extraction = extract_observation(result, "1h", timestamp=datetime(2026, 8, 17, 20, 0, tzinfo=timezone.utc))
        self.assertEqual(extraction.status, UNAVAILABLE_AT_BOUNDARY)
        self.assertIn("market_regime", extraction.unavailable_fields)
        self.assertIsNone(extraction.observation)

    def test_wait_extracts_one_signal_time_observation(self):
        extraction = extract_wait_observation(self._result(decision="WAIT"), "1h", timestamp=datetime(2026, 8, 17, 20, 0, tzinfo=timezone.utc))
        self.assertEqual(extraction.status, "OBSERVED")
        self.assertIsNotNone(extraction.observation)
        observation = extraction.observation
        assert observation is not None
        self.assertEqual(observation.timeframe, "1h")
        self.assertEqual(observation.decision, "WAIT")
        self.assertIsNone(observation.directional_raw_strength)
        self.assertIsNone(observation.context_score)
        self.assertIsNone(observation.composite)
        self.assertIsNone(observation.relative_rank)
        self.assertIsNone(observation.relative_percentile)

    def test_point_in_time_and_future_leakage(self):
        text = (ROOT / "tools" / "orion_phase_a_runtime_observer.py").read_text(encoding="utf-8")
        tree = ast.parse(text)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        self.assertNotIn("engines.execution_engine", imported)
        self.assertNotIn("models.execution", imported)
        for forbidden in ("Opportunity", "OpportunityRelativeRanker", "OpportunityRankingInput", "SignalOutcome", "forward_outcome_validation", "outcome_1h", "outcome_4h", "outcome_24h", "mfe", "mae"):
            self.assertNotIn(forbidden, text)

    def test_symbol_level_decision_creates_at_most_one_observation(self):
        class Stub:
            def __init__(self): self.result = None
            def run(self, symbol, timeframes): self.result = TestPhaseARuntimeObserver._result(symbol=symbol); return self.result
            def last_result(self): return self.result

        run = PhaseARuntimeObserver(self._config(), orchestrator_factory=Stub).run(REQUIRED_SYMBOLS, REQUIRED_TIMEFRAMES)
        observed = [x for x in run.records if x["status"] == "OBSERVED" and x["symbol"] == "BTCUSDT"]
        btc_entries = [entry for entry in run.journal.entries if entry.observation.symbol == "BTCUSDT"]
        self.assertEqual(len(observed), 1)
        self.assertEqual(len(btc_entries), 1)
        self.assertEqual(observed[0]["timeframe"], "1h")
        self.assertEqual(observed[0]["primary_timeframe"], "1h")

    def test_wait_creates_one_observation_and_no_4h_1d_duplicates(self):
        class Stub:
            def __init__(self): self.result = None
            def run(self, symbol, timeframes): self.result = TestPhaseARuntimeObserver._result(symbol=symbol, decision="WAIT"); return self.result
            def last_result(self): return self.result

        run = PhaseARuntimeObserver(self._config(), orchestrator_factory=Stub).run(REQUIRED_SYMBOLS, REQUIRED_TIMEFRAMES)
        btc_records = [record for record in run.records if record["symbol"] == "BTCUSDT"]
        btc_entries = [entry for entry in run.journal.entries if entry.observation.symbol == "BTCUSDT"]
        self.assertEqual(len([record for record in btc_records if record["status"] == "OBSERVED"]), 1)
        self.assertEqual(len(btc_entries), 1)
        self.assertEqual([entry.observation.timeframe for entry in btc_entries], ["1h"])
        self.assertNotIn("4h", [entry.observation.timeframe for entry in btc_entries])
        self.assertNotIn("1d", [entry.observation.timeframe for entry in btc_entries])

    def test_favorable_creates_one_observation_without_d3(self):
        class Stub:
            def __init__(self): self.result = None
            def run(self, symbol, timeframes): self.result = TestPhaseARuntimeObserver._result(symbol=symbol, decision="FAVORABLE"); return self.result
            def last_result(self): return self.result

        run = PhaseARuntimeObserver(self._config(), orchestrator_factory=Stub).run(REQUIRED_SYMBOLS, REQUIRED_TIMEFRAMES)
        btc_entries = [entry for entry in run.journal.entries if entry.observation.symbol == "BTCUSDT"]
        self.assertEqual(len(btc_entries), 1)
        observation = btc_entries[0].observation
        self.assertEqual(observation.timeframe, "1h")
        self.assertEqual(observation.decision, "FAVORABLE")
        self.assertIsNone(observation.directional_raw_strength)
        self.assertIsNone(observation.context_score)
        self.assertIsNone(observation.composite)
        self.assertIsNone(observation.relative_rank)
        self.assertIsNone(observation.relative_percentile)

    def test_unfavorable_creates_one_observation_without_d3(self):
        class Stub:
            def __init__(self): self.result = None
            def run(self, symbol, timeframes): self.result = TestPhaseARuntimeObserver._result(symbol=symbol, decision="UNFAVORABLE", score=-31.5); return self.result
            def last_result(self): return self.result

        run = PhaseARuntimeObserver(self._config(), orchestrator_factory=Stub).run(REQUIRED_SYMBOLS, REQUIRED_TIMEFRAMES)
        btc_entries = [entry for entry in run.journal.entries if entry.observation.symbol == "BTCUSDT"]
        self.assertEqual(len(btc_entries), 1)
        observation = btc_entries[0].observation
        self.assertEqual(observation.timeframe, "1h")
        self.assertEqual(observation.decision, "UNFAVORABLE")
        self.assertIsNone(observation.directional_raw_strength)
        self.assertIsNone(observation.context_score)
        self.assertIsNone(observation.composite)
        self.assertIsNone(observation.relative_rank)
        self.assertIsNone(observation.relative_percentile)

    def test_profile_blocked_creates_no_successful_observation(self):
        class Stub:
            def __init__(self): self.result = None
            def run(self, symbol, timeframes):
                result = TestPhaseARuntimeObserver._result(symbol=symbol)
                result.statistics.current_stage = PipelineStage.PROFILE
                result.statistics.success = False
                result.statistics.error_message = "Profile intelligence blocked before Score/Decision: Extreme market risk"
                result.score = None
                result.decision = None
                self.result = result
                raise PipelineError(result.statistics.error_message)
            def last_result(self): return self.result

        run = PhaseARuntimeObserver(self._config(), orchestrator_factory=Stub).run(REQUIRED_SYMBOLS, REQUIRED_TIMEFRAMES)
        self.assertEqual(len([x for x in run.records if x["status"] == "OBSERVED" and x["symbol"] == "ADAUSDT"]), 0)
        self.assertIn("PIPELINE_BLOCKED", {x["status"] for x in run.records if x["symbol"] == "ADAUSDT"})

    def test_no_score_or_decision_recalculation_in_observer(self):
        class Stub:
            def __init__(self): self.result = None
            def run(self, symbol, timeframes): self.result = TestPhaseARuntimeObserver._result(symbol=symbol, decision="FAVORABLE"); return self.result
            def last_result(self): return self.result

        run = PhaseARuntimeObserver(self._config(), orchestrator_factory=Stub).run(REQUIRED_SYMBOLS, REQUIRED_TIMEFRAMES)
        obs = next(record for record in run.records if record["status"] == "OBSERVED" and record["symbol"] == "BTCUSDT")
        self.assertEqual(obs["source_outputs"]["score"]["raw_score"], 31.5)
        self.assertEqual(obs["source_outputs"]["decision"]["decision"], "FAVORABLE")
        self.assertEqual(obs["observation"]["raw_score"], 31.5)
        self.assertEqual(obs["observation"]["decision"], "FAVORABLE")

    def test_no_execution_access_or_requests(self):
        text = (ROOT / "tools" / "orion_phase_a_runtime_observer.py").read_text(encoding="utf-8")
        for forbidden in ("ExecutionEngine", "PaperExecutionAdapter", "LiveExecutionAdapter", "order_endpoint"):
            self.assertNotIn(forbidden, text)

    def test_primary_timeframe_is_canonical_1h(self):
        class Stub:
            def __init__(self): self.result = None
            def run(self, symbol, timeframes): self.result = TestPhaseARuntimeObserver._result(symbol=symbol, decision="WAIT"); return self.result
            def last_result(self): return self.result

        run = PhaseARuntimeObserver(self._config(), orchestrator_factory=Stub).run(REQUIRED_SYMBOLS, REQUIRED_TIMEFRAMES)
        btc = next(record for record in run.records if record["status"] == "OBSERVED" and record["symbol"] == "BTCUSDT")
        self.assertEqual(btc["primary_timeframe"], "1h")
        self.assertEqual(btc["timeframe"], "1h")

    def test_4h_and_1d_are_boundary_only(self):
        class Stub:
            def __init__(self): self.result = None
            def run(self, symbol, timeframes): self.result = TestPhaseARuntimeObserver._result(symbol=symbol, decision="FAVORABLE"); return self.result
            def last_result(self): return self.result

        run = PhaseARuntimeObserver(self._config(), orchestrator_factory=Stub).run(REQUIRED_SYMBOLS, REQUIRED_TIMEFRAMES)
        btc_unavailable = [x for x in run.records if x["symbol"] == "BTCUSDT" and x["status"] == UNAVAILABLE_AT_BOUNDARY]
        self.assertEqual({x["timeframe"] for x in btc_unavailable}, {"4h", "1d"})
        for record in btc_unavailable:
            self.assertEqual(record["reason"], "ORION runtime produced a symbol-level DecisionResult from the canonical primary timeframe; no independent DecisionResult exists for this timeframe.")

    def test_favorable_provenance_is_signal_time(self):
        class Stub:
            def __init__(self): self.result = None
            def run(self, symbol, timeframes): self.result = TestPhaseARuntimeObserver._result(symbol=symbol, decision="FAVORABLE"); return self.result
            def last_result(self): return self.result

        run = PhaseARuntimeObserver(self._config(), orchestrator_factory=Stub).run(REQUIRED_SYMBOLS, REQUIRED_TIMEFRAMES)
        entry = next(entry for entry in run.journal.entries if entry.observation.symbol == "BTCUSDT")
        self.assertEqual(entry.observation.provenance, "SIGNAL_TIME_OBSERVED")

    def test_unfavorable_provenance_is_signal_time(self):
        class Stub:
            def __init__(self): self.result = None
            def run(self, symbol, timeframes): self.result = TestPhaseARuntimeObserver._result(symbol=symbol, decision="UNFAVORABLE", score=-31.5); return self.result
            def last_result(self): return self.result

        run = PhaseARuntimeObserver(self._config(), orchestrator_factory=Stub).run(REQUIRED_SYMBOLS, REQUIRED_TIMEFRAMES)
        entry = next(entry for entry in run.journal.entries if entry.observation.symbol == "BTCUSDT")
        self.assertEqual(entry.observation.provenance, "SIGNAL_TIME_OBSERVED")


if __name__ == "__main__":
    unittest.main()
