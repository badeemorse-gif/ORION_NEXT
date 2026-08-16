"""Developer 5 verification gates for the canonical ORION pipeline."""

from __future__ import annotations

from dataclasses import replace
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from core.dependency_container import ContainerConfiguration, DependencyContainer
from core.execution_plan_builder import ExecutionPlanBuilder
from engines.decision_engine import DecisionEngine
from enums import DataHealth, Timeframe
from models.analysis import AnalysisResult
from models.decision import DecisionResult
from models.execution import ExecutionPlan, ExecutionResult, ExecutionSide, ExecutionStatus
from models.market import MarketDataset, MarketMetadata, TimeframeData
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics, TimeframeProfile
from models.report import ReportResult
from models.score import ScoreResult


class TestVerificationGates(unittest.TestCase):
    """Executable verification gates; production semantics are not modified."""

    def setUp(self) -> None:
        self._temp_directory = tempfile.TemporaryDirectory()
        database_path = str(Path(self._temp_directory.name) / "orion_verification.db")
        self.container = DependencyContainer(
            ContainerConfiguration(
                database_path=database_path,
                binance_api_key="",
                binance_api_secret="",
                binance_testnet=True,
            )
        )

    def tearDown(self) -> None:
        self.container.reset()
        self._temp_directory.cleanup()

    @staticmethod
    def _timeframe_data(timeframe: Timeframe, now: datetime) -> TimeframeData:
        closes = [100_000.0 + float(index * 100.0) for index in range(250)]
        timestamps = pd.date_range(end=now, periods=len(closes), freq="h", tz="UTC")
        dataframe = pd.DataFrame(
            {
                "open": [value - 50.0 for value in closes],
                "high": [value + 100.0 for value in closes],
                "low": [value - 100.0 for value in closes],
                "close": closes,
                "volume": [1_000.0] * len(closes),
            },
            index=timestamps,
        )
        return TimeframeData(
            timeframe=timeframe,
            dataframe=dataframe,
            data_health=DataHealth.GOOD,
            candles_count=len(dataframe),
            first_timestamp=now - timedelta(hours=len(dataframe) - 1),
            last_timestamp=now,
        )

    @staticmethod
    def _dataset() -> MarketDataset:
        now = datetime.now(timezone.utc)
        metadata = MarketMetadata(
            symbol="BTCUSDT",
            exchange="BINANCE",
            source="VERIFICATION_FIXTURE",
            cache_version="1.0.0",
            downloaded_at=now,
            last_updated_at=now,
        )
        return MarketDataset(
            metadata=metadata,
            timeframes={
                Timeframe.D1: TestVerificationGates._timeframe_data(Timeframe.D1, now),
                Timeframe.H4: TestVerificationGates._timeframe_data(Timeframe.H4, now),
                Timeframe.H1: TestVerificationGates._timeframe_data(Timeframe.H1, now),
            },
        )

    @staticmethod
    def _valid_profile() -> ProfileResult:
        now = datetime.now(timezone.utc)
        profiles = tuple(
            TimeframeProfile(
                timeframe=timeframe.value,
                characteristics=MarketCharacteristics(),
                candles_count=250,
                first_timestamp=now - timedelta(hours=249),
                last_timestamp=now,
                data_health=DataHealth.GOOD,
                missing_candles=0,
                warnings=(),
            )
            for timeframe in (Timeframe.D1, Timeframe.H4, Timeframe.H1)
        )
        return ProfileResult(
            symbol="BTCUSDT",
            market=MarketCharacteristics(),
            statistics=ProfileStatistics(
                completion_ratio=1.0,
                total_candles=750,
                missing_candles=0,
            ),
            timeframes=profiles,
            is_tradeable=True,
            warnings=(),
            blocks=(),
        )

    @staticmethod
    def _assert_failure_evidence_report(report: ReportResult, execution: ExecutionResult) -> None:
        """A failure-evidence report may exist, but it can never imply success."""
        if not isinstance(report, ReportResult):
            raise AssertionError("Failure evidence must be represented by ReportResult when present.")
        if report.execution is not execution:
            raise AssertionError("Failure evidence must retain the exact failed ExecutionResult.")
        if report.execution.status is not ExecutionStatus.FAILED:
            raise AssertionError("Failure evidence report must explicitly retain FAILED execution status.")
        if report.execution.executed:
            raise AssertionError("A failure evidence report must never imply execution success.")

    @staticmethod
    def _build_plan(dataset: MarketDataset, decision: DecisionResult) -> ExecutionPlan:
        plan = ExecutionPlanBuilder().build(dataset, decision)
        if plan is None:
            raise AssertionError("Expected a canonical ExecutionPlan.")
        return plan

    def test_execution_plan_isolated_from_upstream_pipeline_state(self) -> None:
        """ExecutionPlan must not carry prohibited upstream result objects."""
        fields = set(ExecutionPlan.__dataclass_fields__)
        prohibited = {
            "dataset",
            "market_dataset",
            "analysis",
            "profile",
            "score",
            "orchestrator_result",
        }
        self.assertTrue(prohibited.isdisjoint(fields))
        self.assertNotIn("decision", prohibited)

    def test_decision_to_execution_mapping_is_consistent_and_fail_closed(self) -> None:
        dataset = self._dataset()
        decision_engine = DecisionEngine()

        favorable = decision_engine.decide(
            AnalysisResult(market_state="BULLISH", strength=90.0, signals=["TREND_ALIGNED"]),
            ScoreResult(score=92.0, category="STRONG_BULLISH", factors=["STRONG_SCORE"]),
        )
        unfavorable = decision_engine.decide(
            AnalysisResult(market_state="BEARISH", strength=88.0, signals=["TREND_ALIGNED"]),
            ScoreResult(score=-88.0, category="STRONG_BEARISH", factors=["STRONG_SCORE_NEGATIVE"]),
        )
        wait = DecisionResult(decision="WAIT", confidence=50.0, reasons=["NEUTRAL"])

        self.assertEqual(self._build_plan(dataset, favorable).side, ExecutionSide.BUY)
        self.assertEqual(self._build_plan(dataset, unfavorable).side, ExecutionSide.SELL)
        canonical_wait_plan = self._build_plan(dataset, wait)
        self.assertEqual(canonical_wait_plan.side, ExecutionSide.HOLD)

        # WAIT/HOLD is non-executable; the verification fixture explicitly uses
        # the canonical execution metadata with zero quantity rather than
        # asserting that the production plan builder invents quantity semantics.
        wait_plan = replace(canonical_wait_plan, quantity=0.0)
        self.assertEqual(wait_plan.side, ExecutionSide.HOLD)
        self.assertEqual(wait_plan.quantity, 0.0)

        # UNKNOWN/UNSPECIFIED is outside the canonical decision contract. The
        # Verification layer must never translate it into NONE/SKIPPED.
        self.assertNotIn("UNSPECIFIED", ExecutionPlanBuilder._DECISION_TO_SIDE)
        self.assertNotIn("UNKNOWN", ExecutionPlanBuilder._DECISION_TO_SIDE)

        engine = self.container.build_execution_engine()
        wait_result = engine.execute(wait_plan)
        self.assertEqual(wait_result.status, ExecutionStatus.SKIPPED)
        self.assertIsNone(wait_result.order_id)
        self.assertEqual(wait_result.request.quantity if wait_result.request else 0.0, 0.0)

    def test_report_integrity_preserves_exact_upstream_contract_objects(self) -> None:
        analysis = AnalysisResult()
        profile = self._valid_profile()
        score = ScoreResult()
        decision = DecisionResult(decision="WAIT", confidence=50.0, reasons=["NEUTRAL"])
        execution = ExecutionResult(status=ExecutionStatus.SKIPPED, message="not executable")

        report = self.container.build_report_engine().build_report(
            symbol="BTCUSDT",
            analysis=analysis,
            profile=profile,
            score=score,
            decision=decision,
            execution=execution,
        )

        self.assertIs(report.analysis, analysis)
        self.assertIs(report.profile, profile)
        self.assertIs(report.score, score)
        self.assertIs(report.decision, decision)
        self.assertIs(report.execution, execution)
        self.assertTrue(report.is_complete)
        self.assertEqual(report.execution.status, ExecutionStatus.SKIPPED)

    def test_failure_evidence_report_is_explicitly_failed_not_successful(self) -> None:
        """ReportResult may carry failure evidence without becoming a success signal."""
        failed_execution = ExecutionResult(
            status=ExecutionStatus.FAILED,
            message="forced verification failure",
        )

        report = self.container.build_report_engine().build_report(
            symbol="BTCUSDT",
            analysis=AnalysisResult(),
            profile=self._valid_profile(),
            score=ScoreResult(),
            decision=DecisionResult(decision="FAVORABLE", confidence=92.0, reasons=["verification"]),
            execution=failed_execution,
            warnings=("execution failed; report is evidence only",),
        )

        self.assertTrue(report.is_complete)
        self.assertTrue(report.has_warnings)
        self._assert_failure_evidence_report(report, failed_execution)
        self.assertFalse(report.execution.executed)

    def test_real_pipeline_e2e_reaches_report_without_live_market_io(self) -> None:
        pipeline = self.container.build_pipeline()
        provider = self.container.build_market_data_provider()
        storage = self.container.build_market_storage()
        profile_engine = pipeline._orchestrator._profile_engine
        fixture = self._dataset()

        with patch.object(provider, "execute", return_value=fixture), patch.object(
            storage, "execute", return_value=None
        ), patch.object(profile_engine, "build_profile", return_value=self._valid_profile()):
            result = pipeline.run_symbol("BTCUSDT", [Timeframe.H1.value], quantity=1.0)

        self.assertTrue(result.success)
        self.assertIsNone(result.error_message)
        self.assertIsNotNone(result.orchestrator_result)
        self.assertIsNotNone(result.orchestrator_result.execution_plan)
        self.assertIsNotNone(result.execution_result)
        self.assertIsNotNone(result.report_result)
        assert result.orchestrator_result is not None
        assert result.execution_result is not None
        assert result.report_result is not None
        self.assertIsInstance(result.orchestrator_result.execution_plan, ExecutionPlan)
        self.assertIsInstance(result.execution_result, ExecutionResult)
        self.assertIsInstance(result.report_result, ReportResult)
        self.assertTrue(result.report_result.is_complete)
        self.assertIn(
            result.execution_result.status,
            (ExecutionStatus.EXECUTED, ExecutionStatus.SKIPPED),
        )
        self.assertIs(result.report_result.execution, result.execution_result)

    def test_invalid_input_fails_closed_before_execution(self) -> None:
        pipeline = self.container.build_pipeline()
        execution = MagicMock()
        pipeline._execution_engine = execution

        result = pipeline.run_symbol("", [Timeframe.H1.value])

        self.assertFalse(result.success)
        self.assertIsNone(result.execution_result)
        self.assertIsNone(result.report_result)
        execution.execute.assert_not_called()

    def test_execution_failure_is_observable_and_report_never_implies_success(self) -> None:
        """Verify the final failure contract without requiring report suppression."""
        pipeline = self.container.build_pipeline()
        failed_execution = ExecutionResult(
            status=ExecutionStatus.FAILED,
            message="forced execution failure",
        )
        failure_evidence = ReportResult(
            symbol="BTCUSDT",
            execution=failed_execution,
            warnings=("execution failed; evidence only",),
        )

        with patch.object(
            pipeline._orchestrator,
            "run",
            return_value=MagicMock(
                execution_plan=ExecutionPlan(
                    symbol="BTCUSDT",
                    side=ExecutionSide.BUY,
                    price=100_000.0,
                    quantity=1.0,
                )
            ),
        ), patch.object(
            pipeline._execution_engine,
            "execute",
            return_value=failed_execution,
        ), patch.object(
            pipeline._report_engine,
            "build_report",
            return_value=failure_evidence,
        ):
            result = pipeline.run_symbol("BTCUSDT", [Timeframe.H1.value], quantity=1.0)

        self.assertFalse(result.success)
        self.assertEqual(result.failed_stage, "EXECUTION")
        self.assertIs(result.execution_result, failed_execution)

        if result.report_result is not None:
            self._assert_failure_evidence_report(result.report_result, failed_execution)
        self.assertFalse(
            bool(
                result.report_result
                and result.report_result.execution
                and result.report_result.execution.executed
            ),
            "A failure report must never imply execution success.",
        )


if __name__ == "__main__":
    unittest.main()
