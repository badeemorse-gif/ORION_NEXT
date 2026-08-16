"""Contract tests for the canonical market validation/persistence order."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import MagicMock

import pandas as pd

from core.orchestrator import Orchestrator, OrchestratorConfig, PipelineError, PipelineStage
from enums import DataHealth, Timeframe
from models.analysis import AnalysisResult
from models.decision import DecisionResult
from models.market import MarketDataset, MarketMetadata, TimeframeData
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics, TimeframeProfile
from models.score import ScoreResult


class TestOrchestratorValidationOrder(TestCase):
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

    def _orchestrator(self, provider: MagicMock, storage: MagicMock, validation: MagicMock) -> Orchestrator:
        return Orchestrator(
            provider=provider,
            storage=storage,
            indicator_engine=MagicMock(),
            analysis_engine=MagicMock(),
            profile_engine=MagicMock(),
            score_engine=MagicMock(),
            decision_engine=MagicMock(),
            validation_engine=validation,
            config=OrchestratorConfig(ENABLE_TIMING=False),
        )

    def test_invalid_dataset_is_never_persisted(self) -> None:
        """Validation must reject provider output before the storage boundary is reached."""
        dataset = self._dataset()
        provider = MagicMock()
        provider.execute.return_value = dataset
        storage = MagicMock()
        validation = MagicMock()
        validation.validate_dataset.side_effect = ValueError("invalid market data")
        orchestrator = self._orchestrator(provider, storage, validation)

        with self.assertRaises(PipelineError):
            orchestrator.run_pipeline("BTCUSDT", ["1m"])

        validation.validate_dataset.assert_called_once_with(dataset)
        storage.execute.assert_not_called()
        self.assertEqual(orchestrator.statistics().current_stage, PipelineStage.VALIDATION)

    def test_valid_dataset_is_persisted_after_validation(self) -> None:
        """A canonical valid analysis/profile fixture must reach and prove the storage boundary."""
        dataset = self._dataset()
        provider = MagicMock()
        provider.execute.return_value = dataset
        storage = MagicMock()
        validation = MagicMock()
        validation.validate_dataset.return_value = MagicMock()

        indicator = MagicMock()
        indicator.calculate_dataset.return_value = dataset

        canonical_analysis = AnalysisResult(
            market_state="NEUTRAL",
            strength=0.0,
            signals=["VALIDATION_ORDER_FIXTURE"],
            warnings=[],
        )
        analysis = MagicMock()
        analysis.analyze.return_value = canonical_analysis

        profile = MagicMock()
        profile_result = self._valid_profile()
        profile.build_profile.return_value = profile_result

        score = MagicMock()
        score.calculate.return_value = ScoreResult(
            score=0.0,
            category="NEUTRAL",
            factors=["VALIDATION_ORDER_FIXTURE"],
        )

        decision = MagicMock()
        decision.decide.return_value = DecisionResult(
            decision="WAIT",
            confidence=50.0,
            reasons=["VALIDATION_ORDER_FIXTURE"],
        )

        orchestrator = Orchestrator(
            provider=provider,
            storage=storage,
            indicator_engine=indicator,
            analysis_engine=analysis,
            profile_engine=profile,
            score_engine=score,
            decision_engine=decision,
            validation_engine=validation,
            config=OrchestratorConfig(ENABLE_TIMING=False),
        )

        result = orchestrator.run_pipeline("BTCUSDT", ["1m"])

        validation.validate_dataset.assert_called_once_with(dataset)
        storage.execute.assert_called_once_with(dataset)
        analysis.analyze.assert_called_once_with(dataset)
        profile.build_profile.assert_called_once_with(dataset)
        self.assertEqual(profile_result.timeframe_count, 3)
        self.assertEqual(
            {item.timeframe for item in profile_result.timeframes},
            {"1d", "4h", "1h"},
        )
        score.calculate.assert_called_once_with(canonical_analysis)
        decision.decide.assert_called_once_with(canonical_analysis, score.calculate.return_value)
        self.assertTrue(result.statistics.success)
        self.assertEqual(result.statistics.current_stage, PipelineStage.FINISHED)


if __name__ == "__main__":
    import unittest
    unittest.main()
