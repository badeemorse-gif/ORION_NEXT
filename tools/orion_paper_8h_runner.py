"""Official ORION paper runtime runner.

Public Binance market data -> D1 opportunity discovery -> canonical decision
engine -> D3 SignalSnapshot -> PaperRuntimeSupervisor -> D5/D4/D6.

Paper-only: this module has no credentials, no exchange-order API, and no live
execution path. Importing it never starts a run.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BINANS_SCANNER = _REPO_ROOT / "binansScanner"
if str(_BINANS_SCANNER) not in sys.path:
    sys.path.insert(0, str(_BINANS_SCANNER))

from decision_engine import evaluate_decision
from engines.indicator_engine import IndicatorEngine
from engines.profile_engine import ProfileEngine
from enums import Timeframe
from integration.paper_realtime_lifecycle import PaperRealtimeLifecycle
from integration.paper_runtime_supervisor import PaperRuntimeSupervisor
from models.market_event import MarketEvent, MarketEventType
from models.opportunity import MarketMetrics, OpportunityCandidate
from models.paper_capital import PaperLedger
from models.signal_snapshot import MaterialChangePolicy, SignalIdentity, SignalSnapshot, build_next_snapshot
from providers.binance_mapper import BinanceMapper
from providers.market_stream import BinanceWebSocketMarketStream, MarketStreamRunner
from services.opportunity_discovery import MarketUniverseDiscovery, OpportunityConfig, OpportunityDiscovery

UTC = timezone.utc
BINANCE_PUBLIC_API = "https://api.binance.com"


class CanonicalDecisionContextProvider:
    """Build the actual upstream profile context used at the decision boundary.

    Market data is mapped through BinanceMapper, enriched by the canonical
    IndicatorEngine, and profiled by the canonical ProfileEngine. No health,
    trade-mode, confidence, or module values are invented by the runner.
    """

    _PROFILE_TIMEFRAMES = (("1h", Timeframe.H1), ("4h", Timeframe.H4), ("1d", Timeframe.D1))

    def __init__(self, api_base: str = BINANCE_PUBLIC_API) -> None:
        self._api_base = api_base.rstrip("/")
        self._mapper = BinanceMapper()
        self._indicator_engine = IndicatorEngine()
        self._profile_engine = ProfileEngine()
        self._cache: dict[str, tuple[float, Mapping[str, Any]]] = {}

    def _get_json(self, path: str, params: Mapping[str, str]) -> Any:
        request = Request(
            f"{self._api_base}{path}?{urlencode(params)}",
            headers={"User-Agent": "ORION-paper-runner/1.0"},
            method="GET",
        )
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def build(self, symbol: str) -> Mapping[str, Any]:
        symbol = symbol.upper()
        cached = self._cache.get(symbol)
        now = time.monotonic()
        if cached is not None and now - cached[0] < 30.0:
            return cached[1]

        timeframe_data = {}
        for interval, timeframe in self._PROFILE_TIMEFRAMES:
            payload = self._get_json(
                "/api/v3/klines",
                {"symbol": symbol, "interval": interval, "limit": "250"},
            )
            if not isinstance(payload, list) or not payload:
                raise RuntimeError(f"No canonical profile data for {symbol} {interval}")
            timeframe_data[timeframe] = self._mapper.convert_klines_to_dataframe(payload)

        dataset = self._mapper.create_market_dataset(
            symbol=symbol,
            timeframe_data=timeframe_data,
            source="BINANCE_PUBLIC_PROFILE",
        )
        dataset = self._indicator_engine.calculate_dataset(dataset)
        profile = self._profile_engine.build_profile(dataset)

        # evaluate_decision() is a legacy dict-boundary contract. These values
        # are translated only from the canonical ProfileResult; no fixed
        # "healthy" or "standard" profile is created here.
        context: Mapping[str, Any] = {
            "health_score": float(profile.statistics.health_score),
            "trade_mode": "FULL_ANALYSIS" if profile.is_tradeable else "NEW_LISTING",
        }
        self._cache[symbol] = (now, context)
        return context


def canonical_decision(
    candidate: OpportunityCandidate,
    context: Optional[Mapping[str, Any]] = None,
) -> Mapping[str, Any]:
    """Evaluate actual D1 score against canonical upstream decision context."""
    if context is None:
        raise ValueError("canonical decision context is required")
    return evaluate_decision({"score": float(candidate.opportunity_score)}, dict(context))


@dataclass(frozen=True, slots=True)
class Paper8HConfig:
    duration_hours: float = 8.0
    starting_capital: float = 200.0
    symbols: tuple[str, ...] = ("BTCUSDT",)
    output_dir: Path = Path("runs/paper")
    max_notional_pct: float = 20.0
    top_n: int = 1
    metrics_ttl_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.duration_hours <= 0.0:
            raise ValueError("duration_hours must be positive")
        if self.starting_capital <= 0.0:
            raise ValueError("starting_capital must be positive")
        if not self.symbols or any(not str(symbol).strip() for symbol in self.symbols):
            raise ValueError("at least one symbol is required")
        if not 0.0 < self.max_notional_pct <= 100.0:
            raise ValueError("max_notional_pct must be within (0, 100]")
        if self.top_n <= 0:
            raise ValueError("top_n must be positive")
        if self.metrics_ttl_seconds < 0.0:
            raise ValueError("metrics_ttl_seconds cannot be negative")


class BinancePublicOpportunitySource:
    """Read-only public Binance REST adapter for D1's required metrics."""

    def __init__(self, symbols: tuple[str, ...], *, ttl_seconds: float = 30.0, api_base: str = BINANCE_PUBLIC_API) -> None:
        self._symbols = tuple(sorted({symbol.upper() for symbol in symbols}))
        self._ttl = ttl_seconds
        self._api_base = api_base.rstrip("/")
        self._exchange_cache: Optional[tuple[float, Mapping[str, Any]]] = None
        self._metrics_cache: dict[str, tuple[float, MarketMetrics]] = {}

    def _get_json(self, path: str, params: Mapping[str, str]) -> Mapping[str, Any] | list[Any]:
        request = Request(f"{self._api_base}{path}?{urlencode(params)}", headers={"User-Agent": "ORION-paper-runner/1.0"}, method="GET")
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if isinstance(payload, Mapping) and payload.get("code") is not None and int(payload.get("code", 0)) < 0:
            raise RuntimeError(f"Binance public API error: {payload}")
        return payload

    def exchange_info(self) -> Mapping[str, Any]:
        now = time.monotonic()
        if self._exchange_cache is not None and now - self._exchange_cache[0] < self._ttl:
            return self._exchange_cache[1]
        rows: list[Mapping[str, Any]] = []
        for symbol in self._symbols:
            payload = self._get_json("/api/v3/exchangeInfo", {"symbol": symbol})
            if isinstance(payload, Mapping):
                rows.extend(item for item in payload.get("symbols", []) if isinstance(item, Mapping))
        result = {"symbols": rows}
        self._exchange_cache = (now, result)
        return result

    def metrics(self, symbol: str) -> MarketMetrics:
        symbol = symbol.upper()
        now = time.monotonic()
        cached = self._metrics_cache.get(symbol)
        if cached is not None and now - cached[0] < self._ttl:
            return cached[1]
        payload = self._get_json("/api/v3/ticker/24hr", {"symbol": symbol})
        if not isinstance(payload, Mapping):
            raise RuntimeError(f"Unexpected 24h ticker response for {symbol}")
        last = float(payload["lastPrice"])
        high = float(payload["highPrice"])
        low = float(payload["lowPrice"])
        volatility = abs(high - low) / last if last > 0.0 else float("nan")
        metrics = MarketMetrics(symbol=symbol, quote_volume_24h=float(payload["quoteVolume"]), volatility=volatility, spread_bps=None, tradable=True)
        self._metrics_cache[symbol] = (now, metrics)
        return metrics


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
    stream: BinanceWebSocketMarketStream
    supervisor: PaperRuntimeSupervisor
    opportunity: OpportunityDiscovery
    log: JsonlRunLog
    decision_context: Any = field(default_factory=CanonicalDecisionContextProvider)
    previous_signals: dict[str, SignalSnapshot] = field(default_factory=dict)
    last_prices: dict[str, float] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    runtime_failure: Optional[str] = None
    peak_equity: float = 0.0
    maximum_drawdown: float = 0.0

    @classmethod
    def create(cls, config: Paper8HConfig) -> "Paper8HRunner":
        runtime = PaperRealtimeLifecycle(ledger=PaperLedger(starting_equity=config.starting_capital))
        supervisor = PaperRuntimeSupervisor(runtime=runtime)
        public_source = BinancePublicOpportunitySource(config.symbols, ttl_seconds=config.metrics_ttl_seconds)
        opportunity_config = OpportunityConfig(default_top_n=config.top_n)
        opportunity = OpportunityDiscovery(MarketUniverseDiscovery(public_source, opportunity_config), public_source, opportunity_config)
        stream = BinanceWebSocketMarketStream(config.symbols, [Timeframe.M1])
        return cls(config, stream, supervisor, opportunity, JsonlRunLog(config.output_dir / "events.jsonl"), CanonicalDecisionContextProvider(), peak_equity=config.starting_capital)

    async def run(self) -> dict[str, Any]:
        self.started_at = datetime.now(UTC)
        self.log.open()
        self.log.write("run_start", duration_hours=self.config.duration_hours, starting_equity=self.config.starting_capital, symbols=self.config.symbols, paper_only=True, live_execution=False, credentials_used=False, exchange_orders=False)
        stream_runner = MarketStreamRunner(self.stream, on_event=self._on_market_event)
        stream_task = asyncio.create_task(stream_runner.run())
        timer_task = asyncio.create_task(asyncio.sleep(self.config.duration_hours * 3600.0))
        try:
            done, _ = await asyncio.wait({stream_task, timer_task}, return_when=asyncio.FIRST_COMPLETED)
            if stream_task in done:
                timer_task.cancel()
                with suppress(asyncio.CancelledError):
                    await timer_task
                stream_task.result()
            else:
                stream_runner.stop()
                await self.stream.close()
                await stream_task
        except Exception as exc:
            self.runtime_failure = f"{type(exc).__name__}: {exc}"
            self.log.write("runtime_failure", error=self.runtime_failure)
            raise
        finally:
            stream_runner.stop()
            await self.stream.close()
            self.finished_at = datetime.now(UTC)
            report = self._finalize(stream_runner)
            self.log.write("run_end", **report)
            self.log.close()
        return report

    async def _on_market_event(self, event: MarketEvent) -> None:
        price = event.payload.get("price")
        if price is not None:
            self.last_prices[event.symbol] = float(price)
        try:
            filled = self.supervisor.process_market_event(event)
        except Exception as exc:
            self.runtime_failure = f"{type(exc).__name__}: {exc}"
            self.log.write("runtime_failure", event_id=event.event_id, error=self.runtime_failure)
            raise
        state = self._account_state()
        equity = self._marked_equity(state)
        self.peak_equity = max(self.peak_equity, equity)
        self.maximum_drawdown = max(self.maximum_drawdown, self.peak_equity - equity)
        health = self.supervisor.health
        self.log.write("market_event", event_id=event.event_id, source_event_id=event.source_event_id, symbol=event.symbol, market_event_type=event.event_type.value, price=price, filled=filled, active_orders=len(self.supervisor.active_orders), active_positions=len(self.supervisor.active_positions), equity=equity, drawdown=max(self.peak_equity - equity, 0.0), health=health.healthy)
        if filled:
            for order_id in filled:
                self.log.write("fill", order_id=order_id, symbol=event.symbol, price=price)
        if event.event_type is MarketEventType.CANDLE_CLOSE:
            await self._run_signal_cycle(event)

    async def _run_signal_cycle(self, event: MarketEvent) -> None:
        try:
            opportunities = await asyncio.to_thread(self.opportunity.discover, self.config.top_n)
        except Exception as exc:
            self.log.write("signal_cycle_failure", error=f"{type(exc).__name__}: {exc}")
            return
        for candidate in opportunities.candidates:
            try:
                context = await asyncio.to_thread(self.decision_context.build, candidate.symbol)
                decision = canonical_decision(candidate, context)
            except Exception as exc:
                self.log.write("decision_context_failure", symbol=candidate.symbol, error=f"{type(exc).__name__}: {exc}")
                continue
            entry_price = self.last_prices.get(candidate.symbol)
            if entry_price is None or entry_price <= 0.0:
                continue
            active_position = self.supervisor.runtime.positions.active_for_symbol(candidate.symbol)
            previous = self.previous_signals.get(candidate.symbol)
            if active_position is not None and (decision["decision"] != "BUY" or (previous is not None and previous.is_expired(event.event_timestamp))):
                exit_order_id = self.supervisor.runtime.exit_position(symbol=candidate.symbol, price=entry_price, now=event.event_timestamp)
                state = self._account_state()
                self.log.write("signal_event", symbol=candidate.symbol, direction="SELL", decision=decision["decision"], exit_trigger="DECISION_NOT_BUY" if decision["decision"] != "BUY" else "SIGNAL_EXPIRED", entry_price=entry_price, realized_pnl=state.realized_pnl)
                self.log.write("order_lifecycle", action="EXIT_SELL", order_id=exit_order_id, symbol=candidate.symbol, price=entry_price, quantity=active_position.quantity)
                self.previous_signals.pop(candidate.symbol, None)
                continue
            snapshot = build_next_snapshot(
                previous=previous,
                identity=SignalIdentity(candidate.symbol, "D1_D3_PAPER", "ENTRY"),
                direction="BUY",
                decision=decision["decision"],
                confidence=float(candidate.opportunity_score),
                entry_plan={"entry_price": entry_price, "quantity": self._quantity_for(entry_price)},
                generated_at=event.event_timestamp,
                valid_until=event.event_timestamp + timedelta(minutes=15),
                policy=MaterialChangePolicy(entry_price_change_pct=0.10),
                market_context_fingerprint=f"d1:{candidate.symbol}:{candidate.rank}:{candidate.opportunity_score:.8f}",
                quality=float(candidate.opportunity_score),
            ).current
            self.previous_signals[candidate.symbol] = snapshot
            self.log.write("signal_event", symbol=candidate.symbol, version=snapshot.version, decision=decision["decision"], direction=snapshot.direction, confidence=snapshot.confidence, entry_price=entry_price, quantity=snapshot.entry_plan["quantity"], opportunity_score=candidate.opportunity_score, rank=candidate.rank)
            active = self.supervisor.runtime.pending.active_for_intent(snapshot.identity.identity_key)
            if active is not None:
                action = self.supervisor.revalidate(intent_id=active.intent_id, snapshot=snapshot, market_price=entry_price, now=event.event_timestamp)
                self.log.write("order_revalidation", intent_id=active.intent_id, action=action.value, order_id=active.order_id)
            elif decision["decision"] == "BUY":
                try:
                    pending = self.supervisor.submit_signal(snapshot, now=event.event_timestamp)
                    self.log.write("order_lifecycle", action="PENDING", order_id=pending.order_id, symbol=pending.symbol, price=pending.entry_price, quantity=pending.quantity)
                except ValueError as exc:
                    self.log.write("order_rejected", symbol=candidate.symbol, reason=str(exc))

    def _quantity_for(self, price: float) -> float:
        state = self._account_state()
        return max(state.wallet.available_cash * self.config.max_notional_pct / 100.0 / price, 0.0)

    def _account_state(self):
        return self.supervisor.runtime.ledger.replay()

    def _marked_equity(self, state: Any) -> float:
        return state.wallet.cash + sum(position.quantity * self.last_prices[position.symbol] for position in state.positions if position.symbol in self.last_prices)

    def _finalize(self, stream_runner: MarketStreamRunner) -> dict[str, Any]:
        state = self._account_state()
        original = self.supervisor.replay_state()
        recovered = self.supervisor.recover()
        recovered_again = recovered.recover()
        replay_equal = original == recovered.replay_state()
        repeat_equal = recovered.replay_state() == recovered_again.replay_state()
        health = self.supervisor.health
        marked_equity = self._marked_equity(state)
        report = {
            "starting_equity": state.starting_equity,
            "ending_equity": marked_equity,
            "realized_pnl": state.realized_pnl,
            "unrealized_pnl": sum(position.quantity * (self.last_prices.get(position.symbol, position.average_price) - position.average_price) for position in state.positions),
            "fees": state.cumulative_fees,
            "slippage": state.cumulative_slippage,
            "max_drawdown": self.maximum_drawdown,
            "orders": len(self.supervisor.runtime.orders.events),
            "fills": sum(1 for event in self.supervisor.runtime.orders.events if event.event_type == "ORDER_FILLED"),
            "cancelled_replaced_orders": sum(1 for event in self.supervisor.runtime.orders.events if event.event_type in {"ORDER_CANCELLED", "ORDER_REPLACED"}),
            "open_position_at_end": [position.symbol for position in state.positions if position.quantity > 0.0],
            "reconnect_count": stream_runner.stats.reconnects,
            "duplicate_event_count": stream_runner.stats.duplicates,
            "runtime_health": health.healthy,
            "paper_only": health.paper_only,
            "runtime_failure": self.runtime_failure,
            "replay_equal_after_recovery": replay_equal,
            "replay_equal_after_repeated_recovery": repeat_equal,
            "last_market_event_id": health.last_market_event_id,
            "duration_seconds": ((self.finished_at or datetime.now(UTC)) - (self.started_at or datetime.now(UTC))).total_seconds(),
        }
        if not replay_equal or not repeat_equal:
            raise RuntimeError("recovery/replay verification failed")
        if not health.paper_only:
            raise RuntimeError("paper-only safety contract failed")
        return report


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Official ORION public-market paper runtime runner")
    parser.add_argument("--duration-hours", type=float, default=8.0)
    parser.add_argument("--starting-capital", type=float, default=200.0)
    parser.add_argument("--symbols", default="BTCUSDT")
    parser.add_argument("--output-dir", default="runs/paper")
    parser.add_argument("--max-notional-pct", type=float, default=20.0)
    parser.add_argument("--top-n", type=int, default=1)
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    config = Paper8HConfig(duration_hours=args.duration_hours, starting_capital=args.starting_capital, symbols=tuple(symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip()), output_dir=Path(args.output_dir), max_notional_pct=args.max_notional_pct, top_n=args.top_n)
    try:
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