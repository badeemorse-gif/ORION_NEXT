from datetime import datetime, timedelta, timezone
from math import inf, nan
import unittest

from models.opportunity import (
    FreshnessStatus,
    Opportunity,
    OpportunityDirection,
    OpportunityRisk,
    OpportunityStatus,
    RiskState,
)
from models.trading_readiness import TradingReadiness


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


class TestTradingReadinessContract(unittest.TestCase):
    def _ready(self, **overrides) -> TradingReadiness:
        values = dict(
            intelligence_complete=True,
            confidence_acceptable=True,
            opportunity_fresh=True,
            risk_acceptable=True,
            market_conditions_valid=True,
        )
        values.update(overrides)
        return TradingReadiness(**values)

    def test_complete_valid_state_is_eligible(self) -> None:
        self.assertTrue(self._ready().eligible)

    def test_incomplete_intelligence_blocks_eligibility(self) -> None:
        self.assertFalse(self._ready(intelligence_complete=False).eligible)

    def test_low_confidence_blocks_eligibility(self) -> None:
        self.assertFalse(self._ready(confidence_acceptable=False).eligible)

    def test_stale_opportunity_blocks_eligibility(self) -> None:
        self.assertFalse(self._ready(opportunity_fresh=False).eligible)

    def test_unacceptable_risk_blocks_eligibility(self) -> None:
        self.assertFalse(self._ready(risk_acceptable=False).eligible)

    def test_invalid_market_conditions_block_eligibility(self) -> None:
        self.assertFalse(self._ready(market_conditions_valid=False).eligible)

    def test_non_boolean_gate_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._ready(intelligence_complete="true")

    def test_naive_evaluated_at_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._ready(evaluated_at=datetime(2026, 8, 11, 12, 0))


if __name__ == "__main__":
    unittest.main()
