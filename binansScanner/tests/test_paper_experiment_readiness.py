import asyncio
import json
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from integration.paper_capital_runner_bridge import PaperRunnerCapitalBridge
from integration.paper_experiment import PaperABComparison, PaperExperimentConfig, PaperExperimentObservation, build_metrics
from integration.paper_realtime_lifecycle import PaperRealtimeLifecycle
from integration.paper_runtime_supervisor import PaperRuntimeSupervisor
from models.capital_management import AllocationConfig, CapitalMode
from models.paper_capital import PaperLedger
from tools.orion_paper_8h_runner import JsonlRunLog, Paper8HConfig, Paper8HRunner


class _FailingOpportunity:
    def __init__(self, error): self.error = error
    def discover(self): raise self.error


class TestPaperExperimentContract(unittest.TestCase):
    def test_reference_50_is_explicit_experiment_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = PaperExperimentConfig.reference_50(experiment_id="AB-50-001", output_dir=Path(tmp))
        self.assertEqual(config.starting_capital, 50.0)
        self.assertEqual(config.capital_mode, CapitalMode.FIXED_ALLOCATION)
        self.assertEqual(config.universe_mode, "dynamic")
        self.assertEqual(config.active_top_n, 10)
        self.assertEqual(config.broad_pool_size, 100)

    def test_config_rejects_invalid_experiment_shape(self):
        with self.assertRaises(ValueError):
            PaperExperimentConfig(experiment_id="x", starting_capital=50, capital_mode=CapitalMode.FIXED_ALLOCATION,
                                  allocation_rate=0.1, fixed_allocation=None, broad_pool_size=5, active_top_n=6,
                                  run_duration=timedelta(hours=1), universe_mode="dynamic", output_dir=Path("runs"))

    def test_metrics_are_semantic_and_deterministic(self):
        observation = PaperExperimentObservation(opportunity_evaluated=10, opportunity_accepted=4,
            entry_evaluated=4, entry_accepted=3, actionable_outcomes=2, false_negatives=1,
            strategy_rejections=3, capital_rejections=1, pause_rejections=2, duplicate_rejections=1,
            market_data_failures=2, recovery_count=3, duplicate_event_count=1,
            committed_capital_samples=(5.0, 10.0, 7.0), closed_trade_pnl=(2.0, -1.0, 3.0),
            hold_seconds=(60.0, 120.0, 180.0))
        account = {"starting_equity":50.0,"ending_equity":54.0,"realized_pnl":4.0,"unrealized_pnl":0.0,
                   "fees":0.1,"slippage":0.2,"maximum_drawdown":1.5,"fills":6}
        a = build_metrics(account=account, observation=observation)
        self.assertEqual(a, build_metrics(account=account, observation=observation))
        self.assertAlmostEqual(a.win_rate, 2/3); self.assertAlmostEqual(a.expectancy, 4/3)
        self.assertAlmostEqual(a.profit_factor, 5.0); self.assertAlmostEqual(a.capital_utilization, 0.2)
        self.assertAlmostEqual(a.average_hold_time, 120.0); self.assertAlmostEqual(a.opportunity_capture_rate, 0.4)
        self.assertAlmostEqual(a.entry_acceptance_rate, 0.75); self.assertAlmostEqual(a.false_negative_rate, 0.5)
        self.assertEqual(a.rejected_by_pause, 2); self.assertEqual(a.market_data_failures, 2)

    def test_ab_comparison_is_neutral_and_structurally_compatible(self):
        metrics = build_metrics(account={"starting_equity":50.0,"ending_equity":50.5,"realized_pnl":0.5,
            "unrealized_pnl":0.0,"fees":0.0,"slippage":0.0,"maximum_drawdown":0.0,"fills":2},
            observation=PaperExperimentObservation(closed_trade_pnl=(1.0,-0.5)))
        comparison = PaperABComparison(metrics, metrics)
        self.assertTrue(comparison.structurally_equal()); self.assertAlmostEqual(comparison.delta("ending_equity"), 0.0)


class TestPaperCapitalCrashWindows(unittest.TestCase):
    def _new_bridge(self, journal, ledger=None):
        return PaperRunnerCapitalBridge(AllocationConfig(starting_capital=50.0, mode=CapitalMode.FIXED_ALLOCATION,
            fixed_allocation=5.0), ledger or PaperLedger(starting_equity=50.0), journal_path=journal)

    def test_reserve_stop_recover_preserves_identity_and_releases_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal=Path(tmp)/"capital.jsonl"; live=self._new_bridge(journal)
            audit=live.allocation_for(symbol="BTCUSDT",rank=1,opportunity_score=90.0,required_symbol_minimum=0.0)
            self.assertTrue(audit.accepted); recovered=self._new_bridge(journal)
            self.assertEqual(recovered.pending_reserved,5.0); self.assertEqual(recovered._allocation_state[audit.allocation_id],"RESERVED")
            self.assertTrue(recovered.release(audit.allocation_id,reason="TEST_EXIT")); self.assertFalse(recovered.release(audit.allocation_id,reason="DUPLICATE"))
            self.assertEqual(recovered.audit_state()["reserved_capital"],0.0)
            events=[json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual([e["type"] for e in events],["RESERVE","RELEASE"]); self.assertEqual(recovered_again:=self._new_bridge(journal), self._new_bridge(journal))

    def test_reserve_bind_stop_recover_preserves_order_identity_and_releases_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal=Path(tmp)/"capital.jsonl"; live=self._new_bridge(journal)
            audit=live.allocation_for(symbol="ETHUSDT",rank=2,opportunity_score=80.0,required_symbol_minimum=0.0)
            live.bind_order(audit.allocation_id,"ENTRY-ORDER-1"); recovered=self._new_bridge(journal)
            self.assertEqual(recovered._allocation_state[audit.allocation_id],"BOUND"); self.assertEqual(recovered._allocation_to_order[audit.allocation_id],"ENTRY-ORDER-1")
            self.assertEqual(recovered._order_to_allocation["ENTRY-ORDER-1"],audit.allocation_id)
            self.assertTrue(recovered.release(audit.allocation_id,reason="TEST_EXIT")); self.assertFalse(recovered.release(audit.allocation_id,reason="DUPLICATE"))
            events=[json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual([e["type"] for e in events],["RESERVE","BIND","RELEASE"]); self.assertEqual(self._new_bridge(journal).audit_state(),recovered.audit_state())


class TestPaperRunnerNetworkFailureMatrix(unittest.TestCase):
    def _runner(self,tmp,error):
        config=Paper8HConfig(duration_hours=1.0,starting_capital=50.0,dynamic_universe=True,output_dir=Path(tmp),capital_mode=CapitalMode.FIXED_ALLOCATION,allocation_rate=0.10,top_n=2)
        runtime=PaperRealtimeLifecycle(ledger=PaperLedger(starting_equity=50.0)); supervisor=PaperRuntimeSupervisor(runtime=runtime)
        runner=Paper8HRunner(config=config,stream=object(),supervisor=supervisor,opportunity=_FailingOpportunity(error),log=JsonlRunLog(Path(tmp)/"events.jsonl")); runner.log.open(); return runner

    def _assert_fail_closed(self,error):
        async def run_case():
            with tempfile.TemporaryDirectory() as tmp:
                runner=self._runner(tmp,error)
                try:
                    await runner._run_signal_cycle(None); self.assertEqual(runner.capital.pending_reserved,0.0); self.assertEqual(runner.supervisor.active_orders,())
                    records=[json.loads(line) for line in Path(tmp,"events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
                    failure=next(r for r in records if r["event_type"]=="signal_cycle_failure"); self.assertTrue(failure["fail_closed"]); self.assertEqual(failure["rejection_reason"],"MARKET_DATA_FAILURE")
                finally: runner.log.close()
        asyncio.run(run_case())

    def test_dns_failure_fail_closed(self): self._assert_fail_closed(OSError("DNS resolution failed"))
    def test_timeout_fail_closed(self): self._assert_fail_closed(TimeoutError("market request timed out"))
    def test_market_data_failure_fail_closed(self): self._assert_fail_closed(RuntimeError("market data unavailable"))
    def test_decision_context_failure_fail_closed(self): self._assert_fail_closed(ValueError("decision context unavailable"))


if __name__ == "__main__": unittest.main()
