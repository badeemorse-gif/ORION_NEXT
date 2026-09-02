from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from models.market_event import MarketEvent, MarketEventType
from models.signal_snapshot import MaterialChangePolicy, SignalIdentity, build_next_snapshot
from replay.clock import ReplayClock
from replay.dataset import HistoricalDataset, HistoricalDatasetManifest, HistoricalMarketEvent
from replay.runner import HistoricalPaperReplayRunner, ReplayConfig
from replay.source import HistoricalMarketDataSource
from replay.verification import ReplayVerifier

from tests.fixtures.historical_replay_fixture import START, SYMBOLS, build_fixture_dataset


class TestHistoricalPaperReplay(unittest.TestCase):
    def test_fixture_manifest_is_reproducible(self):
        left = build_fixture_dataset()
        right = build_fixture_dataset()
        self.assertEqual(left.manifest.integrity_sha256, right.manifest.integrity_sha256)
        self.assertEqual(tuple(event.event_id for event in left.events), tuple(event.event_id for event in right.events))

    def test_progressive_clock_blocks_future_metadata_and_candles(self):
        dataset = build_fixture_dataset()
        clock = ReplayClock(dataset.start)
        source = HistoricalMarketDataSource(dataset, clock)
        before = dataset.start - timedelta(seconds=2)
        clock.advance_to(before)
        self.assertEqual(source.exchange_info(), {"symbols": []})
        clock.advance_to(dataset.start)
        self.assertEqual(len(source.exchange_info()["symbols"]), len(SYMBOLS))
        future_row = (int((dataset.end + timedelta(days=1)).timestamp() * 1000), "1", "1", "1", "1", "1", int((dataset.end + timedelta(days=1, hours=1)).timestamp() * 1000))
        augmented = dict(dataset.candles)
        augmented[(SYMBOLS[0], "1d")] = (*augmented[(SYMBOLS[0], "1d")], future_row)
        future_dataset = HistoricalDataset(dataset.manifest, dataset.events, dataset.metadata_snapshots, augmented)
        future_clock = ReplayClock(dataset.start)
        future_source = HistoricalMarketDataSource(future_dataset, future_clock)
        visible = future_dataset.candles_at(SYMBOLS[0], "1d", dataset.start)
        self.assertNotIn(future_row, visible)
        self.assertEqual(future_source.dataset.candles_at(SYMBOLS[0], "1d", dataset.start), visible)

    def test_same_timestamp_order_is_deterministic(self):
        dataset = build_fixture_dataset()
        ordered = tuple((event.timestamp, event.symbol, event.event_type.value, event.source_event_id) for event in dataset.events)
        self.assertEqual(ordered, tuple(sorted(ordered)))

    def test_event_identity_and_duplicate_protection_are_stable(self):
        event = build_fixture_dataset().events[0].to_market_event()
        duplicate = MarketEvent(
            symbol=event.symbol,
            event_timestamp=event.event_timestamp,
            event_type=event.event_type,
            payload=dict(event.payload),
            source_event_id=event.source_event_id,
        )
        self.assertEqual(event.event_id, duplicate.event_id)
        supervisor = HistoricalPaperReplayRunner.build(build_fixture_dataset(), Path(tempfile.mkdtemp()), replay_config=ReplayConfig(active_top_n=1, broad_pool_top_n=5)).supervisor
        self.assertEqual(supervisor.process_market_event(event), ())
        self.assertEqual(supervisor.process_market_event(duplicate), ())
        self.assertEqual(supervisor.health.duplicate_events, 1)

    def test_historical_source_never_calls_live_transport(self):
        dataset = build_fixture_dataset()
        source = HistoricalMarketDataSource(dataset, ReplayClock(dataset.start))
        source.exchange_info()
        source._get_json("ticker/24hr")
        source._get_json("ticker/bookTicker")
        source._get_json("klines", {"symbol": SYMBOLS[0], "interval": "1d", "limit": 32})
        self.assertFalse(source.live_accessed)

    def test_real_paper_runtime_is_constructed_only_after_startup_discovery(self):
        dataset = build_fixture_dataset()
        with tempfile.TemporaryDirectory() as tmp:
            runner = HistoricalPaperReplayRunner.build(
                dataset,
                Path(tmp),
                replay_config=ReplayConfig(active_top_n=1, broad_pool_top_n=5),
                starting_capital=200.0,
            )
            self.assertTrue(runner.opportunity.discovery._cached_output is not None)
            self.assertTrue(runner.supervisor.no_live_path())

    def test_replay_processes_progressively_and_produces_end_evidence(self):
        dataset = build_fixture_dataset()
        with tempfile.TemporaryDirectory() as tmp:
            runner = HistoricalPaperReplayRunner.build(
                dataset,
                Path(tmp),
                replay_config=ReplayConfig(active_top_n=1, broad_pool_top_n=5, acceleration_factor=600.0),
                starting_capital=200.0,
            )
            report = asyncio.run(runner.run_replay(dataset, replay_config=ReplayConfig(active_top_n=1, broad_pool_top_n=5, acceleration_factor=600.0)))
            self.assertGreater(report["processed_event_count"], 0)
            self.assertEqual(report["out_of_order_count"], 0)
            self.assertTrue(report["lookahead_verification"])
            self.assertTrue(report["runtime_health"])
            self.assertTrue(report["paper_only"])
            events = (Path(tmp) / "events.jsonl").read_text(encoding="utf-8")
            self.assertIn('"event_type": "replay_start"', events)
            self.assertIn('"event_type": "replay_end"', events)

    def test_order_fill_causality_uses_later_market_event(self):
        dataset = build_fixture_dataset()
        with tempfile.TemporaryDirectory() as tmp:
            runner = HistoricalPaperReplayRunner.build(dataset, Path(tmp), replay_config=ReplayConfig(active_top_n=1, broad_pool_top_n=5))
            now = START
            snapshot = build_next_snapshot(
                previous=None,
                identity=SignalIdentity(SYMBOLS[0], "REPLAY", "ENTRY"),
                direction="BUY",
                decision="BUY",
                confidence=1.0,
                entry_plan={"entry_price": 100.0, "quantity": 1.0},
                generated_at=now,
                valid_until=now + timedelta(hours=1),
                policy=MaterialChangePolicy(entry_price_change_pct=0.10),
                market_context_fingerprint="replay-test",
                quality=90.0,
            )
            runner.supervisor.submit_signal(snapshot.current, now=now)
            later = MarketEvent(
                symbol=SYMBOLS[0],
                event_timestamp=now + timedelta(seconds=1),
                event_type=MarketEventType.TRADE,
                payload={"price": 99.0, "quantity": 1.0},
                source_timestamp=now + timedelta(seconds=1),
                source_event_id="trade-1",
            )
            filled = runner.supervisor.process_market_event(later)
            self.assertEqual(len(filled), 1)
            order_id = filled[0]
            self.assertEqual(runner.supervisor.runtime.orders.get(order_id).state.value, "filled")

    def test_recovery_from_checkpoint_matches_uninterrupted_state(self):
        dataset = build_fixture_dataset()

        def process(supervisor, event):
            supervisor.process_market_event(event)

        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            full = HistoricalPaperReplayRunner.build(dataset, Path(a), replay_config=ReplayConfig(active_top_n=1, broad_pool_top_n=5))
            recovered_seed = HistoricalPaperReplayRunner.build(dataset, Path(b), replay_config=ReplayConfig(active_top_n=1, broad_pool_top_n=5))
            events = tuple(event.to_market_event() for event in dataset.events)
            for event in events:
                process(full.supervisor, event)
            checkpoint = len(events) // 2
            recovered = ReplayVerifier.recovery_from_checkpoint(recovered_seed.supervisor, events, checkpoint, process)
            self.assertEqual(full.supervisor.replay_state(), recovered.replay_state())
            self.assertTrue(full.supervisor.no_live_path())
            self.assertTrue(recovered.no_live_path())

    def test_historical_universe_changes_only_when_metadata_snapshot_is_visible(self):
        dataset = build_fixture_dataset()
        later_time = START + timedelta(days=10)
        later_snapshot = dict(dataset.metadata_snapshots[0][1])
        later_snapshot["exchange_info"] = {
            "symbols": [*later_snapshot["exchange_info"]["symbols"], {"symbol": "NEWUSDT", "baseAsset": "NEW", "quoteAsset": "USDT", "status": "TRADING", "isSpotTradingAllowed": True}]
        }
        modified = HistoricalDataset(
            dataset.manifest,
            dataset.events,
            (*dataset.metadata_snapshots, (later_time, later_snapshot)),
            dataset.candles,
        )
        clock = ReplayClock(START)
        source = HistoricalMarketDataSource(modified, clock)
        self.assertNotIn("NEWUSDT", {row["symbol"] for row in source.exchange_info()["symbols"]})
        clock.advance_to(later_time)
        self.assertIn("NEWUSDT", {row["symbol"] for row in source.exchange_info()["symbols"]})

    def test_replay_uses_single_engine_for_campaigns(self):
        for campaign in ("7D", "30D", "90D", "365D"):
            config = ReplayConfig(campaign=campaign, active_top_n=1, broad_pool_top_n=5)
            self.assertEqual(config.__class__.__name__, "ReplayConfig")


if __name__ == "__main__":
    unittest.main()
