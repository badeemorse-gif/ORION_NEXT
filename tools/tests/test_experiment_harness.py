"""Contract tests for the ORION Phase A experiment harness."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from tools.experiment_harness import (
    ExperimentContractError,
    ExperimentFixture,
    ExperimentHarness,
    ExecutionDisabledError,
    ObservationSpec,
    SignalDirection,
)


UTC = timezone.utc


class TestExperimentHarness(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = ExperimentHarness()
        self.fixture = ExperimentFixture.generate(
            fixture_id="phase-a-fixture",
            symbol="BTCUSDT",
            start_at=datetime(2025, 1, 1, tzinfo=UTC),
            seed=17,
            periods=97,
        )
        self.signal_at = self.fixture.candles[10].timestamp
        self.spec = ObservationSpec(
            emitted_at=self.signal_at,
            direction=SignalDirection.BUY,
            confidence=82.5,
            signal="FAVORABLE",
            context=(
                ("market_state", "BULLISH"),
                ("score", 72.0),
            ),
            context_timestamps=(("market_state", self.signal_at), ("score", self.signal_at)),
        )

    def test_fixture_is_repeatable_for_same_seed(self) -> None:
        replay = ExperimentFixture.generate(
            fixture_id="phase-a-fixture",
            symbol="BTCUSDT",
            start_at=datetime(2025, 1, 1, tzinfo=UTC),
            seed=17,
            periods=97,
        )
        self.assertEqual(self.fixture.fingerprint(), replay.fingerprint())
        self.assertEqual(self.fixture.candles, replay.candles)

    def test_fixture_changes_when_seed_changes(self) -> None:
        alternate = ExperimentFixture.generate(
            fixture_id="phase-a-fixture",
            symbol="BTCUSDT",
            start_at=datetime(2025, 1, 1, tzinfo=UTC),
            seed=18,
            periods=97,
        )
        self.assertNotEqual(self.fixture.fingerprint(), alternate.fingerprint())

    def test_timestamp_integrity_requires_consecutive_utc_hourly_candles(self) -> None:
        self.assertEqual(self.fixture.candles[0].timestamp.tzinfo, UTC)
        for previous, current in zip(self.fixture.candles, self.fixture.candles[1:]):
            self.assertEqual(current.timestamp - previous.timestamp, timedelta(hours=1))

    def test_observation_is_point_in_time_and_immutable(self) -> None:
        observation = self.harness.create_observation(self.fixture, self.spec)
        observation.validate_against_fixture(self.fixture)
        self.assertEqual(observation.entry_price, self.fixture.candles[10].close)
        with self.assertRaises((AttributeError, TypeError)):
            observation.signal = "SELL"  # type: ignore[misc]

    def test_future_timestamp_in_observation_context_is_rejected(self) -> None:
        future = self.signal_at + timedelta(hours=1)
        invalid_spec = ObservationSpec(
            emitted_at=self.signal_at,
            direction=SignalDirection.BUY,
            confidence=80.0,
            signal="FAVORABLE",
            context=(('future_value', 123.0),),
            context_timestamps=(('future_value', future),),
        )
        with self.assertRaisesRegex(ExperimentContractError, "Future leakage"):
            self.harness.create_observation(self.fixture, invalid_spec)

    def test_wrong_entry_price_is_rejected(self) -> None:
        observation = self.harness.create_observation(self.fixture, self.spec)
        tampered = observation.__class__(
            observation_id=observation.observation_id,
            fixture_id=observation.fixture_id,
            symbol=observation.symbol,
            emitted_at=observation.emitted_at,
            direction=observation.direction,
            signal=observation.signal,
            confidence=observation.confidence,
            entry_price=observation.entry_price + 1.0,
            context=observation.context,
            context_timestamps=observation.context_timestamps,
        )
        with self.assertRaises(ExperimentContractError):
            tampered.validate_against_fixture(self.fixture)

    def test_forward_outcomes_are_exactly_1h_4h_24h(self) -> None:
        observation = self.harness.create_observation(self.fixture, self.spec)
        outcomes = self.harness.forward_outcomes(self.fixture, observation)
        self.assertEqual([outcome.horizon for outcome in outcomes], ["1h", "4h", "24h"])
        for outcome in outcomes:
            self.assertGreater(outcome.as_of, outcome.observed_at)
            self.assertGreaterEqual(outcome.mfe_pct, 0.0)
            self.assertGreaterEqual(outcome.mae_pct, 0.0)

    def test_forward_outcomes_use_future_only_window(self) -> None:
        observation = self.harness.create_observation(self.fixture, self.spec)
        outcomes = self.harness.forward_outcomes(self.fixture, observation, horizons_hours=(1,))
        expected_timestamp = self.fixture.candles[11].timestamp
        self.assertEqual(outcomes[0].as_of, expected_timestamp)

    def test_sell_outcomes_are_direction_adjusted(self) -> None:
        sell_spec = ObservationSpec(
            emitted_at=self.signal_at,
            direction=SignalDirection.SELL,
            confidence=77.0,
            signal="UNFAVORABLE",
            context=(("market_state", "BEARISH"),),
            context_timestamps=(("market_state", self.signal_at),),
        )
        observation = self.harness.create_observation(self.fixture, sell_spec)
        outcomes = self.harness.forward_outcomes(self.fixture, observation, horizons_hours=(1,))
        expected = (observation.entry_price - self.fixture.candles[11].close) / observation.entry_price * 100.0
        self.assertAlmostEqual(outcomes[0].return_pct, expected, places=12)

    def test_replay_is_deterministic_and_comparable(self) -> None:
        specs = (self.spec,)
        first = self.harness.replay(self.fixture, specs)
        second = self.harness.replay(self.fixture, specs)
        comparison = self.harness.compare(first, second)
        self.assertTrue(comparison.matched)
        self.assertEqual(first, second)

    def test_replay_comparison_detects_changed_signal(self) -> None:
        expected = self.harness.replay(self.fixture, (self.spec,))
        altered = ObservationSpec(
            emitted_at=self.signal_at,
            direction=SignalDirection.SELL,
            confidence=self.spec.confidence,
            signal=self.spec.signal,
            context=self.spec.context,
            context_timestamps=self.spec.context_timestamps,
        )
        actual = self.harness.replay(self.fixture, (altered,))
        comparison = self.harness.compare(expected, actual)
        self.assertFalse(comparison.matched)
        self.assertTrue(comparison.mismatches)

    def test_harness_never_executes(self) -> None:
        self.assertFalse(self.harness.EXECUTION_ENABLED)
        with self.assertRaises(ExecutionDisabledError):
            self.harness.execute("BTCUSDT")

    def test_observation_ids_are_stable(self) -> None:
        first = self.harness.create_observation(self.fixture, self.spec)
        second = self.harness.create_observation(self.fixture, self.spec)
        self.assertEqual(first.observation_id, second.observation_id)

    def test_fixture_rejects_insufficient_forward_history(self) -> None:
        short_fixture = ExperimentFixture.generate(
            fixture_id="short",
            symbol="BTCUSDT",
            start_at=datetime(2025, 1, 1, tzinfo=UTC),
            seed=17,
            periods=25,
        )
        observation = self.harness.create_observation(
            short_fixture,
            ObservationSpec(
                emitted_at=short_fixture.candles[10].timestamp,
                direction=SignalDirection.BUY,
                confidence=50.0,
                signal="WAIT",
            ),
        )
        with self.assertRaises(ExperimentContractError):
            self.harness.forward_outcomes(short_fixture, observation)


if __name__ == "__main__":
    unittest.main()
