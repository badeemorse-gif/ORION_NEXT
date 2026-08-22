"""Official ORION paper runtime runner with D1 dynamic opportunities and D6 capital allocation."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BINANS_SCANNER = _REPO_ROOT / "binansScanner"
if str(_BINANS_SCANNER) not in sys.path:
    sys.path.insert(0, str(_BINANS_SCANNER))

from decision_engine import evaluate_decision
from engines.indicator_engine import IndicatorEngine
from engines.profile_engine import ProfileEngine
from enums import Timeframe
from integration.paper_capital_runner_bridge import PaperRunnerCapitalBridge
from integration.paper_realtime_lifecycle import PaperRealtimeLifecycle
from integration.paper_runtime_supervisor import PaperRuntimeSupervisor
from integration.trading_control import TradingState
from models.capital_management import AllocationConfig, CapitalMode
from models.market_event import MarketEvent, MarketEventType
from models.opportunity import OpportunityCandidate
from models.paper_capital import PaperLedger
from models.signal_snapshot import MaterialChangePolicy, SignalIdentity, SignalSnapshot, build_next_snapshot
from providers.binance_mapper import BinanceMapper
from providers.binance_opportunity_source import BinanceSpotOpportunitySource
from providers.market_stream import BinanceWebSocketMarketStream, MarketStreamRunner
from services.opportunity_discovery import MarketUniverseDiscovery, OpportunityConfig, OpportunityDiscovery

UTC = timezone.utc


class CanonicalDecisionContextProvider:
    _PROFILE_TIMEFRAMES = (("1h", Timeframe.H1), ("4h", Timeframe.H4), ("1d", Timeframe.D1))

    def __init__(self) -> None:
        self._mapper = BinanceMapper()
        self._indicator_engine = IndicatorEngine()
        self._profile_engine = ProfileEngine()
        self._cache: dict[str, Mapping[str, Any]] = {}

    def build(self, symbol: str) -> Mapping[str, Any]:
        symbol = symbol.upper()
        if symbol in self._cache:
            return self._cache[symbol]
        import urllib.request
        from urllib.parse import urlencode
        frames: dict[Timeframe, Any] = {}
        for interval, timeframe in self._PROFILE_TIMEFRAMES:
            request = urllib.request.Request(
                f"https://api.binance.com/api/v3/klines?{urlencode({'symbol': symbol, 'interval': interval, 'limit': '250'})}",
                headers={"User-Agent": "ORION-paper-runner/1.0"},
                method="GET",
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, list) or not payload:
                raise RuntimeError(f"No canonical profile data for {symbol} {interval}")
            frames[timeframe] = self._mapper.convert_klines_to_dataframe(payload)
        dataset = self._mapper.create_market_dataset(symbol=symbol, timeframe_data=frames, source="BINANCE_PUBLIC_PROFILE")
        profile = self._profile_engine.build_profile(self._indicator_engine.calculate_dataset(dataset))
        context = {"health_score": float(profile.statistics.health_score), "trade_mode": "FULL_ANALYSIS" if profile.is_tradeable else "NEW_LISTING"}
        self._cache[symbol] = context
        return context


def canonical_decision(candidate: OpportunityCandidate, context: Mapping[str, Any]) -> Mapping[str, Any]:
    return evaluate_decision({"score": float(candidate.opportunity_score)}, dict(context))


class FixedUniverseSource:
    def __init__(self, source: BinanceSpotOpportunitySource, symbols: tuple[str, ...]) -> None:
        self._source = source
        self._symbols = frozenset(s.upper() for s in symbols)

    def exchange_info(self) -> Mapping[str, Any]:
        payload = self._source.exchange_info()
        return {"symbols": [row for row in payload.get("symbols", []) if str(row.get("symbol", "")).upper() in self._symbols]}

    def metrics_bulk(self, symbols: Any) -> Mapping[str, Any]:
        return self._source.metrics_bulk(tuple(s for s in symbols if str(s).upper() in self._symbols))


class DynamicMarketStream:
    def __init__(self, symbols: tuple[str, ...]) -> None:
        self._symbols = tuple(sorted(set(symbols)))
        self._inner = BinanceWebSocketMarketStream(self._symbols, [Timeframe.M1])

    @property
    def symbols(self) -> tuple[str, ...]:
        return self._symbols

    def set_symbols(self, symbols: tuple[str, ...]) -> bool:
        normalized = tuple(sorted(set(s.upper() for s in symbols if s)))
        if not normalized or normalized == self._symbols:
            return False
        self._symbols = normalized
        self._inner = BinanceWebSocketMarketStream(self._symbols, [Timeframe.M1])
        return True

    async def connect(self) -> None:
        await self._inner.connect()

    def events(self):
        return self._inner.events()

    async def close(self) -> None:
        await self._inner.close()


@dataclass(frozen=True, slots=True)
class Paper8HConfig:
    duration_hours: float = 8.0
    starting_capital: float = 200.0
    symbols: tuple[str, ...] = ()
    dynamic_universe: bool = True
    output_dir: Path = Path("runs/paper")
    capital_mode: CapitalMode = CapitalMode.FIXED_ALLOCATION
    allocation_rate: Optional[float] = 0.10
    fixed_allocation: Optional[float] = None
    max_concurrent_positions: Optional[int] = None
    top_n: int = 10
    metrics_ttl_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.duration_hours <= 0 or self.starting_capital <= 0:
            raise ValueError("duration and starting capital must be positive")
        if self.dynamic_universe and self.symbols:
            raise ValueError("dynamic universe cannot carry a fixed symbol override")
        if not self.dynamic_universe and not self.symbols:
            raise ValueError("fixed universe override requires symbols")
        if self.top_n <= 0 or self.metrics_ttl_seconds < 0:
            raise ValueError("invalid runner configuration")
        AllocationConfig(starting_capital=self.starting_capital, mode=self.capital_mode, allocation_rate=self.allocation_rate, fixed_allocation=self.fixed_allocation, max_concurrent_positions=self.max_concurrent_positions)


@dataclass(slots=True)
class JsonlRunLog:
    path: Path
    _handle: Any = field(default=None, init=False, repr=False)

    def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a", encoding="utf-8")

    def write(self, record_type: str, **payload: Any) -> None:
        if self._handle is None:
            raise RuntimeError("run log is not open")
        self._handle.write(json.dumps({"timestamp": datetime.now(UTC).isoformat(), "event_type": record_type, **payload}, sort_keys=True, default=str) + "\n")
        self._handle.flush()

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None


@dataclass(slots=True)
class Paper8HRunner:
    config: Paper8HConfig
    stream: Any
    supervisor: PaperRuntimeSupervisor
    opportunity: OpportunityDiscovery
    log: JsonlRunLog
    decision_context: Any = field(default_factory=CanonicalDecisionContextProvider)
    previous_signals: dict[str, SignalSnapshot] = field(default_factory=dict)
    previous_top_symbols: tuple[str, ...] = ()
    last_prices: dict[str, float] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    runtime_failure: Optional[str] = None
    peak_equity: float = 0.0
    maximum_drawdown: float = 0.0
    capital: Optional[PaperRunnerCapitalBridge] = None

    def __post_init__(self) -> None:
        if self.capital is None:
            self.capital = PaperRunnerCapitalBridge(
                AllocationConfig(
                    starting_capital=self.config.starting_capital,
                    mode=self.config.capital_mode,
                    allocation_rate=self.config.allocation_rate,
                    fixed_allocation=self.config.fixed_allocation,
                    max_concurrent_positions=self.config.max_concurrent_positions,
                ),
                self.supervisor.runtime.ledger,
                journal_path=self.config.output_dir / "capital_allocations.jsonl",
            )

    @classmethod
    def create(cls, config: Paper8HConfig) -> "Paper8HRunner":
        source = BinanceSpotOpportunitySource(ttl_seconds=config.metrics_ttl_seconds)
        universe_source: Any = source if config.dynamic_universe else FixedUniverseSource(source, config.symbols)
        d1 = OpportunityConfig(default_top_n=config.top_n, refresh_interval_seconds=config.metrics_ttl_seconds, cache_ttl_seconds=config.metrics_ttl_seconds)
        opportunity = OpportunityDiscovery(MarketUniverseDiscovery(universe_source, d1), source, d1)
        opportunity.market_provider = source
        initial = opportunity.discover(config.top_n)
        symbols = initial.symbols()
        if not symbols:
            raise RuntimeError("D1 returned no eligible Top-N opportunities")
        runtime = PaperRealtimeLifecycle(ledger=PaperLedger(starting_equity=config.starting_capital))
        return cls(config, DynamicMarketStream(symbols), PaperRuntimeSupervisor(runtime=runtime), opportunity, JsonlRunLog(config.output_dir / "events.jsonl"), peak_equity=config.starting_capital)

    async def run(self) -> dict[str, Any]:
        self.started_at = datetime.now(UTC)
        self.log.open()
        assert self.capital is not None
        self.log.write("run_start", duration_hours=self.config.duration_hours, starting_equity=self.config.starting_capital, capital_mode=self.config.capital_mode.value, allocation_rate=self.config.allocation_rate, fixed_allocation=self.config.fixed_allocation, max_concurrent_positions=self.config.max_concurrent_positions, universe="dynamic" if self.config.dynamic_universe else "fixed_override", top_n=self.config.top_n, symbols=self.previous_top_symbols, paper_only=True, live_execution=False, credentials_used=False, exchange_orders=False)
        runner = MarketStreamRunner(self.stream, on_event=self._on_market_event)
        stream_task = asyncio.create_task(runner.run())
        timer_task = asyncio.create_task(asyncio.sleep(self.config.duration_hours * 3600.0))
        try:
            done, _ = await asyncio.wait({stream_task, timer_task}, return_when=asyncio.FIRST_COMPLETED)
            if stream_task in done:
                timer_task.cancel()
                with suppress(asyncio.CancelledError):
                    await timer_task
                stream_task.result()
            else:
                runner.stop()
                await self.stream.close()
                await stream_task
        except Exception as exc:
            self.runtime_failure = f"{type(exc).__name__}: {exc}"
            self.log.write("runtime_failure", error=self.runtime_failure)
            raise
        finally:
            runner.stop()
            await self.stream.close()
            self.finished_at = datetime.now(UTC)
            report = self._finalize(runner)
            self.log.write("run_end", **report)
            self.log.close()
        return report

    async def _on_market_event(self, event: MarketEvent) -> None:
        if "price" in event.payload:
            self.last_prices[event.symbol] = float(event.payload["price"])
        try:
            filled = self.supervisor.process_market_event(event)
        except Exception as exc:
            self.runtime_failure = f"{type(exc).__name__}: {exc}"
            self.log.write("runtime_failure", event_id=event.event_id, error=self.runtime_failure)
            raise
        assert self.capital is not None
        self.capital.ledger = self.supervisor.runtime.ledger
        for order_id in filled:
            allocation_id = self.capital.on_fill(order_id)
            self.log.write("fill", order_id=order_id, symbol=event.symbol, price=event.payload.get("price"), allocation_id=allocation_id, capital_state=self.capital.audit_state())
        self.capital.reconcile_terminal_orders(self.supervisor.runtime.orders)
        state = self._account_state()
        equity = self._marked_equity(state)
        self.peak_equity = max(self.peak_equity, equity)
        self.maximum_drawdown = max(self.maximum_drawdown, self.peak_equity - equity)
        health = self.supervisor.health
        self.log.write("market_event", event_id=event.event_id, source_event_id=event.source_event_id, symbol=event.symbol, market_event_type=event.event_type.value, price=event.payload.get("price"), filled=filled, active_orders=len(self.supervisor.active_orders), active_positions=len(self.supervisor.active_positions), equity=equity, drawdown=max(self.peak_equity - equity, 0.0), health=health.healthy)
        if event.event_type is MarketEventType.CANDLE_CLOSE:
            await self._run_signal_cycle(event)

    @staticmethod
    def _symbol_minimum(exchange_info: Mapping[str, Any], symbol: str) -> float:
        for row in exchange_info.get("symbols", []):
            if str(row.get("symbol", "")).upper() != symbol.upper():
                continue
            minimums = [float(rule["minNotional"]) for rule in row.get("filters", []) if rule.get("filterType") in {"MIN_NOTIONAL", "NOTIONAL"} and rule.get("minNotional") is not None]
            return max(minimums, default=0.0)
        return 0.0

    def _required_symbol_minimum(self, symbol: str) -> float:
        source = getattr(self.opportunity, "market_provider", getattr(self.opportunity, "_metrics_source", None))
        return self._symbol_minimum(source.exchange_info(), symbol) if source is not None and hasattr(source, "exchange_info") else 0.0

    @property
    def _current_event_time(self) -> datetime:
        event = self.supervisor.last_processed_market_event
        return event.event_timestamp if event is not None else datetime.now(UTC)

    def _allocation_snapshot(self, candidate: OpportunityCandidate, decision: Mapping[str, Any], price: float, previous: Optional[SignalSnapshot]):
        assert self.capital is not None
        if self.supervisor.trading_state is not TradingState.RUNNING:
            self.log.write("allocation_blocked", symbol=candidate.symbol, reason="PAUSED", trading_state=self.supervisor.trading_state.value)
            return None, None
        audit = self.capital.allocation_for(symbol=candidate.symbol, rank=candidate.rank, opportunity_score=float(candidate.opportunity_score), required_symbol_minimum=self._required_symbol_minimum(candidate.symbol))
        self.log.write("capital_allocation", allocation_id=audit.allocation_id, symbol=audit.symbol, intent=audit.intent, desired_allocation=audit.desired_allocation, required_symbol_minimum=audit.required_symbol_minimum, final_order_notional=audit.final_order_notional, capital_mode=audit.capital_mode.value, available_capital_before=audit.available_capital_before, available_capital_after=self.capital.manager.available_capital, reserved_capital_before=audit.reserved_capital_before, reserved_capital_after=self.capital.manager.reserved_capital, committed_capital=self.capital.manager.committed_capital, minimum_adjustment_applied=audit.minimum_adjustment_applied, accepted=audit.accepted, rejection_reason=audit.rejection_reason.value if audit.rejection_reason else None)
        if not audit.accepted:
            return None, audit
        quantity = audit.final_order_notional / price
        snapshot = build_next_snapshot(previous=previous, identity=SignalIdentity(candidate.symbol, "D1_D3_PAPER", "ENTRY"), direction="BUY", decision=decision["decision"], confidence=float(candidate.opportunity_score), entry_plan={"entry_price": price, "quantity": quantity, "allocation_id": audit.allocation_id, "final_order_notional": audit.final_order_notional}, generated_at=self._current_event_time, valid_until=self._current_event_time + timedelta(minutes=15), policy=MaterialChangePolicy(entry_price_change_pct=0.10), market_context_fingerprint=f"d1:{candidate.symbol}:{candidate.rank}:{candidate.opportunity_score:.8f}", quality=float(candidate.opportunity_score)).current
        return snapshot, audit

    async def _run_signal_cycle(self, event: MarketEvent) -> None:
        assert self.capital is not None
        try:
            opportunities = await asyncio.to_thread(self.opportunity.discover, self.config.top_n)
        except Exception as exc:
            self.log.write("signal_cycle_failure", error=f"{type(exc).__name__}: {exc}")
            return
        selected = opportunities.symbols()
        added = tuple(s for s in selected if s not in self.previous_top_symbols)
        removed = tuple(s for s in self.previous_top_symbols if s not in selected)
        if added or removed or selected != self.previous_top_symbols:
            self.log.write("opportunity_refresh", universe_snapshot_size="dynamic", eligible_candidate_count=len(opportunities.candidates), top_n_symbols=selected, scores={c.symbol: c.opportunity_score for c in opportunities.candidates}, directional_evidence={c.symbol: c.directional_evidence for c in opportunities.candidates}, refresh_timestamp=event.event_timestamp.isoformat(), candidate_additions=added, candidate_removals=removed)
            if isinstance(self.stream, DynamicMarketStream) and self.stream.set_symbols(selected):
                self.log.write("market_stream_resubscribe", symbols=selected)
            self.previous_top_symbols = selected
        self.capital.ledger = self.supervisor.runtime.ledger
        self.capital.sync_policy_positions()
        for candidate in opportunities.candidates:
            try:
                context = await asyncio.to_thread(self.decision_context.build, candidate.symbol)
                decision = canonical_decision(candidate, context)
            except Exception as exc:
                self.log.write("decision_context_failure", symbol=candidate.symbol, error=f"{type(exc).__name__}: {exc}", fail_closed=True)
                continue
            price = self.last_prices.get(candidate.symbol)
            if price is None or price <= 0:
                continue
            active_position = self.supervisor.runtime.positions.active_for_symbol(candidate.symbol)
            previous = self.previous_signals.get(candidate.symbol)
            if active_position is not None and decision["decision"] != "BUY":
                exit_order_id = self.supervisor.runtime.exit_position(symbol=candidate.symbol, price=price, now=event.event_timestamp)
                self.capital.ledger = self.supervisor.runtime.ledger
                self.capital.on_exit_symbol(candidate.symbol)
                self.log.write("signal_event", symbol=candidate.symbol, direction="SELL", decision=decision["decision"], exit_trigger="DECISION_NOT_BUY", price=price, realized_pnl=self._account_state().realized_pnl)
                self.log.write("order_lifecycle", action="EXIT_SELL", order_id=exit_order_id, symbol=candidate.symbol, price=price, quantity=active_position.quantity)
                self.previous_signals.pop(candidate.symbol, None)
                continue
            if active_position is not None:
                self.log.write("allocation_rejected", symbol=candidate.symbol, reason="DUPLICATE_ALLOCATION", existing_position=True)
                continue
            if decision["decision"] != "BUY":
                continue
            snapshot, audit = self._allocation_snapshot(candidate, decision, price, previous)
            if snapshot is None:
                continue
            self.previous_signals[candidate.symbol] = snapshot
            active = self.supervisor.runtime.pending.active_for_intent(snapshot.identity.identity_key)
            if active is not None:
                action = self.supervisor.revalidate(intent_id=active.intent_id, snapshot=snapshot, market_price=price, now=event.event_timestamp)
                self.log.write("order_revalidation", intent_id=active.intent_id, action=action.value, order_id=active.order_id)
                if action.value in {"CANCEL", "NO_TRADE"}:
                    self.capital.release_for_order(active.order_id, reason=action.value)
            else:
                try:
                    pending = self.supervisor.submit_signal(snapshot, now=event.event_timestamp)
                    self.capital.bind_order(audit.allocation_id, pending.order_id)
                    self.log.write("order_lifecycle", action="PENDING", order_id=pending.order_id, symbol=pending.symbol, price=pending.entry_price, quantity=pending.quantity, allocation_id=audit.allocation_id)
                except (ValueError, PermissionError) as exc:
                    self.capital.release(audit.allocation_id, reason=f"ENTRY_REJECTED:{type(exc).__name__}")
                    self.log.write("order_rejected", symbol=candidate.symbol, reason=str(exc), allocation_id=audit.allocation_id)

    def _account_state(self):
        return self.supervisor.runtime.ledger.replay()

    def _marked_equity(self, state: Any) -> float:
        return state.wallet.cash + sum(p.quantity * self.last_prices[p.symbol] for p in state.positions if p.symbol in self.last_prices)

    def _finalize(self, runner: MarketStreamRunner) -> dict[str, Any]:
        assert self.capital is not None
        state = self._account_state()
        original = self.supervisor.replay_state()
        recovered = self.supervisor.recover()
        recovered_again = recovered.recover()
        replay_equal = original == recovered.replay_state()
        repeat_equal = recovered.replay_state() == recovered_again.replay_state()
        capital_original = self.capital.audit_state()
        capital_recovered = self.capital.recover(recovered.runtime.ledger).audit_state()
        capital_recovered_again = self.capital.recover(recovered.runtime.ledger).recover(recovered_again.runtime.ledger).audit_state()
        capital_replay_equal = capital_original == capital_recovered == capital_recovered_again
        health = self.supervisor.health
        if not replay_equal or not repeat_equal or not capital_replay_equal:
            raise RuntimeError("recovery/replay verification failed")
        if not health.paper_only:
            raise RuntimeError("paper-only safety contract failed")
        return {"starting_equity": state.starting_equity, "ending_equity": self._marked_equity(state), "realized_pnl": state.realized_pnl, "unrealized_pnl": state.unrealized_pnl, "fees": state.cumulative_fees, "slippage": state.cumulative_slippage, "max_drawdown": self.maximum_drawdown, "orders": len(self.supervisor.runtime.orders.events), "fills": sum(1 for e in self.supervisor.runtime.orders.events if e.event_type == "ORDER_FILLED"), "cancelled_replaced_orders": sum(1 for e in self.supervisor.runtime.orders.events if e.event_type in {"ORDER_CANCELLED", "ORDER_REPLACED"}), "open_position_at_end": [p.symbol for p in state.positions if p.quantity > 0], "reconnect_count": runner.stats.reconnects, "duplicate_event_count": runner.stats.duplicates, "runtime_health": health.healthy, "paper_only": health.paper_only, "runtime_failure": self.runtime_failure, "replay_equal_after_recovery": replay_equal, "replay_equal_after_repeated_recovery": repeat_equal, "capital_replay_equal": capital_replay_equal, "capital_state": capital_original, "last_market_event_id": health.last_market_event_id}


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Official ORION public-market paper runtime runner")
    parser.add_argument("--duration-hours", type=float, default=8.0)
    parser.add_argument("--starting-capital", type=float, default=200.0)
    parser.add_argument("--capital-mode", choices=("FIXED_ALLOCATION", "COMPOUNDING"), default="FIXED_ALLOCATION")
    parser.add_argument("--allocation-rate", type=float, default=0.10)
    parser.add_argument("--fixed-allocation", type=float, default=None)
    parser.add_argument("--max-concurrent-positions", type=int, default=None)
    parser.add_argument("--universe", choices=("dynamic", "fixed"), default="dynamic")
    parser.add_argument("--symbols", default="")
    parser.add_argument("--output-dir", default="runs/paper")
    parser.add_argument("--top-n", type=int, default=10)
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    symbols = tuple(s.strip().upper() for s in args.symbols.split(",") if s.strip())
    try:
        config = Paper8HConfig(duration_hours=args.duration_hours, starting_capital=args.starting_capital, symbols=symbols, dynamic_universe=args.universe == "dynamic", output_dir=Path(args.output_dir), capital_mode=CapitalMode(args.capital_mode), allocation_rate=args.allocation_rate, fixed_allocation=args.fixed_allocation, max_concurrent_positions=args.max_concurrent_positions, top_n=args.top_n)
        report = asyncio.run(Paper8HRunner.create(config).run())
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"ORION paper runner failed closed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
