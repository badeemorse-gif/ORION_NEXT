"""Contract tests for historical Observation -> forward outcome validation."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest

from tools.experiment_harness import ExperimentFixture, ExperimentHarness, ObservationSpec, SignalDirection
from tools.forward_outcome_validation import ForwardOutcomeValidator, HistoricalObservation


UTC = timezone.utc


class TestForwardOutcomeValidation(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = ExperimentFixture.generate(
            fixture_id="forward-validation",
            symbol="BTCUSDT",
            start_at=datetime(2025, 1, 1, tzinfo=UTC),
            seed=29,
            periods=97,
        )
        self.harness = ExperimentHarness()
        self.validator = ForwardOutcomeValidator(self.harness)

    def _item(self, index: int, *, score: float, confidence: float, relative_rank: float) -> HistoricalObservation:
        signal = self.fixture.candles[index].timestamp
        spec = ObservationSpec(
            emitted_at=signal,
            direction=SignalDirection.BUY,
            confidence=confidence,
            signal="FAVORABLE",
            context=(("score", score), ("relative_rank", relative_rank)),
            context_timestamps=(("score", signal), ("relative_rank", signal)),
        )
        observation = self.harness.create_observation(self.fixture, spec)
        return HistoricalObservation(
            fixture=self.fixture,
            observation=observation,
            score=score,
            relative_rank=relative_rank,
        )

    def test_process_one_emits_exact_three_future_horizons(self) -> None:
        item = self._item(10, score=20.0, confidence=55.0, relative_rank=80.0)
        record = self.validator.process_one(item)
        self.assertEqual(record.signal_id, item.observation.observation_id)
        self.assertEqual(record.entry_time, item.observation.emitted_at.isoformat())
        self.assertEqual([o.horizon for o in record.outcomes], ["1h", "4h", "24h"])
        for outcome in record.outcomes:
            self.assertGreater(outcome.as_of, item.observation.emitted_at)
            self.assertEqual(outcome.observed_at, item.observation.emitted_at)

    def test_signal_candle_is_never_used_as_forward_outcome(self) -> None:
        item = self._item(10, score=30.0, confidence=60.0, relative_rank=70.0)
        record = self.validator.process_one(item)
        first_future = self.fixture.candles[11]
        one_hour = record.outcome("1h")
        self.assertEqual(one_hour.as_of, first_future.timestamp)
        self.assertEqual(one_hour.close_price, first_future.close)

    def test_mfe_mae_are_directional_and_non_negative(self) -> None:
        buy = self._item(10, score=40.0, confidence=65.0, relative_rank=60.0)
        record = self.validator.process_one(buy)
        for outcome in record.outcomes:
            self.assertGreaterEqual(outcome.mfe_pct, 0.0)
            self.assertGreaterEqual(outcome.mae_pct, 0.0)

        signal = self.fixture.candles[10].timestamp
        sell_obs = self.harness.create_observation(
            self.fixture,
            ObservationSpec(
                emitted_at=signal,
                direction=SignalDirection.SELL,
                confidence=65.0,
                signal="UNFAVORABLE",
                context=(("score", -40.0), ("relative_rank", 40.0)),
                context_timestamps=(("score", signal), ("relative_rank", signal)),
            ),
        )
        sell = self.validator.process_one(
            HistoricalObservation(self.fixture, sell_obs, -40.0, 40.0)
        )
        self.assertGreaterEqual(sell.outcome("1h").mfe_pct, 0.0)
        self.assertGreaterEqual(sell.outcome("1h").mae_pct, 0.0)

    def test_process_many_reports_completeness_rejections_and_leakage(self) -> None:
        valid = [
            self._item(index, score=float(index), confidence=50.0 + index, relative_rank=float(100 - index))
            for index in (10, 20, 30, 40, 50, 60, 70, 71, 72, 73)
        ]
        short_fixture = ExperimentFixture.generate(
            fixture_id="short-forward",
            symbol="BTCUSDT",
            start_at=datetime(2025, 2, 1, tzinfo=UTC),
            seed=29,
            periods=25,
        )
        signal = short_fixture.candles[10].timestamp
        short_obs = self.harness.create_observation(
            short_fixture,
            ObservationSpec(
                emitted_at=signal,
                direction=SignalDirection.BUY,
                confidence=50.0,
                signal="WAIT",
            ),
        )
        rejected = HistoricalObservation(short_fixture, short_obs, score=1.0, relative_rank=1.0)

        report = self.validator.process_many((*valid, rejected))
        self.assertEqual(report.observations_processed, 11)
        self.assertEqual(report.valid_outcomes, 10)
        self.assertEqual(report.rejected_outcomes, 1)
        self.assertEqual(report.outcome_completeness["1h"], 10 / 11)
        self.assertEqual(report.outcome_completeness["4h"], 10 / 11)
        self.assertEqual(report.outcome_completeness["24h"], 10 / 11)
        self.assertTrue(all(check.passed for check in report.leakage_checks))
        self.assertEqual(len(report.records), 10)
        self.assertEqual(len(report.rejected), 1)

    def test_export_rows_contain_required_output_fields_and_timestamps(self) -> None:
        report = self.validator.process_many(
            [self._item(10, score=10.0, confidence=60.0, relative_rank=90.0)]
        )
        row = report.export_rows()[0]
        required = {
            "signal_id", "entry_time", "entry_price", "1h_return_pct", "4h_return_pct", "24h_return_pct",
            "1h_mfe_pct", "1h_mae_pct", "4h_mfe_pct", "4h_mae_pct", "24h_mfe_pct", "24h_mae_pct",
            "1h_outcome_timestamp", "4h_outcome_timestamp", "24h_outcome_timestamp",
        }
        self.assertTrue(required.issubset(row))
        self.assertLess(row["entry_time"], row["1h_outcome_timestamp"])
        self.assertLess(row["1h_outcome_timestamp"], row["4h_outcome_timestamp"])
        self.assertLess(row["4h_outcome_timestamp"], row["24h_outcome_timestamp"])

    def test_analysis_produces_score_deciles_confidence_bands_and_rank_bands(self) -> None:
        observations = [
            self._item(index, score=float(index), confidence=50.0 + index, relative_rank=float(index))
            for index in (10, 20, 30, 40, 50, 60, 70, 71, 72, 73)
        ]
        report = self.validator.process_many(observations)
        self.assertEqual(len(report.score_deciles), 10)
        self.assertEqual(len(report.confidence_bands), 5)
        self.assertEqual(len(report.relative_rank_bands), 5)
        for table in (report.score_deciles, report.confidence_bands, report.relative_rank_bands):
            for band in table:
                self.assertEqual([row.horizon for row in band.horizon_summaries], ["1h", "4h", "24h"])
                for row in band.horizon_summaries:
                    self.assertIsNotNone(row.mean_return_pct)
                    self.assertIsNotNone(row.mean_mfe_pct)
                    self.assertIsNotNone(row.mean_mae_pct)

    def test_no_score_or_decision_recalculation_is_used(self) -> None:
        self.assertEqual(set(self.validator.__class__.__module__.split(".")) & {"engines"}, set())
        report = self.validator.process_many(
            [self._item(10, score=42.0, confidence=71.0, relative_rank=13.0)]
        )
        self.assertEqual(report.records[0].score, 42.0)
        self.assertEqual(report.records[0].confidence, 71.0)
        self.assertEqual(report.records[0].relative_rank, 13.0)


if __name__ == "__main__":
    unittest.main()
