from __future__ import annotations

import ast
import builtins
import sys
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.orchestrator import (
    OrchestratorResult,
    PipelineError,
    PipelineStage,
    PipelineStatistics,
)
from enums import DataHealth, Timeframe
from models.analysis import AnalysisResult
from models.decision import DecisionResult
from models.market import MarketDataset, MarketMetadata, TimeframeData
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics, TimeframeProfile
from models.score import ScoreResult
from models.signal_journal import SignalJournal, SignalJournalEntry
from tools.orion_phase_a_runtime_observer import (
    REQUIRED_SYMBOLS,
    REQUIRED_TIMEFRAMES,
    UNAVAILABLE_AT_BOUNDARY,
    PhaseARuntimeObserver,
    _primary_timeframe,
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
            trend="Bullish",
            trend_strength="Strong",
            momentum="Buy",
            volume_strength="Strong",
            volatility=0.02,
            volatility_level="Normal",
            liquidity=0.9,
            market_phase="Markup",
            confidence=80.0,
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
            statistics=PipelineStatistics(
                finished_at=now,
                current_stage=PipelineStage.FINISHED,
                completed_stage_count=8,
                success=True,
            ),
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

    def test_required_universe_and_binding(self):
        self.assertEqual(REQUIRED_SYMBOLS, ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"))
        self.assertEqual(REQUIRED_TIMEFRAMES, ("1h", "4h", "1d"))
        config = self._config("ce97cb6064dc0d0cfd02e15d4f30f1d80b824c2c")
        self.assertEqual(config.baseline_commit, "c54dc67792776da905a3efb1f667c1869c15db3d")
        self.assertEqual(len(config.configuration_fingerprint), 64)
        self.assertTrue(config.universe_identity.startswith("UNIV-"))

    def test_observation_preserves_orion_outputs(self):
        extraction = extract_observation(
            self._result(decision="FAVORABLE", score=31.5),
            "1h",
            timestamp=datetime(2026, 8, 17, 20, 0, tzinfo=timezone.utc),
        )
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
        observation = extract_observation(
            self._result(), "1h", timestamp=datetime(2026, 8, 17, 20, 0, tzinfo=timezone.utc)
        ).observation
        assert observation is not None
        journal = SignalJournal().record(SignalJournalEntry(observation=observation))
        self.assertEqual(len(journal), 1)
        self.assertIsNone(journal.entries[0].outcome)

    def test_missing_boundary_is_not_guessed(self):
        result = self._result()
        characteristics = replace(result.profile.market, market_phase="")
        profile = replace(result.profile, market=characteristics)
        result = replace(result, profile=profile)
        extraction = extract_observation(
            result, "1h", timestamp=datetime(2026, 8, 17, 20, 0, tzinfo=timezone.utc)
        )
        self.assertEqual(extraction.status, UNAVAILABLE_AT_BOUNDARY)
        self.assertIn("market_regime", extraction.unavailable_fields)
        self.assertIsNone(extraction.observation)

    def test_wait_extracts_one_signal_time_observation(self):
        extraction = extract_wait_observation(
            self._result(decision="WAIT"), "1h", timestamp=datetime(2026, 8, 17, 20, 0, tzinfo=timezone.utc)
        )
        self.assertEqual(extraction.status, "OBSERVED")
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
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        self.assertNotIn("engines.execution_engine", imports)
        self.assertNotIn("models.execution", imports)
        for forbidden in (
            "Opportunity", "OpportunityRelativeRanker", "OpportunityRankingInput", "build_ranking_inputs",
            "ranker.rank", "SignalOutcome", "forward_outcome_validation", "outcome_1h", "outcome_4h",
            "outcome_24h", "mfe", "mae",
        ):
            self.assertNotIn(forbidden, text)

    def test_ast_import_guard_blocks_d3_imports(self):
        tree = ast.parse((ROOT / "tools" / "orion_phase_a_runtime_observer.py").read_text(encoding="utf-8"))
        forbidden_modules = {"engines.opportunity_relative_ranking", "models.opportunity"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name, forbidden_modules)
            elif isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module, forbidden_modules)

    def test_directional_runtime_never_imports_d3_or_opportunity(self):
        real_import = builtins.__import__
        requested = []

        def spy_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in {"engines.opportunity_relative_ranking", "models.opportunity"}:
                requested.append(name)
                raise AssertionError(f"forbidden runtime import: {name}")
            return real_import(name, globals, locals, fromlist, level)

        for decision in ("FAVORABLE", "UNFAVORABLE"):
            with mock.patch("builtins.__import__", side_effect=spy_import):
                observer = PhaseARuntimeObserver(
                    self._config(),
                    orchestrator_factory=lambda: self._single_result_orchestrator(decision),
                )
                run = observer.run(REQUIRED_SYMBOLS, REQUIRED_TIMEFRAMES)
                btc = [e for e in run.journal.entries if e.observation.symbol == "BTCUSDT"]
                self.assertEqual(len(btc), 1)
                self.assertEqual(btc[0].observation.timeframe, "1h")
        self.assertEqual(requested, [])

    def _single_result_orchestrator(self, decision):
        result = self._result(decision=decision, score=31.5 if decision == "FAVORABLE" else -31.5)

        class Stub:
            def __init__(self):
                self.result = result
                self._analysis_engine = mock.Mock()
                self._analysis_engine._select_primary_timeframe.side_effect = lambda dataset: (None, Timeframe.H1)

            def run(self, symbol, timeframes):
                self.result = TestPhaseARuntimeObserver._result(
                    symbol=symbol,
                    decision=decision,
                    score=31.5 if decision == "FAVORABLE" else -31.5,
                )
                return self.result

            def last_result(self):
                return self.result

        return Stub()

    def test_directional_matrix_and_d3_none_contract(self):
        for decision in ("FAVORABLE", "UNFAVORABLE"):
            run = PhaseARuntimeObserver(
                self._config(),
                orchestrator_factory=lambda d=decision: self._single_result_orchestrator(d),
            ).run(REQUIRED_SYMBOLS, REQUIRED_TIMEFRAMES)
            btc_entries = [entry for entry in run.journal.entries if entry.observation.symbol == "BTCUSDT"]
            self.assertEqual(len(btc_entries), 1)
            observation = btc_entries[0].observation
            self.assertEqual(observation.timeframe, "1h")
            self.assertEqual(observation.decision, decision)
            for field in (
                "directional_raw_strength", "context_score", "composite", "relative_rank", "relative_percentile"
            ):
                self.assertIsNone(getattr(observation, field))
            btc_records = [record for record in run.records if record["symbol"] == "BTCUSDT"]
            self.assertEqual(len([r for r in btc_records if r["status"] == "OBSERVED"]), 1)
            self.assertEqual({r["timeframe"] for r in btc_records if r["status"] == UNAVAILABLE_AT_BOUNDARY}, {"4h", "1d"})

    def test_wait_matrix(self):
        run = PhaseARuntimeObserver(self._config(), orchestrator_factory=lambda: self._single_result_orchestrator("WAIT")).run(REQUIRED_SYMBOLS, REQUIRED_TIMEFRAMES)
        btc_entries = [entry for entry in run.journal.entries if entry.observation.symbol == "BTCUSDT"]
        self.assertEqual(len(btc_entries), 1)
        self.assertEqual(btc_entries[0].observation.decision, "WAIT")
        self.assertEqual(btc_entries[0].observation.timeframe, "1h")
        self.assertEqual({r["timeframe"] for r in run.records if r["symbol"] == "BTCUSDT" and r["status"] == UNAVAILABLE_AT_BOUNDARY}, {"4h", "1d"})

    def test_primary_selector_identity(self):
        selector_calls = []
        created = []
        result = self._result(decision="WAIT")

        class SelectorSpy:
            def __init__(self, owner):
                self.owner = owner
                self.calls = 0

            def __call__(self, dataset):
                self.calls += 1
                selector_calls.append(self.owner)
                return None, Timeframe.H1

        class Stub:
            def __init__(self):
                self.result = result
                self._analysis_engine = mock.Mock()
                self._analysis_engine._select_primary_timeframe = SelectorSpy(self)
                created.append(self)

            def run(self, symbol, timeframes):
                self.result = TestPhaseARuntimeObserver._result(symbol=symbol, decision="WAIT")
                return self.result

            def last_result(self):
                return self.result

        class CapturingFactory:
            def __call__(self):
                instance = Stub()
                created.append(instance)
                return instance

        # The observer must call the selector on each actual Orchestrator instance it receives.
        run = PhaseARuntimeObserver(self._config(), orchestrator_factory=CapturingFactory()).run(
            REQUIRED_SYMBOLS, REQUIRED_TIMEFRAMES
        )
        self.assertTrue(run.journal.entries)
        self.assertEqual(len(selector_calls), len(REQUIRED_SYMBOLS) * 2)
        self.assertEqual({id(owner) for owner in selector_calls}, {id(instance) for instance in created})
        for instance in created:
            self.assertGreater(instance._analysis_engine._select_primary_timeframe.calls, 0)
        btc = [record for record in run.records if record["symbol"] == "BTCUSDT" and record["status"] == "OBSERVED"]
        self.assertEqual([record["timeframe"] for record in btc], ["1h"])

    def test_missing_primary_selector_fails_closed_without_new_analysis_engine(self):
        constructed = []

        class ForbiddenAnalysisEngine:
            def __init__(self, *args, **kwargs):
                constructed.append(True)
                raise AssertionError("fallback AnalysisEngine construction is forbidden")

        result = self._result(decision="WAIT")

        class MissingSelectorEngine:
            pass

        class Stub:
            def __init__(self):
                self.result = result
                self._analysis_engine = MissingSelectorEngine()

            def run(self, symbol, timeframes):
                self.result = TestPhaseARuntimeObserver._result(symbol=symbol, decision="WAIT")
                return self.result

            def last_result(self):
                return self.result

        with mock.patch("tools.orion_phase_a_runtime_observer.AnalysisEngine", ForbiddenAnalysisEngine):
            observer = PhaseARuntimeObserver(self._config(), orchestrator_factory=Stub)
            self.assertIsNone(_primary_timeframe(Stub(), result))
            run = observer.run(REQUIRED_SYMBOLS, REQUIRED_TIMEFRAMES)

        self.assertEqual(constructed, [])
        btc = [record for record in run.records if record["symbol"] == "BTCUSDT"]
        self.assertEqual([record["status"] for record in btc if record["timeframe"] == "UNRESOLVED"], [UNAVAILABLE_AT_BOUNDARY])
        self.assertEqual(len([entry for entry in run.journal.entries if entry.observation.symbol == "BTCUSDT"]), 0)

    def test_profile_blocked_creates_no_successful_observation(self):
        class Stub:
            def __init__(self):
                self.result = None

            def run(self, symbol, timeframes):
                result = TestPhaseARuntimeObserver._result(symbol=symbol)
                result.statistics.current_stage = PipelineStage.PROFILE
                result.statistics.success = False
                result.statistics.error_message = "Profile intelligence blocked before Score/Decision: Extreme market risk"
                result.score = None
                result.decision = None
                self.result = result
                raise PipelineError(result.statistics.error_message)

            def last_result(self):
                return self.result

        run = PhaseARuntimeObserver(self._config(), orchestrator_factory=Stub).run(REQUIRED_SYMBOLS, REQUIRED_TIMEFRAMES)
        ada_records = [record for record in run.records if record["symbol"] == "ADAUSDT"]
        self.assertEqual(len([record for record in ada_records if record["status"] == "OBSERVED"]), 0)
        self.assertIn("PIPELINE_BLOCKED", {record["status"] for record in ada_records})

    def test_no_score_or_decision_recalculation_in_observer(self):
        class Stub:
            def __init__(self):
                self.result = None
                self._analysis_engine = mock.Mock()
                self._analysis_engine._select_primary_timeframe.side_effect = lambda dataset: (None, Timeframe.H1)

            def run(self, symbol, timeframes):
                self.result = TestPhaseARuntimeObserver._result(symbol=symbol)
                return self.result

            def last_result(self):
                return self.result

        run = PhaseARuntimeObserver(self._config(), orchestrator_factory=Stub).run(REQUIRED_SYMBOLS, REQUIRED_TIMEFRAMES)
        obs = next(record for record in run.records if record["status"] == "OBSERVED" and record["symbol"] == "BTCUSDT")
        self.assertEqual(obs["source_outputs"]["score"]["raw_score"], 31.5)
        self.assertEqual(obs["source_outputs"]["decision"]["decision"], "FAVORABLE")

    def test_execution_isolation(self):
        tree = ast.parse((ROOT / "tools" / "orion_phase_a_runtime_observer.py").read_text(encoding="utf-8"))
        forbidden = {"engines.execution_engine", "adapters.paper_execution", "adapters.live_execution", "models.execution"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name, forbidden)
            elif isinstance(node, ast.ImportFrom):
                self.assertNotIn(node.module, forbidden)


if __name__ == "__main__":
    unittest.main()
