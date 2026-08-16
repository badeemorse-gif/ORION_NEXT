"""Contract tests for pipeline fail-fast stage boundaries."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import MagicMock

import pandas as pd

from core.orchestrator import Orchestrator, OrchestratorConfig, PipelineError, PipelineStage
from enums import DataHealth, Timeframe
from models.analysis import AnalysisResult
from models.market import MarketDataset, MarketMetadata, TimeframeData
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics, TimeframeProfile
from models.score import ScoreResult


class TestOrchestratorStageFailureBoundary(TestCase):
    """A failed stage must prevent every downstream stage from executing."""

    def _dataset(self) -> MarketDataset:
        now = datetime.now(timezone.utc)
        dataframe = pd.DataFrame(
            {"open": [100.0], "high": [101.0], "low": [99.0], "close": [100.5], "volume": [10.0]},
            index=pd.DatetimeIndex([now], name="timestamp"),
        )
        return MarketDataset(
            metadata=MarketMetadata(
                symbol="BTCUSDT", exchange="BINANCE", source="TEST", cache_version="1.0.0",
                downloaded_at=now, last_updated_at=now,
            ),
            timeframes={
                Timeframe.M1: TimeframeData(
                    timeframe=Timeframe.M1, dataframe=dataframe,
                    data_health=DataHealth.ACCEPTABLE, candles_count=1,
                    first_timestamp=now, last_timestamp=now,
                )
            },
        )

    @staticmethod
    def _valid_profile() -> ProfileResult:
        now = datetime.now(timezone.utc)
        timeframes = tuple(
            TimeframeProfile(
                timeframe=timeframe.value,
                characteristics=MarketCharacteristics(),
                candles_count=1,
                first_timestamp=now,
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
            statistics=ProfileStatistics(completion_ratio=1.0, total_candles=3),
            timeframes=timeframes,
            is_tradeable=True,
            warnings=(),
            blocks=(),
        )

    def _orchestrator(self, failing_stage: str):
        dataset = self._dataset()
        provider = MagicMock()
        provider.execute.return_value = dataset
        storage = MagicMock()

        validation = MagicMock()
        validation.validate_dataset.return_value = MagicMock()

        indicator = MagicMock()
        indicator.calculate_dataset.return_value = dataset

        analysis = MagicMock()
        analysis.analyze.return_value = AnalysisResult(
            market_state="NEUTRAL",
            strength=0.0,
            signals=["STAGE_BOUNDARY_FIXTURE"],
            warnings=[],
        )

        profile = MagicMock()
        profile.build_profile.return_value = self._valid_profile()

        score = MagicMock()
        score.calculate.return_value = ScoreResult(
            score=0.0,
            category="NEUTRAL",
            factors=["STAGE_BOUNDARY_FIXTURE"],
        )

        decision = MagicMock()
        decision_result = MagicMock()
        decision_result.decision = "WAIT"
        decision_result.confidence = 50.0
        decision_result.reasons = ["STAGE_BOUNDARY_FIXTURE"]
        decision.decide.return_value = decision_result

        stages = {
            "STORE": storage.execute,
            "INDICATORS": indicator.calculate_dataset,
            "ANALYSIS": analysis.analyze,
            "PROFILE": profile.build_profile,
            "SCORE": score.calculate,
            "DECISION": decision.decide,
        }
        stages[failing_stage].side_effect = ValueError(f"forced {failing_stage} failure")

        orchestrator = Orchestrator(
            provider=provider, storage=storage, indicator_engine=indicator,
            analysis_engine=analysis, profile_engine=profile, score_engine=score,
            decision_engine=decision, validation_engine=validation,
            config=OrchestratorConfig(ENABLE_TIMING=False),
        )
        return orchestrator, {
            "indicator": indicator,
            "analysis": analysis,
            "profile": profile,
            "score": score,
            "decision": decision,
        }

    def test_failed_stage_blocks_all_downstream_stages(self) -> None:
        """Failure at any intelligence/execution-preparation stage must fail fast."""
        stage_order = [
            (PipelineStage.STORE, "STORE", ["indicator", "analysis", "profile", "score", "decision"]),
            (PipelineStage.INDICATORS, "INDICATORS", ["analysis", "profile", "score", "decision"]),
            (PipelineStage.ANALYSIS, "ANALYSIS", ["profile", "score", "decision"]),
            (PipelineStage.PROFILE, "PROFILE", ["score", "decision"]),
            (PipelineStage.SCORE, "SCORE", ["decision"]),
            (PipelineStage.DECISION, "DECISION", []),
        ]

        preceding = {
            "PROFILE": ["indicator", "analysis"],
            "SCORE": ["indicator", "analysis", "profile"],
            "DECISION": ["indicator", "analysis", "profile", "score"],
        }

        for expected_stage, failing_stage, downstream in stage_order:
            with self.subTest(stage=failing_stage):
                orchestrator, mocks = self._orchestrator(failing_stage)

                with self.assertRaises(PipelineError):
                    orchestrator.run_pipeline("BTCUSDT", ["1m"])

                self.assertEqual(orchestrator.statistics().current_stage, expected_stage)
                self.assertFalse(orchestrator.statistics().success)
                self.assertIsNotNone(orchestrator.last_result())
                self.assertIsNone(
                    orchestrator.last_result().execution_plan,
                    "A failed orchestration must not expose an ExecutionPlan as if planning completed.",
                )

                for name in preceding.get(failing_stage, []):
                    method = {
                        "indicator": mocks["indicator"].calculate_dataset,
                        "analysis": mocks["analysis"].analyze,
                        "profile": mocks["profile"].build_profile,
                        "score": mocks["score"].calculate,
                        "decision": mocks["decision"].decide,
                    }[name]
                    method.assert_called_once()

                for name in downstream:
                    method = {
                        "indicator": mocks["indicator"].calculate_dataset,
                        "analysis": mocks["analysis"].analyze,
                        "profile": mocks["profile"].build_profile,
                        "score": mocks["score"].calculate,
                        "decision": mocks["decision"].decide,
                    }[name]
                    method.assert_not_called()


if __name__ == "__main__":
    import unittest
    unittest.main()
