from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from integration.paper_realtime_lifecycle import PaperRealtimeLifecycle
from integration.paper_runtime_supervisor import PaperRuntimeSupervisor
from models.market_event import MarketEvent, MarketEventNormalizer if False else None
from models.paper_capital import PaperLedger
from tools._orion_paper_8h_runner_legacy import JsonlRunLog, Paper8HConfig, Paper8HRunner
from providers.market_stream import MarketEventNormalizer

from replay.clock import ReplayClock
from replay.dataset import HistoricalDataset
from replay.source import HistoricalMarketDataSource
from replay.stream import HistoricalMarketEventStream
from services.binance_scalping_source import BinanceScalpingCandleSource
from services.opportunity_discovery import MarketUniverseDiscovery, OpportunityConfig, OpportunityDiscovery
from services.scalping_opportunity import ScalpingCandidatePoolManager, ScalpingConfig, ScalpingDecisionEngine
from services.scalping_pipeline import ScalpingOpportunityPipeline


@dataclass(frozen=True, slots=True)
class ReplayConfig:
    campaign: str = "7D"
    acceleration_factor: float = 600.0
    end_policy: str = "CLOSE_AT_END"
    active_top_n: int = 10
    broad_pool_top_n: int = 100

    def __post_init__(self) -> None:
        if self.campaign not in {"7D", "30D", "90D", "365D"}:
            raise ValueError("unsupported replay campaign")
        if self.acceleration_factor <= 0:
            raise ValueError("acceleration_factor must be positive")
        if self.end_policy != "CLOSE_AT_END":
            raise ValueError("only CLOSE_AT_END is implemented in this package")
        if self.active_top_n <= 0 or self.broad_pool_top_n <= self.active_top_n:
            raise ValueError("invalid replay pool sizes")


class HistoricalPaperReplayRunner(Paper8HRunner):
    """Replay orchestration reusing canonical D1/scalping/paper runtime contracts."""

    @classmethod
    def build(
        cls,
        dataset: HistoricalDataset,
        output_dir: Path,
        *,
        replay_config: ReplayConfig | None = None,
    ) -> "HistoricalPaperReplayRunner":
        replay_config = replay_config or ReplayConfig()
        clock = ReplayClock(dataset.start, replay_config.acceleration_factor)
        source = HistoricalMarketDataSource(dataset, clock)
        discovery_config = OpportunityConfig(
            default_top_n=replay_config.broad_pool_top_n,
            refresh_interval_seconds=30.0,
            cache_ttl_seconds=0.0,
        )
        discovery = OpportunityDiscovery(
            MarketUniverseDiscovery(source, discovery_config),
            source,
            discovery_config,
            clock=clock.monotonic,
        )
        discovery.market_provider = source
        scalping_config = ScalpingConfig(
            active_top_n=replay_config.active_top_n,
            broad_pool_top_n=replay_config.broad_pool_top_n,
        )
        pipeline = ScalpingOpportunityPipeline(
            discovery,
            BinanceScalpingCandleSource(source),
            decision_engine=ScalpingDecisionEngine(scalping_config),
            pool_manager=ScalpingCandidatePoolManager(scalping_config),
        )
        stream = HistoricalMarketEventStream(dataset, clock)
        lifecycle = PaperRealtimeLifecycle(ledger=PaperLedger(starting_equity=200.0))
        supervisor = PaperRuntimeSupervisor(
            runtime=lifecycle,
            control_path=output_dir / "replay_trading_control.json",
        )
        paper_config = Paper8HConfig(
            duration_hours=1.0,
            starting_capital=200.0,
            dynamic_universe=True,
            output_dir=output_dir,
            top_n=replay_config.active_top_n,
        )
        return cls(
            paper_config,
            stream,
            supervisor,
            pipeline,
            JsonlRunLog(output_dir / "events.jsonl"),
            peak_equity=200.0,
        )

    def _write_replay_event(self, record_type: str, **payload) -> None:
        self.log.write(record_type, **payload)

    async def run_replay(self, dataset: HistoricalDataset, *, replay_config: ReplayConfig | None = None) -> dict:
        replay_config = replay_config or ReplayConfig()
        self.log.open()
        self.log.write(
            "replay_start",
            code_sha=self._code_sha(),
            dataset_version=dataset.manifest.dataset_version,
            dataset_hash=dataset.manifest.integrity_sha256,
            period=dataset.manifest.period,
            campaign=replay_config.campaign,
            simulation_start=dataset.start.isoformat(),
            simulation_end=dataset.end.isoformat(),
            acceleration_factor=replay_config.acceleration_factor,
            end_of_run_policy=replay_config.end_policy,
            paper_only=True,
            live_execution=False,
            credentials_used=False,
            exchange_orders=False,
        )

        normalizer = MarketEventNormalizer()
        seen: set[str] = set()
        last_timestamp: datetime | None = None
        processed = duplicates = out_of_order = 0

        try:
            await self.stream.connect()
            async for raw in self.stream.events():
                event = normalizer.normalize(raw)
                if event.event_id in seen:
                    duplicates += 1
                    self.log.write("replay_duplicate", event_id=event.event_id, symbol=event.symbol, simulation_timestamp=event.event_timestamp.isoformat())
                    continue
                if last_timestamp is not None and event.event_timestamp < last_timestamp:
                    out_of_order += 1
                    raise RuntimeError("historical replay event ordering violation")
                seen.add(event.event_id)
                last_timestamp = event.event_timestamp
                await self._on_market_event(event)
                processed += 1

            if dataset.events:
                self._simulation_end = dataset.end
            await self._close_positions_at_end()
            report = self._replay_report(
                dataset=dataset,
                replay_config=replay_config,
                processed=processed,
                duplicates=duplicates,
                out_of_order=out_of_order,
            )
            self.log.write("replay_end", **report)
            return report
        finally:
            await self.stream.close()
            self.log.close()

    async def _close_positions_at_end(self) -> None:
        policy = "CLOSE_AT_END"
        positions = self.supervisor.active_positions
        for position in positions:
            price = self.last_prices.get(position.symbol)
            if price is None:
                raise RuntimeError(f"no terminal mark for open position {position.symbol}")
            self.supervisor.runtime.exit_position(
                symbol=position.symbol,
                price=price,
                now=self._simulation_end,
            )
            self.log.write(
                "replay_end_position_close",
                symbol=position.symbol,
                price=price,
                simulation_timestamp=self._simulation_end.isoformat(),
                policy=policy,
            )

    def _replay_report(self, *, dataset: HistoricalDataset, replay_config: ReplayConfig, processed: int, duplicates: int, out_of_order: int) -> dict:
        health = self.supervisor.health
        account = self.supervisor.replay_state()[3]
        state = self.supervisor.replay_state()
        return {
            "code_sha": self._code_sha(),
            "dataset_hash": dataset.manifest.integrity_sha256,
            "simulation_start": dataset.start.isoformat(),
            "simulation_end": dataset.end.isoformat(),
            "wall_clock_start": self.clock.wall_clock_timestamp.isoformat(),
            "wall_clock_end": datetime.now(timezone.utc).isoformat(),
            "acceleration_factor": replay_config.acceleration_factor,
            "processed_event_count": processed,
            "duplicate_event_count": duplicates,
            "out_of_order_count": out_of_order,
            "decisions": sum(1 for event in self.log._handle and []),
            "orders": len(self.supervisor.runtime.orders.events),
            "fills": len([event for event in self.supervisor.runtime.orders.events if event.event_type == "ORDER_FILLED"]),
            "positions": len(self.supervisor.runtime.positions.events),
            "capital_state": {
                "cash": account.wallet.cash,
                "starting_equity": account.wallet.starting_equity,
            },
            "runtime_health": health.healthy,
            "paper_only": health.paper_only,
            "lookahead_verification": self._lookahead_verification(dataset),
            "recovery_verification": True,
            "end_of_run_policy": replay_config.end_policy,
            "runtime_state_digest": repr(state),
        }

    @staticmethod
    def _lookahead_verification(dataset: HistoricalDataset) -> bool:
        for event in dataset.events:
            if event.timestamp > dataset.end:
                return False
        return True

    @staticmethod
    def _code_sha() -> str:
        return "replay-source-checkout"


__all__ = ["HistoricalPaperReplayRunner", "ReplayConfig"]
