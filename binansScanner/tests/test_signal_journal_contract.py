"""Contract tests for the Phase A signal journal boundary."""
from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timedelta, timezone

from models.signal_journal import (
    OBSERVED_EVIDENCE,
    RETROSPECTIVE_LABEL,
    SignalJournal,
    SignalJournalEntry,
    SignalObservation,
    SignalOutcome,
)


class TestSignalJournalContract(unittest.TestCase):
    @staticmethod
    def _observation() -> SignalObservation:
        return SignalObservation(
            timestamp=datetime(2026, 8, 17, 0, 0, tzinfo=timezone.utc),
            symbol="BTCUSDT",
            timeframe="1h",
            raw_score=72.5,
            directional_raw_strength=81.0,
            context_score=68.0,
            composite=74.5,
            relative_rank=2.0,
            relative_percentile=96.0,
            confidence=0.84,
            decision="BUY",
            market_regime="TRENDING",
            volume=1250.0,
            relative_volume=1.7,
            volatility=0.021,
            relative_volatility=1.2,
            liquidity=0.91,
            momentum=0.68,
            multi_timeframe_alignment="1h/4h aligned",
            reasons=("trend aligned", "volume confirmed"),
        )

    def _entry(self) -> SignalJournalEntry:
        observation = self._observation()
        return SignalJournalEntry(
            observation=observation,
            outcome=SignalOutcome(
                outcome_1h=0.5,
                outcome_timestamp=observation.timestamp + timedelta(hours=1),
                metric_unit="percent",
            ),
        )

    def test_observation_schema_contains_only_signal_time_fields(self) -> None:
        names = {field.name for field in fields(SignalObservation)}
        self.assertEqual(
            names,
            {
                "timestamp",
                "symbol",
                "timeframe",
                "raw_score",
                "directional_raw_strength",
                "context_score",
                "composite",
                "relative_rank",
                "relative_percentile",
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
            },
        )
        self.assertNotIn("outcome_1h", names)
        self.assertNotIn("mfe", names)
        self.assertNotIn("mae", names)
        self.assertEqual(set(SignalObservation.field_provenance().values()), {OBSERVED_EVIDENCE})

    def test_relative_rank_and_percentile_are_signal_time_evidence(self) -> None:
        observation = self._observation()
        self.assertEqual(observation.relative_rank, 2.0)
        self.assertEqual(observation.relative_percentile, 96.0)
        self.assertEqual(observation.field_provenance()["relative_rank"], OBSERVED_EVIDENCE)
        self.assertEqual(observation.field_provenance()["relative_percentile"], OBSERVED_EVIDENCE)

    def test_observation_is_immutable(self) -> None:
        observation = self._observation()
        with self.assertRaises(FrozenInstanceError):
            observation.raw_score = 80.0  # type: ignore[misc]

    def test_observation_timestamp_must_be_timezone_aware(self) -> None:
        with self.assertRaises(ValueError):
            SignalObservation(
                timestamp=datetime(2026, 8, 17, 0, 0),
                symbol="BTCUSDT",
                timeframe="1h",
                raw_score=1.0,
                directional_raw_strength=1.0,
                context_score=1.0,
                composite=1.0,
                relative_rank=None,
                relative_percentile=None,
                confidence=0.5,
                decision="WAIT",
                market_regime="NEUTRAL",
            )

    def test_relative_percentile_is_bounded(self) -> None:
        with self.assertRaises(ValueError):
            SignalObservation(
                timestamp=datetime(2026, 8, 17, 0, 0, tzinfo=timezone.utc),
                symbol="BTCUSDT",
                timeframe="1h",
                raw_score=1.0,
                directional_raw_strength=1.0,
                context_score=1.0,
                composite=1.0,
                relative_rank=1.0,
                relative_percentile=101.0,
                confidence=0.5,
                decision="WAIT",
                market_regime="NEUTRAL",
            )

    def test_outcome_is_retrospective_and_has_its_own_provenance(self) -> None:
        outcome = SignalOutcome(
            outcome_1h=0.8,
            outcome_4h=1.4,
            outcome_24h=2.1,
            mfe=2.8,
            mae=-0.7,
            outcome_timestamp=datetime(2026, 8, 18, 0, 0, tzinfo=timezone.utc),
            metric_unit="percent",
        )
        self.assertTrue(all(value == RETROSPECTIVE_LABEL for value in SignalOutcome.field_provenance().values()))
        self.assertEqual(outcome.metric_unit, "percent")
        with self.assertRaises(FrozenInstanceError):
            outcome.outcome_1h = 1.0  # type: ignore[misc]

    def test_mfe_mae_require_explicit_metric_unit(self) -> None:
        with self.assertRaises(ValueError):
            SignalOutcome(mfe=1.0)
        with self.assertRaises(ValueError):
            SignalOutcome(mae=-1.0)

    def test_journal_keeps_observation_and_outcome_separate(self) -> None:
        entry = self._entry()
        payload = entry.to_dict()
        self.assertIs(entry.observation, entry.observation)
        self.assertIs(entry.outcome, entry.outcome)
        self.assertNotIn("outcome_1h", payload["observation"])
        self.assertEqual(payload["outcome"]["outcome_1h"], 0.5)
        self.assertEqual(payload["outcome"]["metric_unit"], "percent")

    def test_future_leakage_boundary_rejects_outcome_before_signal(self) -> None:
        observation = self._observation()
        with self.assertRaises(ValueError):
            SignalJournalEntry(
                observation=observation,
                outcome=SignalOutcome(
                    outcome_1h=0.5,
                    outcome_timestamp=observation.timestamp - timedelta(minutes=1),
                    metric_unit="percent",
                ),
            )

    def test_entry_provenance_is_auditable(self) -> None:
        provenance = SignalJournalEntry.field_provenance()
        self.assertEqual(provenance["observation.raw_score"], OBSERVED_EVIDENCE)
        self.assertEqual(provenance["observation.directional_raw_strength"], OBSERVED_EVIDENCE)
        self.assertEqual(provenance["observation.composite"], OBSERVED_EVIDENCE)
        self.assertEqual(provenance["observation.relative_percentile"], OBSERVED_EVIDENCE)
        self.assertEqual(provenance["outcome.outcome_24h"], RETROSPECTIVE_LABEL)
        self.assertEqual(provenance["outcome.mfe"], RETROSPECTIVE_LABEL)
        self.assertEqual(provenance["outcome.metric_unit"], RETROSPECTIVE_LABEL)

    def test_signal_journal_is_immutable_and_append_only(self) -> None:
        journal = SignalJournal()
        entry = self._entry()
        updated = journal.record(entry)
        self.assertEqual(len(journal), 0)
        self.assertEqual(len(updated), 1)
        self.assertIs(updated.entries[0], entry)
        with self.assertRaises(FrozenInstanceError):
            updated.entries = ()  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
