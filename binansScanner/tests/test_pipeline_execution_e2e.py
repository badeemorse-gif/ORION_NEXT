"""ORION Composition Root decision -> execution -> report E2E contract."""
from __future__ import annotations
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import pandas as pd
from core.dependency_container import ContainerConfiguration, DependencyContainer
from enums import DataHealth, Timeframe
from models.decision import DecisionResult
from models.execution import ExecutionResult, ExecutionSide, ExecutionStatus
from models.market import MarketDataset, MarketMetadata, TimeframeData
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics
class TestPipelineExecutionE2E(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_directory = tempfile.TemporaryDirectory(); database_path = str(Path(self._temp_directory.name) / "orion_e2e.db")
        self.container = DependencyContainer(ContainerConfiguration(database_path=database_path, binance_api_key="", binance_api_secret="", binance_testnet=True))
    def tearDown(self) -> None:
        self.container.reset(); self._temp_directory.cleanup()
    @staticmethod
    def _dataset() -> MarketDataset:
        now = datetime.now(timezone.utc); closes = [100_000.0 + float(index * 100.0) for index in range(60)]
        timestamps = pd.date_range(end=now, periods=len(closes), freq="h", tz="UTC")
        dataframe = pd.DataFrame({"open": [value - 50.0 for value in closes], "high": [value + 100.0 for value in closes], "low": [value - 100.0 for value in closes], "close": closes, "volume": [1_000.0] * len(closes)}, index=timestamps)
        timeframe_data = TimeframeData(timeframe=Timeframe.H1, dataframe=dataframe, data_health=DataHealth.GOOD, candles_count=len(dataframe), first_timestamp=now - timedelta(hours=len(dataframe) - 1), last_timestamp=now)
        metadata = MarketMetadata(symbol="BTCUSDT", exchange="BINANCE", source="E2E_FIXTURE", cache_version="1.0.0", downloaded_at=now, last_updated_at=now)
        return MarketDataset(metadata=metadata, timeframes={Timeframe.H1: timeframe_data})
    @staticmethod
    def _tradeable_profile() -> ProfileResult:
        return ProfileResult(symbol="BTCUSDT", market=MarketCharacteristics(), statistics=ProfileStatistics(), timeframes=(), warnings=(), blocks=(), is_tradeable=True)
    def _run_with_real_market_stages(self, decision: DecisionResult | None = None):
        dataset = self._dataset(); provider = self.container.build_market_data_provider(); storage = self.container.build_market_storage(); pipeline = self.container.build_pipeline()
        decision_patch = patch.object(pipeline._orchestrator._decision_engine, "decide", return_value=decision) if decision is not None else patch.object(pipeline._orchestrator._decision_engine, "decide", wraps=pipeline._orchestrator._decision_engine.decide)
        with patch.object(provider, "execute", return_value=dataset), patch.object(storage, "execute", return_value=None), patch.object(pipeline._orchestrator._profile_engine, "build_profile", return_value=self._tradeable_profile()), decision_patch:
            return pipeline.run_symbol("BTCUSDT", [Timeframe.H1.value], quantity=1.0)
    def test_container_pipeline_reaches_execution_and_builds_report(self) -> None:
        result = self._run_with_real_market_stages()
        self.assertTrue(result.success); self.assertIsNone(result.error_message); self.assertIsNotNone(result.orchestrator_result); self.assertIsNotNone(result.orchestrator_result.execution_plan); self.assertIsNotNone(result.execution_result); self.assertIsNotNone(result.report_result)
        plan = result.orchestrator_result.execution_plan; execution = result.execution_result; report = result.report_result; assert plan is not None; assert execution is not None; assert report is not None
        self.assertEqual(result.orchestrator_result.decision.decision, "WAIT"); self.assertEqual(plan.side, ExecutionSide.HOLD); self.assertEqual(execution.status, ExecutionStatus.SKIPPED); self.assertFalse(execution.executed); self.assertIsNone(execution.order_id); self.assertIs(report.execution, execution); self.assertTrue(report.is_complete)
    def test_container_pipeline_executes_favorable_decision_end_to_end(self) -> None:
        result = self._run_with_real_market_stages(DecisionResult(decision="FAVORABLE", confidence=0.95, reasons=["E2E executable decision"]))
        self.assertTrue(result.success); self.assertIsNone(result.error_message); self.assertIsNotNone(result.orchestrator_result); self.assertIsNotNone(result.execution_result); self.assertIsNotNone(result.report_result)
        plan = result.orchestrator_result.execution_plan; execution = result.execution_result; report = result.report_result; assert plan is not None; assert execution is not None; assert report is not None
        self.assertEqual(result.orchestrator_result.decision.decision, "FAVORABLE"); self.assertEqual(plan.side, ExecutionSide.BUY); self.assertEqual(execution.status, ExecutionStatus.EXECUTED); self.assertTrue(execution.executed); self.assertIsNotNone(execution.order_id); self.assertTrue(execution.order_id.startswith("PAPER-")); self.assertIs(report.execution, execution); self.assertTrue(report.is_complete)
    def test_execution_failure_stops_before_report_boundary(self) -> None:
        pipeline = self.container.build_pipeline(); execution_failure = ExecutionResult(status=ExecutionStatus.FAILED, message="forced execution failure"); report_builder = MagicMock()
        with patch.object(pipeline._orchestrator, "run", return_value=MagicMock(execution_plan=MagicMock())), patch.object(pipeline._execution_engine, "execute", return_value=execution_failure), patch.object(pipeline._report_engine, "build_report", report_builder):
            result = pipeline.run_symbol("BTCUSDT", [Timeframe.H1.value], quantity=1.0)
        self.assertFalse(result.success); self.assertEqual(result.failed_stage, "EXECUTION"); self.assertIs(result.execution_result, execution_failure); self.assertIsNone(result.report_result); report_builder.assert_not_called()
