import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from integration.paper_capital_runner_bridge import PaperRunnerCapitalBridge
from integration.trading_control import TradingState
from models.capital_management import AllocationConfig, CapitalMode
from models.market_event import MarketEvent, MarketEventType
from models.paper_capital import PaperLedger
from models.signal_snapshot import SignalSnapshot

from tools import orion_paper_8h_runner as runner_module


class _Log:
    def __init__(self):
        self.records = []

    def write(self, event_type, **payload):
        self.records.append((event_type, payload))


class _Source:
    def exchange_info(self):
        return {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "filters": [{"filterType": "NOTIONAL", "minNotional": "5"}],
                },
                {
                    "symbol": "ETHUSDT",
                    "filters": [{"filterType": "MIN_NOTIONAL", "minNotional": "3"}],
                },
            ]
        }


class _Opportunity:
    _metrics_source = _Source()


class TestPaperRunnerCapitalIntegration(unittest.TestCase):
    def test_fixed_mode_through_runner_boundary_does_not_compound(self):
        ledger = PaperLedger(starting_equity=50.0)
        bridge = PaperRunnerCapitalBridge(
            AllocationConfig(starting_capital=50.0, mode=CapitalMode.FIXED_ALLOCATION, allocation_rate=0.10),
            ledger,
        )
        audit = bridge.allocation_for(symbol="BTCUSDT", rank=1, opportunity_score=90.0, required_symbol_minimum=0.0)
        self.assertEqual(audit.final_order_notional, 5.0)
        bridge.bind_order(audit.allocation_id, "ORDER-1")
        ledger = ledger.record_fill(datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc), "BTCUSDT", "BUY", 1.0, 5.0)
        ledger = ledger.record_fill(datetime(2026, 8, 22, 11, 0, tzinfo=timezone.utc), "BTCUSDT", "SELL", 1.0, 5.5)
        bridge.ledger = ledger
        bridge.on_fill("ORDER-1")
        bridge.on_exit_symbol("BTCUSDT")
        bridge.ledger = ledger
        next_audit = bridge.allocation_for(symbol="ETHUSDT", rank=1, opportunity_score=90.0, required_symbol_minimum=0.0)
        self.assertEqual(next_audit.final_order_notional, 5.0)
        self.assertAlmostEqual(bridge.manager.total_equity, 50.5)

    def test_compounding_mode_through_runner_boundary_recalculates_from_realized_pnl(self):
        ledger = PaperLedger(starting_equity=50.0)
        ledger = ledger.record_fill(datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc), "BTCUSDT", "BUY", 1.0, 5.0)
        ledger = ledger.record_fill(datetime(2026, 8, 22, 11, 0, tzinfo=timezone.utc), "BTCUSDT", "SELL", 1.0, 6.0)
        bridge = PaperRunnerCapitalBridge(
            AllocationConfig(starting_capital=50.0, mode=CapitalMode.COMPOUNDING, allocation_rate=0.10),
            ledger,
        )
        audit = bridge.allocation_for(symbol="ETHUSDT", rank=1, opportunity_score=90.0, required_symbol_minimum=0.0)
        self.assertAlmostEqual(audit.final_order_notional, 5.1)
        ledger = ledger.mark(datetime(2026, 8, 22, 11, 1, tzinfo=timezone.utc), "ETHUSDT", 7.0)
        bridge.ledger = ledger
        self.assertAlmostEqual(bridge.manager.trading_capital, 51.0)
        self.assertAlmostEqual(bridge.manager.desired_allocation(), 5.1)

    def test_minimum_notional_is_symbol_specific_and_promotes_before_quantity(self):
        runner = runner_module.Paper8HRunner.__new__(runner_module.Paper8HRunner)
        runner.opportunity = _Opportunity()
        self.assertEqual(runner._required_symbol_minimum("BTCUSDT"), 5.0)
        self.assertEqual(runner._required_symbol_minimum("ETHUSDT"), 3.0)

    def test_multiple_default_reservations_are_possible_and_capital_is_authoritative(self):
        bridge = PaperRunnerCapitalBridge(
            AllocationConfig(starting_capital=50.0, mode=CapitalMode.FIXED_ALLOCATION, allocation_rate=0.10),
            PaperLedger(starting_equity=50.0),
        )
        first = bridge.allocation_for(symbol="BTCUSDT", rank=1, opportunity_score=100.0, required_symbol_minimum=5.0)
        second = bridge.allocation_for(symbol="ETHUSDT", rank=2, opportunity_score=90.0, required_symbol_minimum=5.0)
        self.assertTrue(first.accepted)
        self.assertTrue(second.accepted)
        self.assertEqual(bridge.pending_reserved, 10.0)
        self.assertEqual(bridge.manager.available_capital, 40.0)

    def test_configured_concurrency_limit_blocks_only_at_limit(self):
        bridge = PaperRunnerCapitalBridge(
            AllocationConfig(starting_capital=50.0, mode=CapitalMode.FIXED_ALLOCATION, allocation_rate=0.10, max_concurrent_positions=2),
            PaperLedger(starting_equity=50.0),
        )
        one = bridge.allocation_for(symbol="BTCUSDT", rank=1, opportunity_score=100.0, required_symbol_minimum=0.0)
        two = bridge.allocation_for(symbol="ETHUSDT", rank=2, opportunity_score=90.0, required_symbol_minimum=0.0)
        self.assertTrue(one.accepted)
        self.assertTrue(two.accepted)
        bridge.bind_order(one.allocation_id, "ORDER-1")
        bridge.bind_order(two.allocation_id, "ORDER-2")
        bridge.ledger = bridge.ledger.record_fill(datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc), "BTCUSDT", "BUY", 1.0, 5.0)
        bridge.ledger = bridge.ledger.record_fill(datetime(2026, 8, 22, 10, 1, tzinfo=timezone.utc), "ETHUSDT", "BUY", 1.0, 5.0)
        bridge.on_fill("ORDER-1")
        bridge.on_fill("ORDER-2")
        blocked = bridge.allocation_for(symbol="SOLUSDT", rank=3, opportunity_score=80.0, required_symbol_minimum=0.0)
        self.assertFalse(blocked.accepted)
        self.assertEqual(blocked.reason, "MAX_CONCURRENT_POSITIONS")

    def test_duplicate_symbol_protection_and_existing_position_survival(self):
        bridge = PaperRunnerCapitalBridge(
            AllocationConfig(starting_capital=50.0, mode=CapitalMode.FIXED_ALLOCATION, allocation_rate=0.10),
            PaperLedger(starting_equity=50.0),
        )
        allocation = bridge.allocation_for(symbol="BTCUSDT", rank=1, opportunity_score=100.0, required_symbol_minimum=0.0)
        bridge.bind_order(allocation.allocation_id, "ORDER-1")
        bridge.ledger = bridge.ledger.record_fill(datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc), "BTCUSDT", "BUY", 1.0, 5.0)
        bridge.on_fill("ORDER-1")
        bridge.sync_policy_positions()
        duplicate = bridge.allocation_for(symbol="BTCUSDT", rank=1, opportunity_score=110.0, required_symbol_minimum=0.0)
        self.assertFalse(duplicate.accepted)
        self.assertEqual(duplicate.reason, "DUPLICATE_ALLOCATION")
        self.assertEqual(bridge.manager.available_capital, 45.0)

    def test_paused_runner_boundary_blocks_reservation_but_existing_exit_remains_allowed(self):
        bridge = PaperRunnerCapitalBridge(
            AllocationConfig(starting_capital=50.0, mode=CapitalMode.FIXED_ALLOCATION, allocation_rate=0.10),
            PaperLedger(starting_equity=50.0),
        )
        runner = runner_module.Paper8HRunner.__new__(runner_module.Paper8HRunner)
        runner.supervisor = SimpleNamespace(
            trading_state=TradingState.PAUSED,
            last_processed_market_event=MarketEvent(
                event_id="E1",
                source_event_id="S1",
                symbol="BTCUSDT",
                event_type=MarketEventType.CANDLE_CLOSE,
                event_timestamp=datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc),
                payload={"price": 5.0},
            ),
        )
        runner.capital = bridge
        runner.log = _Log()
        runner.previous_signals = {}
        audit_snapshot = runner._allocation_snapshot(
            SimpleNamespace(symbol="BTCUSDT", rank=1, opportunity_score=100.0),
            {"decision": "BUY"},
            5.0,
            None,
        )
        self.assertEqual(audit_snapshot, (None, None))
        self.assertEqual(bridge.pending_reserved, 0.0)

    def test_recovery_reproduces_policy_state_without_duplicate_accounting_events(self):
        bridge = PaperRunnerCapitalBridge(
            AllocationConfig(starting_capital=50.0, mode=CapitalMode.COMPOUNDING, allocation_rate=0.10),
            PaperLedger(starting_equity=50.0),
        )
        allocation = bridge.allocation_for(symbol="BTCUSDT", rank=1, opportunity_score=100.0, required_symbol_minimum=0.0)
        bridge.bind_order(allocation.allocation_id, "ORDER-1")
        ledger = bridge.ledger.record_fill(datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc), "BTCUSDT", "BUY", 1.0, 5.0)
        bridge.ledger = ledger
        bridge.on_fill("ORDER-1")
        bridge.ledger = ledger.record_fill(datetime(2026, 8, 22, 11, 0, tzinfo=timezone.utc), "BTCUSDT", "SELL", 1.0, 6.0)
        bridge.on_exit_symbol("BTCUSDT")
        original = bridge.audit_state()
        recovered = bridge.recover(bridge.ledger)
        recovered_again = recovered.recover(bridge.ledger)
        self.assertEqual(original, recovered.audit_state())
        self.assertEqual(recovered.audit_state(), recovered_again.audit_state())
        self.assertEqual(len(bridge.ledger.events), len(recovered.ledger.events))

    def test_runner_contains_no_local_percentage_sizing(self):
        source = Path(runner_module.__file__).read_text(encoding="utf-8")
        self.assertNotIn("max_notional_pct", source)
        self.assertIn("PaperRunnerCapitalBridge", source)

    def test_runner_remains_paper_only(self):
        bridge = PaperRunnerCapitalBridge(
            AllocationConfig(starting_capital=50.0, mode=CapitalMode.FIXED_ALLOCATION, allocation_rate=0.10),
            PaperLedger(starting_equity=50.0),
        )
        self.assertEqual(bridge.manager.snapshot().starting_capital, 50.0)


if __name__ == "__main__":
    unittest.main()
