from datetime import datetime, timedelta, timezone
from math import inf, nan
import unittest

from models.opportunity import (
    Opportunity,
    OpportunityDirection,
    OpportunityRisk,
    OpportunityStatus,
)
from models.trading_readiness import TradingReadiness
from models.watchlist import ExplosiveWatchCandidate, WatchlistStatus


UTC = timezone.utc


class TestFutureTradingOpportunityContract(unittest.TestCase):
    def _opportunity(self, **overrides):
        now = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
        values = dict(
            symbol="BTCUSDT",
            timeframe="5m",
            direction=OpportunityDirection.LONG,
            confidence=82.0,
            setup_quality=78.0,
            risk=OpportunityRisk.MEDIUM,
            entry_candidate=100.0,
            invalidation=98.0,
            expected_move=1.5,
            supporting_evidence=("trend aligned",),
            market_context=("liquid",),
            observed_at=now,
            expires_at=now + timedelta(minutes=15),
            status=OpportunityStatus.ACTIVE,
        )
        values.update(overrides)
        return Opportunity(**values)

    def test_valid_opportunity(self):
        opportunity = self._opportunity()
        self.assertEqual(opportunity.symbol, "BTCUSDT")
        self.assertTrue(opportunity.is_fresh(at=datetime(2026, 8, 11, 12, 5, tzinfo=UTC)))

    def test_incomplete_optional_intelligence_remains_explicit(self):
        opportunity = self._opportunity(entry_candidate=None, invalidation=None, expected_move=None)
        self.assertIsNone(opportunity.entry_candidate)
        self.assertIsNone(opportunity.invalidation)
        self.assertIsNone(opportunity.expected_move)

    def test_invalid_confidence_is_rejected(self):
        with self.assertRaises(ValueError):
            self._opportunity(confidence=101.0)

    def test_non_finite_confidence_is_rejected(self):
        for value in (nan, inf, -inf):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self._opportunity(confidence=value)

    def test_stale_opportunity_is_not_fresh(self):
        now = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
        opportunity = self._opportunity(observed_at=now, expires_at=now + timedelta(minutes=1))
        self.assertFalse(opportunity.is_fresh(at=now + timedelta(minutes=1)))

    def test_explicit_expired_status_is_not_fresh(self):
        opportunity = self._opportunity(status=OpportunityStatus.EXPIRED)
        self.assertFalse(opportunity.is_fresh())


class TestExplosiveWatchlistContract(unittest.TestCase):
    def _candidate(self, **overrides):
        now = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
        values = dict(
            symbol="XYZUSDT",
            timeframe="1h",
            strong_move_probability=0.72,
            readiness_score=81.0,
            confidence=76.0,
            supporting_signals=("compression", "volume expansion risk"),
            invalidation_conditions=("structure breakdown",),
            window_start=now,
            window_end=now + timedelta(hours=8),
            observed_at=now,
        )
        values.update(overrides)
        return ExplosiveWatchCandidate(**values)

    def test_probabilistic_candidate_is_valid(self):
        candidate = self._candidate()
        self.assertEqual(candidate.estimate_kind.value, "PROBABILISTIC")
        self.assertTrue(candidate.is_fresh(at=datetime(2026, 8, 11, 15, 0, tzinfo=UTC)))

    def test_invalid_probability_is_rejected(self):
        with self.assertRaises(ValueError):
            self._candidate(strong_move_probability=1.01)

    def test_non_finite_probability_is_rejected(self):
        with self.assertRaises(ValueError):
            self._candidate(strong_move_probability=nan)

    def test_stale_candidate_is_not_fresh(self):
        now = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
        candidate = self._candidate(window_start=now, window_end=now + timedelta(hours=1))
        self.assertFalse(candidate.is_fresh(at=now + timedelta(hours=1)))

    def test_rejected_candidate_is_not_fresh(self):
        candidate = self._candidate(status=WatchlistStatus.REJECTED)
        self.assertFalse(candidate.is_fresh())


class TestTradingReadinessContract(unittest.TestCase):
    def test_complete_valid_state_is_eligible(self):
        readiness = TradingReadiness(True, True, True, True, True)
        self.assertTrue(readiness.eligible)

    def test_incomplete_intelligence_blocks_eligibility(self):
        readiness = TradingReadiness(False, True, True, True, True, reasons=("missing intelligence",))
        self.assertFalse(readiness.eligible)

    def test_stale_opportunity_blocks_eligibility(self):
        readiness = TradingReadiness(True, True, False, True, True)
        self.assertFalse(readiness.eligible)

    def test_unacceptable_risk_blocks_eligibility(self):
        readiness = TradingReadiness(True, True, True, False, True)
        self.assertFalse(readiness.eligible)

    def test_invalid_market_conditions_block_eligibility(self):
        readiness = TradingReadiness(True, True, True, True, False)
        self.assertFalse(readiness.eligible)


if __name__ == "__main__":
    unittest.main()
