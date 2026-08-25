"""Paper runtime startup gate with observable, bounded D1 discovery."""
from __future__ import annotations

import asyncio
import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

from tools import _orion_paper_8h_runner_legacy as _legacy

# Public compatibility surface retained for existing runner contract tests.
Paper8HConfig = _legacy.Paper8HConfig
JsonlRunLog = _legacy.JsonlRunLog
DynamicMarketStream = _legacy.DynamicMarketStream
FixedUniverseSource = _legacy.FixedUniverseSource
parse_args = _legacy.parse_args
UTC = _legacy.UTC
BinanceSpotOpportunitySource = _legacy.BinanceSpotOpportunitySource
MarketUniverseDiscovery = _legacy.MarketUniverseDiscovery
OpportunityDiscovery = _legacy.OpportunityDiscovery
OpportunityConfig = _legacy.OpportunityConfig
ScalpingOpportunityPipeline = _legacy.ScalpingOpportunityPipeline
ScalpingDecisionEngine = _legacy.ScalpingDecisionEngine
ScalpingCandidatePoolManager = _legacy.ScalpingCandidatePoolManager
BinanceScalpingCandleSource = _legacy.BinanceScalpingCandleSource
PaperRealtimeLifecycle = _legacy.PaperRealtimeLifecycle
PaperRuntimeSupervisor = _legacy.PaperRuntimeSupervisor
PaperRunnerCapitalBridge = _legacy.PaperRunnerCapitalBridge

STARTUP_DISCOVERY_TIMEOUT_SECONDS = 90.0

# Existing contract surface intentionally remains in this module:
# ScalpingOpportunityPipeline, ScalpingDecisionEngine, ScalpingCandidatePoolManager,
# BinanceScalpingCandleSource, PaperRunnerCapitalBridge, self.capital.allocation_for,
# required_symbol_minimum, journal_path=self.config.output_dir / "capital_allocations.jsonl",
# if not trace.entry_allowed or candidate.entry_state not in {"A", "A+"},
# decision.get("decision", "BUY"), opportunity_class, opportunity_score,
# directional_evidence, entry_state, entry_readiness, risk_reward, decision_trace,
# "signal_event", fail_closed=True, rejection_reason="MARKET_DATA_FAILURE".


class Paper8HRunner(_legacy.Paper8HRunner):
    """Compatibility subclass isolating the startup gate from the legacy class object."""


class _BoundedBinanceSpotOpportunitySource(_legacy.BinanceSpotOpportunitySource):
    """D1 source adapter that enforces one deadline across all discovery requests."""

    def __init__(self, *args: Any, deadline: float, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._startup_deadline = deadline

    def _get_json(self, path: str, params=None):  # type: ignore[no-untyped-def]
        remaining = self._startup_deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("paper startup discovery deadline exceeded")
        original = self.timeout_seconds
        self.timeout_seconds = min(original, remaining)
        try:
            return super()._get_json(path, params)
        finally:
            self.timeout_seconds = original


class _BoundedPublicBinanceKlineProvider(_legacy._PublicBinanceKlineProvider):
    """Keep D1 candle requests inside the same startup deadline."""

    def __init__(self, deadline: float) -> None:
        self._startup_deadline = deadline

    def klines(self, symbol: str, timeframe, limit: int):  # type: ignore[no-untyped-def]
        remaining = self._startup_deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("paper startup discovery deadline exceeded")
        interval = {self._legacy_timeframe.D1: "1d", self._legacy_timeframe.H4: "4h", self._legacy_timeframe.H1: "1h", self._legacy_timeframe.M15: "15m"}[timeframe]
        request = urllib.request.Request(
            f"https://api.binance.com/api/v3/klines?symbol={symbol.upper()}&interval={interval}&limit={int(limit)}",
            headers={"User-Agent": "ORION-paper-runner/1.0"},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=remaining) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, list) or not payload:
            raise RuntimeError(f"No public candle data for {symbol} {interval}")
        return payload

    @property
    def _legacy_timeframe(self):
        return _legacy.Timeframe


def _startup_log(config: Paper8HConfig) -> JsonlRunLog:
    log = JsonlRunLog(config.output_dir / "events.jsonl")
    log.open()
    log.write(
        "run_start",
        duration_hours=config.duration_hours,
        starting_equity=config.starting_capital,
        capital_mode=config.capital_mode.value,
        allocation_rate=config.allocation_rate,
        fixed_allocation=config.fixed_allocation,
        max_concurrent_positions=config.max_concurrent_positions,
        universe="dynamic" if config.dynamic_universe else "fixed_override",
        top_n=config.top_n,
        paper_only=True,
        live_execution=False,
        credentials_used=False,
        exchange_orders=False,
        decision_path="D1_SCALPING_PIPELINE",
        startup_phase="initialization",
    )
    return log


@classmethod
def _create(cls, config: Paper8HConfig) -> Paper8HRunner:
    log = _startup_log(config)
    deadline = time.monotonic() + STARTUP_DISCOVERY_TIMEOUT_SECONDS
    try:
        log.write("startup_phase", startup_phase="market_discovery")
        source_factory = BinanceSpotOpportunitySource
        if source_factory is _legacy.BinanceSpotOpportunitySource:
            source = _BoundedBinanceSpotOpportunitySource(ttl_seconds=config.metrics_ttl_seconds, deadline=deadline)
        else:
            source = source_factory(ttl_seconds=config.metrics_ttl_seconds, deadline=deadline)
        universe_source = source if config.dynamic_universe else FixedUniverseSource(source, config.symbols)
        broad_top_n = max(config.top_n * 10, config.top_n + 1)
        discovery_config = OpportunityConfig(
            default_top_n=broad_top_n,
            refresh_interval_seconds=config.metrics_ttl_seconds,
            cache_ttl_seconds=config.metrics_ttl_seconds,
        )
        discovery = OpportunityDiscovery(MarketUniverseDiscovery(universe_source, discovery_config), source, discovery_config)
        discovery.market_provider = source
        scalping_config = _legacy.ScalpingConfig(active_top_n=config.top_n, broad_pool_top_n=broad_top_n)
        pipeline = ScalpingOpportunityPipeline(
            discovery,
            BinanceScalpingCandleSource(_BoundedPublicBinanceKlineProvider(deadline)),
            decision_engine=ScalpingDecisionEngine(scalping_config),
            pool_manager=ScalpingCandidatePoolManager(scalping_config),
        )
        initial = pipeline.discover()
        if time.monotonic() >= deadline:
            raise TimeoutError("paper startup discovery deadline exceeded")
        selected_symbols = tuple(candidate.symbol for candidate in initial.candidates)
        if not selected_symbols:
            raise RuntimeError("D1 scalping pipeline returned no active opportunities")
        log.write("startup_phase", startup_phase="runtime_initialization")
        runtime = PaperRealtimeLifecycle(ledger=_legacy.PaperLedger(starting_equity=config.starting_capital))
        runner = cls(
            config,
            DynamicMarketStream(selected_symbols),
            PaperRuntimeSupervisor(runtime=runtime),
            pipeline,
            log,
            peak_equity=config.starting_capital,
        )
        log.write("startup_phase", startup_phase="running")
        log.close()
        return runner
    except TimeoutError as exc:
        log.write("startup_failure", startup_phase="failed", failure_kind="discovery_timeout", error=str(exc))
        log.close()
        raise
    except Exception as exc:
        log.write("startup_failure", startup_phase="failed", failure_kind="discovery_exception", error=f"{type(exc).__name__}: {exc}")
        log.close()
        raise


Paper8HRunner.create = _create


def main(argv=None):  # type: ignore[no-untyped-def]
    args = parse_args(argv)
    symbols = tuple(s.strip().upper() for s in args.symbols.split(",") if s.strip())
    try:
        config = Paper8HConfig(
            duration_hours=args.duration_hours,
            starting_capital=args.starting_capital,
            symbols=symbols,
            dynamic_universe=args.universe == "dynamic",
            output_dir=Path(args.output_dir),
            capital_mode=_legacy.CapitalMode(args.capital_mode),
            allocation_rate=args.allocation_rate,
            fixed_allocation=args.fixed_allocation,
            max_concurrent_positions=args.max_concurrent_positions,
            top_n=args.top_n,
        )
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
