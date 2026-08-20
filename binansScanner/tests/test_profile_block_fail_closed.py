from __future__
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock
import pandas as pd
from core.orchestrator import Orchestrator, OrchestratorConfig, PipelineError, PipelineStage
from enums import DataHealth, Timeframe
from models.analysis import AnalysisResult
from models.market import MarketDataset, MarketMetadata, TimeframeData
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics
from models.score import ScoreResult
from models.decision import DecisionResult
class TestProfileBlockFailClosed(TestCase):
    def _dataset(self) -> MarketDataset:
        now = datetime.now(timezone.utc); frame = pd.DataFrame({"open":[100.0],"high":[101.0],"low":[99.0],"close":[100.5],"volume":[10.0]}, index=pd.DatetimeIndex([now], name="timestamp"))
        return MarketDataset(metadata=MarketMetadata(symbol="BTCUSDT", exchange="BINANCE", source="TEST", cache_version="1.0.0", downloaded_at=now, last_updated_at=now), timeframes={Timeframe.M1: TimeframeData(timeframe=Timeframe.M1, dataframe=frame, data_health=DataHealth.ACCEPTABLE, candles_count=1, first_timestamp=now, last_timestamp=now)})
    @staticmethod
    def _profile(*, tradeable: bool) -> ProfileResult:
        return ProfileResult(symbol="BTCUSDT", market=MarketCharacteristics(), statistics=ProfileStatistics(), timeframes=(), warnings=(), blocks=() if tradeable else ("PROFILE_BLOCK",), is_tradeable=tradeable)
    def _orchestrator(self, profile_result: ProfileResult):
        dataset = self._dataset(); provider = MagicMock(); provider.execute.return_value = dataset; storage = MagicMock(); validation = MagicMock(); validation.validate_dataset.return_value = MagicMock(); indicator = MagicMock(); indicator.calculate_dataset.return_value = dataset; analysis = MagicMock(); analysis.analyze.return_value = AnalysisResult(market_state="NEUTRAL", strength=0.0, signals=["PROFILE_BLOCK_FIXTURE"], warnings=[]); profile = MagicMock(); profile.build_profile.return_value = profile_result; score = MagicMock(); score.calculate.return_value = ScoreResult(score=0.0, category="NEUTRAL", factors=["PROFILE_BLOCK_FIXTURE"]); decision = MagicMock(); decision.decide.return_value = DecisionResult(decision="WAIT", confidence=0.0, reasons=["PROFILE_BLOCK_FIXTURE"]); plan_builder = MagicMock(); plan_builder.build.return_value = MagicMock(name="execution_plan")
        orchestrator = Orchestrator(provider=provider, storage=storage, indicator_engine=indicator, analysis_engine=analysis, profile_engine=profile, score_engine=score, decision_engine=decision, validation_engine=validation, config=OrchestratorConfig(ENABLE_TIMING=False), execution_plan_builder=plan_builder)
        return orchestrator, score, decision, plan_builder
    def test_blocked_profile_fails_closed_before_score_decision_and_plan(self) -> None:
        orchestrator, score, decision, plan_builder = self._orchestrator(self._profile(tradeable=False))
        with self.assertRaisesRegex(PipelineError, "Profile intelligence blocked before Score/Decision"): orchestrator.run_pipeline("BTCUSDT", ["1m"])
        stats = orchestrator.statistics(); self.assertIsNotNone(stats); self.assertEqual(stats.current_stage, PipelineStage.PROFILE); self.assertFalse(stats.success); self.assertIsNone(orchestrator.last_result().execution_plan); score.calculate.assert_not_called(); decision.decide.assert_not_called(); plan_builder.build.assert_not_called()
    def test_tradeable_profile_preserves_existing_score_decision_and_plan_path(self) -> None:
        orchestrator, score, decision, plan_builder = self._orchestrator(self._profile(tradeable=True)); result = orchestrator.run_pipeline("BTCUSDT", ["1m"])
        score.calculate.assert_called_once(); decision.decide.assert_called_once_with(orchestrator._last_result.analysis, score.calculate.return_value); plan_builder.build.assert_called_once_with(result.dataset, decision.decide.return_value); self.assertTrue(result.statistics.success); self.assertEqual(result.statistics.current_stage, PipelineStage.FINISHED); self.assertIs(result.execution_plan, plan_builder.build.return_value)
if __name__ == "__main__":
 import unittest
 unittest.main()