import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from enum import Enum

from models.signal_journal import SignalJournalEntry, SignalObservation, SignalOutcome
from models.d5_signal_outcome_adapter import D5D6SignalOutcomeAdapter


class Direction(Enum):
    BUY = "BUY"
    FLAT = "FLAT"


class D5Observation:
    def __init__(self):
        self.observation_id = "obs-001"
        self.emitted_at = datetime(2026, 8, 19, 10, 0, tzinfo=timezone(timedelta(hours=3)))
        self.symbol = "BTCUSDT"
        self.direction = Direction.BUY
        self.confidence = 82.5
        self.context = (("score", 72.0), ("market_state", "BULLISH"))


class D5ForwardOutcome:
    def __init__(self, horizon, as_of, return_pct, mfe_pct, mae_pct):
        self.horizon = horizon
        self.as_of = as_of
        self.return_pct = return_pct
        self.mfe_pct = mfe_pct
        self.mae_pct = mae_pct


class TestCanonicalSignalOutcomeHandoff(unittest.TestCase):
    def setUp(self):
        self.d5 = D5Observation()
        self.adapter = D5D6SignalOutcomeAdapter()

    def outcomes(self):
        base = datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc)
        return (
            D5ForwardOutcome("1h", base + timedelta(hours=1), 1.1, 2.0, 0.8),
            D5ForwardOutcome("4h", base + timedelta(hours=4), 2.2, 3.5, 1.4),
            D5ForwardOutcome("24h", base + timedelta(hours=24), 4.4, 7.0, 2.9),
        )

    def test_observation_id_is_canonical_and_immutable(self):
        observation = self.adapter.observation(self.d5, timeframe="1h")
        self.assertEqual(observation.observation_id, "obs-001")
        with self.assertRaises(FrozenInstanceError):
            observation.observation_id = "other"  # type: ignore[misc]

    def test_observation_timestamp_is_utc_normalized(self):
        observation = self.adapter.observation(self.d5, timeframe="1h")
        self.assertEqual(observation.timestamp.tzinfo, timezone.utc)
        self.assertEqual(observation.timestamp, datetime(2026, 8, 19, 7, 0, tzinfo=timezone.utc))

    def test_outcome_mapping_and_canonical_aggregates(self):
        outcome = self.adapter.outcome(self.d5, self.outcomes())
        self.assertEqual(outcome.outcome_1h, 1.1)
        self.assertEqual(outcome.outcome_4h, 2.2)
        self.assertEqual(outcome.outcome_24h, 4.4)
        self.assertEqual(outcome.mfe, 7.0)
        self.assertEqual(outcome.mae, 2.9)
        self.assertEqual(outcome.metric_unit, "percent")
        self.assertEqual(outcome.outcome_timestamp, datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc))

    def test_strict_outcome_chronology(self):
        observation = self.adapter.observation(self.d5, timeframe="1h")
        outcome = self.adapter.outcome(self.d5, self.outcomes())
        entry = SignalJournalEntry(observation=observation, outcome=outcome)
        self.assertGreater(entry.outcome.outcome_timestamp, entry.observation.timestamp)

    def test_equal_timestamp_is_rejected(self):
        observation = SignalObservation(
            observation_id="obs-001",
            timestamp=datetime(2026, 8, 19, 7, 0, tzinfo=timezone.utc),
            symbol="BTCUSDT",
            timeframe="1h",
            raw_score=72.0,
            confidence=82.5,
            decision="BUY",
            market_regime="BULLISH",
        )
        outcome = SignalOutcome(
            outcome_1h=1.0,
            outcome_timestamp=observation.timestamp,
        )
        with self.assertRaises(ValueError):
            SignalJournalEntry(observation=observation, outcome=outcome)

    def test_d5_outcome_without_required_horizon_is_rejected(self):
        with self.assertRaises(ValueError):
            self.adapter.outcome(self.d5, self.outcomes()[:2])


if __name__ == "__main__":
    unittest.main()
