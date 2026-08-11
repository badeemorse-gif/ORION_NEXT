from datetime import datetime, timedelta, timezone
from math import inf, nan
import unittest

from models.explosive_watchlist import ExplosiveWatchCandidate, WatchlistStatus
from models.opportunity import (
    FreshnessStatus,
    Opportunity,
    OpportunityDirection,
    OpportunityRisk,
    OpportunityStatus,
    RiskState,
)


class TestOpportunityContract(unittest.TestCase):
    def _valid(self) -> Opportunity:
        return Opportunity(
            symbol="BTCUSDT",
            timeframe="5m",
            direction=OpportunityDirection.LONG,
            entry_candidate=100.0,
            confidence=82.0,
            setup_quality=78.0,
            risk=OpportunityRisk(
                state=RiskState.ACCEPTABLE,
                invalidation="Close below setup invalidation",
            ),
            expected_move=1.5,
            supporting_evidence=("trend alignment", "momentum confirmation"),
            market_context=("liquid", "active session"),
            freshness=FreshnessStatus.FRESH,
            status=OpportunityStatus.ACTIVE,
        )

    def test_valid_opportunity_is_complete_and_eligible(self) -> None:
        opportunity = self._valid()
        self.assertTrue(opportunity.is_complete)
        self.assertTrue(opportunity.is_eligible)
        self.assertFalse(opportunity.is_expired)

    def test_incomplete_intelligence_is_not_eligible(self) -> None:
        opportunity = Opportunity(
            symbol="BTCUSDT",
            timeframe="5m",
            direction=OpportunityDirection.LONG,
            status=OpportunityStatus.ACTIVE,
            freshness=FreshnessStatus.FRESH,
        )
        self.assertFalse(opportunity.is_complete)
        self.assertFalse(opportunity.is_eligible)

    def test_stale_opportunity_is_not_eligible(self) -> None:
        opportunity = Opportunity(
            symbol="BTCUSDT",
            timeframe="5m",
            direction=OpportunityDirection.LONG,
            entry_candidate=100.0,
            confidence=82.0,
            setup_quality=78.0,
            risk=OpportunityRisk(state=RiskState.ACCEPTABLE),
            supporting_evidence=("evidence",),
            freshness=FreshnessStatus.STALE,
            status=OpportunityStatus.ACTIVE,
        )
        self.assertTrue(opportunity.is_complete)
        self.assertFalse(opportunity.is_eligible)

    def test_invalid_confidence_and_nan_are_rejected(self) -> None:
        for value in (-1.0, 101.0, nan, inf, -inf):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    Opportunity(
                        symbol="BTCUSDT",
                        timeframe="5m",
                        direction=OpportunityDirection.LONG,
                        confidence=value,
                    )

    def test_expired_opportunity_is_not_eligible(self) -> None:
        now = datetime.now(timezone.utc)
        opportunity = Opportunity(
            symbol="BTCUSDT",
            timeframe="5m",
            direction=OpportunityDirection.LONG,
            entry_candidate=100.0,
            confidence=82.0,
            setup_quality=78.0,
            risk=OpportunityRisk(state=RiskState.ACCEPTABLE),
            supporting_evidence=("evidence",),
            freshness=FreshnessStatus.FRESH,
            status=OpportunityStatus.ACTIVE,
            generated_at=now - timedelta(minutes=2),
            expires_at=now - timedelta(minutes=1),
        )
        self.assertTrue(opportunity.is_expired)
        self.assertFalse(opportunity.is_eligible)


class TestExplosiveWatchlistContract(unittest.TestCase):
    def _valid(self) -> ExplosiveWatchCandidate:
        return ExplosiveWatchCandidate(
            symbol="ALTUSDT",
            timeframe_window="1h-12h",
            move_probability=72.0,
            readiness_score=81.0,
            confidence=74.0,
            freshness=FreshnessStatus.FRESH,
            supporting_signals=("compression", "volume expansion"),
            invalidation_conditions=("structure breakdown",),
            estimated_time_window="hours",
            status=WatchlistStatus.MONITOR,
        )

    def test_valid_candidate_is_monitorable(self) -> None:
        candidate = self._valid()
        self.assertTrue(candidate.is_complete)
        self.assertTrue(candidate.is_monitorable)

    def test_ineligible_candidate_is_not_monitorable(self) -> None:
        candidate = ExplosiveWatchCandidate(
            symbol="ALTUSDT",
            timeframe_window="1h-12h",
            freshness=FreshnessStatus.FRESH,
            status=WatchlistStatus.MONITOR,
        )
        self.assertFalse(candidate.is_complete)
        self.assertFalse(candidate.is_monitorable)

    def test_invalid_probability_is_rejected(self) -> None:
        for value in (-1.0, 101.0, nan, inf, -inf):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    ExplosiveWatchCandidate(
                        symbol="ALTUSDT",
                        timeframe_window="1h-12h",
                        move_probability=value,
                    )

    def test_stale_candidate_is_not_monitorable(self) -> None:
        candidate = ExplosiveWatchCandidate(
            symbol="ALTUSDT",
            timeframe_window="1h-12h",
            move_probability=72.0,
            readiness_score=81.0,
            confidence=74.0,
            freshness=FreshnessStatus.STALE,
            supporting_signals=("compression",),
            invalidation_conditions=("structure breakdown",),
            status=WatchlistStatus.MONITOR,
        )
        self.assertTrue(candidate.is_complete)
        self.assertFalse(candidate.is_monitorable)


if __name__ == "__main__":
    unittest.main()
