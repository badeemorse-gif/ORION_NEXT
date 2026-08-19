"""Contract tests for the experimental Signal Journal evidence boundary."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from models.signal_journal import (
    SignalFieldProvenance,
    SignalJournalEntry,
    SignalObservation,
    SignalOutcome,
)


class TestSignalJournalContract(unittest.TestCase):
    def setUp(self) -> None:
        self.signal_time = datetime(2026, 8, 17, 0, 0, tzinfo=timezone.utc)

    def _observation(self) -> SignalObservation:
        return SignalObservation(
            timestamp=self.signal_time,
            symbol="BTCUSDT",
            timeframe="1h",
            raw_score=72.5,
            confidence=0.81,
            decision="BUY",
            market_regime="TRENDING",
            volume=125000.0,
            relative_volume=1.8,
            volatility=0.024,
            relative_volatility=1.2,
            liquidity=950000.0,
            momentum=0.64,
            multi_timeframe_alignment="ALIGNED",
            reasons=("trend evidence", "volume evidence"),
        )

    def test_observation_contains_only_signal_time_fields(self) -> None:
        observation = self._observation()
        data = observation.to_dict()

        required = {
            "timestamp",
            "symbol",
            "timeframe",
            "raw_score",
            "confidence",
            "decision",
            "market_regime",
            "volume",
            "relative_volume",
            "volatility",
            "relative_volatility",
            "liquidity",
            "momentum",
            "multi_timeframe_alignment",
            "reasons",
        }
        self.assertEqual(set(data), required)
        self.assertNotIn("outcome_1h", data)
        self.assertNotIn("mfe", data)
        self.assertNotIn("outcome_timestamp", data)

    def test_field_provenance_is_explicit(self) -> None:
        provenance = SignalObservation.field_provenance()
        self.assertTrue(provenance)
        self.assertTrue(all(value is SignalFieldProvenance.SIGNAL_TIME_OBSERVED for value in provenance.values()))

        outcome_provenance = SignalOutcome.field_provenance()
        self.assertTrue(
            all(value is SignalFieldProvenance.RETROSPECTIVE_LABEL for value in outcome_provenance.values())
        )

    def test_retrospective_outcome_is_kept_separate_and_appendable(self) -> None:
        observation = self._observation()
        outcome = SignalOutcome(
            outcome_1h="POSITIVE",
            outcome_4h="POSITIVE",
            outcome_24h="NEUTRAL",
            mfe=2.7,
            mae=-0.9,
            metric_unit="percent",
            outcome_timestamp=self.signal_time + timedelta(hours=24),
        )
        entry = SignalJournalEntry(observation=observation, outcome=outcome)

        self.assertIs(entry.observation, observation)
        self.assertIs(entry.outcome, outcome)
        self.assertEqual(entry.to_dict()["observation"]["decision"], "BUY")
        self.assertEqual(entry.to_dict()["outcome"]["outcome_24h"], "NEUTRAL")

    def test_future_leakage_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SignalJournalEntry(
                observation=self._observation(),
                outcome=SignalOutcome(
                    outcome_1h="POSITIVE",
                    outcome_timestamp=self.signal_time - timedelta(seconds=1),
                ),
            )

    def test_mfe_mae_require_explicit_unit(self) -> None:
        with self.assertRaises(ValueError):
            SignalOutcome(mfe=1.0)
        with self.assertRaises(ValueError):
            SignalOutcome(mae=-1.0, metric_unit="")

    def test_timestamp_must_be_timezone_aware(self) -> None:
        with self.assertRaises(ValueError):
            SignalObservation(
                timestamp=datetime(2026, 8, 17, 0, 0),
                symbol="BTCUSDT",
                timeframe="1h",
            )

    def test_immutability_prevents_rewriting_signal_observation(self) -> None:
        observation = self._observation()
        with self.assertRaises((AttributeError, TypeError)):
            observation.decision = "SELL"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
