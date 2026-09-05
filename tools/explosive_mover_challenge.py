from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from models.market_event import MarketEventType
from replay.dataset import HistoricalDataset, HistoricalDatasetManifest, HistoricalMarketEvent
from replay.runner import HistoricalPaperReplayRunner, ReplayConfig

UTC = timezone.utc
API = "https://data-api.binance.vision/api/v3/klines"

# Individually validated challenge symbols. This is NOT a reconstructed universe.
CHALLENGE_SYMBOLS = (
    "TRUMPUSDT", "STXUSDT", "PEPEUSDT", "BCHUSDT", "WIFUSDT",
    "XRPUSDT", "DOGEUSDT", "ADAUSDT", "SUIUSDT", "APTUSDT",
    "UNIUSDT", "ATOMUSDT", "INJUSDT",
)

SIMULATION_START = datetime(2026, 8, 20, tzinfo=UTC)
SIMULATION_END = datetime(2026, 8, 24, 23, 59, 59, 999000, tzinfo=UTC)
WARMUP_START = SIMULATION_START - timedelta(days=40)
MOVE_THRESHOLDS = (10, 20, 30, 50, 70, 100, 150, 200)
WINDOW_STEPS = {"5m": 1, "15m": 3, "30m": 6, "1h": 12, "4h": 48, "24h": 288}
TF_MIN = {"5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}


def _ts(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).isoformat()


def _request_json(symbol: str, start_ms: int, end_ms: int) -> list:
    q = urlencode({"symbol": symbol, "interval": "5m", "startTime": start_ms, "endTime": end_ms, "limit": 1000})
    request = Request(f"{API}?{q}", headers={"User-Agent": "ORION-explosive-mover-challenge/1.0", "Accept": "application/json"})
    last_error: Exception | None = None
    for attempt in range(1, 6):
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, list):
                raise ValueError("Binance kline response was not a list")
            return payload
        except Exception as exc:
            last_error = exc
            if attempt == 5:
                break
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"historical acquisition failed for {symbol}: {last_error}")


def fetch_5m(symbol: str, start: datetime, end: datetime) -> tuple[tuple, ...]:
    cur = _ts(start)
    stop = _ts(end)
    rows: list = []
    while cur < stop:
        batch = _request_json(symbol, cur, stop)
        if not batch:
            break
        rows.extend(batch)
        nxt = int(batch[-1][0]) + 5 * 60 * 1000
        if nxt <= cur:
            raise RuntimeError(f"pagination stalled for {symbol}")
        cur = nxt
        if len(batch) < 1000:
            break
    filtered = [tuple(row) for row in rows if _ts(start) <= int(row[0]) < stop]
    dedup: dict[int, tuple] = {int(row[0]): row for row in filtered}
    return tuple(dedup[key] for key in sorted(dedup))


def aggregate(rows: tuple[tuple, ...], minutes: int) -> tuple[tuple, ...]:
    bucket_ms = minutes * 60 * 1000
    needed = minutes // 5
    groups: dict[int, list[tuple]] = defaultdict(list)
    for row in rows:
        groups[(int(row[0]) // bucket_ms) * bucket_ms].append(row)
    result: list[tuple] = []
    for bucket, group in sorted(groups.items()):
        group.sort(key=lambda r: int(r[0]))
        if len(group) != needed:
            continue
        result.append((
            bucket,
            group[0][1],
            max(float(r[2]) for r in group),
            min(float(r[3]) for r in group),
            group[-1][4],
            sum(float(r[5]) for r in group),
            bucket + bucket_ms - 1,
            "0",
            sum(int(r[8]) for r in group),
            "0", "0", "0",
        ))
    return tuple(result)


def source_references(symbol: str) -> dict[str, str]:
    return {
        "spot_kline_endpoint": f"{API}?symbol={symbol}&interval=5m&startTime=<historical>&endTime=<historical>&limit=1000",
        "binance_market_data_docs": "https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md",
        "binance_public_data": "https://github.com/binance/binance-public-data/blob/master/README.md",
    }


def acquire_dataset(root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    raw: dict[str, tuple[tuple, ...]] = {}
    validation: dict[str, dict] = {}
    for symbol in CHALLENGE_SYMBOLS:
        rows = fetch_5m(symbol, WARMUP_START, SIMULATION_END + timedelta(milliseconds=1))
        raw[symbol] = rows
        pre = [r for r in rows if int(r[0]) < _ts(SIMULATION_START)]
        period = [r for r in rows if _ts(SIMULATION_START) <= int(r[6]) <= _ts(SIMULATION_END)]
        validation[symbol] = {
            "historical_existence": bool(pre),
            "historical_period_trade": bool(period),
            "pre_start_first_observable": None if not pre else _iso(int(pre[0][0])),
            "period_first_observable": None if not period else _iso(int(period[0][0])),
            "period_last_observable": None if not period else _iso(int(period[-1][6])),
            "usdt_identity": symbol.endswith("USDT"),
            "spot_evidence": "Binance Spot 5m kline observations exist at historical timestamps",
            "status_semantics": "TRADING_OBSERVED_BY_SPOT_KLINE; historical exchangeInfo status snapshot unavailable",
            "future_exchange_info_used": False,
            "source_references": source_references(symbol),
        }
        if not all((validation[symbol]["historical_existence"], validation[symbol]["historical_period_trade"], validation[symbol]["usdt_identity"])):
            raise RuntimeError(f"challenge symbol historical validation failed: {symbol}: {validation[symbol]}")

    candles: dict[tuple[str, str], tuple[tuple, ...]] = {}
    for symbol, rows in raw.items():
        candles[(symbol, "5m")] = rows
        for tf, minutes in TF_MIN.items():
            if tf != "5m":
                candles[(symbol, tf)] = aggregate(rows, minutes)

    lo = _ts(SIMULATION_START)
    hi = _ts(SIMULATION_END)
    events: list[HistoricalMarketEvent] = []
    for symbol, rows in raw.items():
        for row in rows:
            close_ms = int(row[6])
            if lo <= close_ms <= hi:
                events.append(HistoricalMarketEvent(
                    timestamp=datetime.fromtimestamp(close_ms / 1000, tz=UTC),
                    symbol=symbol,
                    event_type=MarketEventType.CANDLE_CLOSE,
                    payload={
                        "timeframe": "5m",
                        "open_time": _iso(int(row[0])),
                        "close_time": _iso(close_ms),
                        "open": float(row[1]),
                        "high": float(row[2]),
                        "low": float(row[3]),
                        "close": float(row[4]),
                        "volume": float(row[5]),
                        "is_closed": True,
                    },
                    source_event_id=f"{symbol}:5m:{int(row[0])}",
                ))
    events = sorted(events, key=lambda e: (e.timestamp, e.symbol, e.event_type.value, e.event_id))

    metadata = ((SIMULATION_START, {
        "exchange_info": {
            "symbols": [
                {
                    "symbol": symbol,
                    "status": "TRADING",
                    "baseAsset": symbol[:-4],
                    "quoteAsset": "USDT",
                    "isSpotTradingAllowed": True,
                    "historical_evidence_basis": "Binance Spot historical kline observations; challenge-scoped, not a complete universe manifest",
                }
                for symbol in CHALLENGE_SYMBOLS
            ],
            "scope": "INDIVIDUAL_CHALLENGE_SET_ONLY",
            "universe_completeness": "NOT_ESTABLISHED",
            "current_exchange_info_used": False,
        }
    }),)

    manifest = HistoricalDatasetManifest(
        period=f"{SIMULATION_START.isoformat()}/{SIMULATION_END.isoformat()}",
        source="Binance Spot historical public market data via data-api.binance.vision; individually validated challenge set",
        symbols=CHALLENGE_SYMBOLS,
        event_types=("candle_close",),
        timeframes=tuple(TF_MIN),
        timestamp_convention="UTC milliseconds; event timestamp = 5m candle close",
        ordering_convention="timestamp,symbol,event_type,stable source id",
        dataset_version="binance-spot-explosive-challenge-v1",
        integrity_sha256="pending",
    )
    dataset = HistoricalDataset(manifest, tuple(events), metadata, candles)
    dataset.write_directory(root)
    parsed = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    parsed.update({
        "scope": "INDIVIDUAL_VALIDATED_CHALLENGE_SET",
        "universe_completeness": "NOT_ESTABLISHED",
        "challenge_symbols": list(CHALLENGE_SYMBOLS),
        "campaign_interval": f"{SIMULATION_START.isoformat()}/{SIMULATION_END.isoformat()}",
        "warmup_start": WARMUP_START.isoformat(),
        "historical_validation": validation,
        "future_exchange_info_used": False,
        "source_policy": "No current exchangeInfo, no current symbol list, no future listing/status information used for membership",
        "sha256_scope": "HistoricalDataset canonical digest in integrity_sha256",
    })
    (root / "manifest.json").write_text(json.dumps(parsed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"validation": validation, "dataset_hash": parsed["integrity_sha256"], "event_count": len(events)}


def detect_moves(dataset: HistoricalDataset) -> list[dict]:
    results: list[dict] = []
    for symbol in dataset.manifest.symbols:
        rows = dataset.candles[(symbol, "5m")]
        closes = [(int(row[6]), float(row[4])) for row in rows]
        index = {ts: i for i, (ts, _) in enumerate(closes)}
        for window, n in WINDOW_STEPS.items():
            crossed: set[int] = set()
            for ts, price in closes:
                if not (_ts(SIMULATION_START) <= ts <= _ts(SIMULATION_END)):
                    continue
                i = index[ts]
                if i < n:
                    continue
                base_ts, base_price = closes[i - n]
                if base_price <= 0:
                    continue
                move = (price / base_price - 1.0) * 100.0
                for threshold in MOVE_THRESHOLDS:
                    if threshold in crossed:
                        continue
                    if move >= threshold:
                        crossed.add(threshold)
                        results.append({
                            "symbol": symbol,
                            "window": window,
                            "threshold_pct": threshold,
                            "base_timestamp": _iso(base_ts),
                            "first_measurable_timestamp": _iso(ts),
                            "base_price": base_price,
                            "price_at_threshold": price,
                            "movement_pct": move,
                        })
    return sorted(results, key=lambda x: (x["first_measurable_timestamp"], x["symbol"], x["window"], x["threshold_pct"]))


def _serialize_candidate(candidate) -> dict:
    trace = candidate.decision_trace
    payload = {
        "symbol": candidate.symbol,
        "rank": candidate.rank,
        "opportunity_score": candidate.opportunity_score,
        "opportunity_class": candidate.opportunity_class,
        "entry_state": candidate.entry_state,
        "entry_readiness": candidate.entry_readiness,
        "entry_allowed": None if trace is None else trace.entry_allowed,
        "rejection_reasons": [] if trace is None else [getattr(r, "value", str(r)) for r in trace.rejection_reasons],
        "directional_evidence": candidate.directional_evidence,
        "recall_lanes": list(candidate.recall_lanes),
        "score_components": list(candidate.score_components),
        "eligibility_reasons": list(candidate.eligibility_reasons),
    }
    if trace is not None:
        payload["decision_trace"] = asdict(trace) if is_dataclass(trace) else str(trace)
    return payload


def _install_observer(runner: HistoricalPaperReplayRunner, observer_path: Path) -> None:
    observer_path.parent.mkdir(parents=True, exist_ok=True)
    handle = observer_path.open("w", encoding="utf-8")
    original = runner.opportunity.discover

    def wrapped(*args, **kwargs):
        result = original(*args, **kwargs)
        event = runner.supervisor.last_processed_market_event
        ts = event.event_timestamp.isoformat() if event is not None else None
        broad = tuple(result.broad_pool.candidates)
        active = {candidate.symbol for candidate in result.active_set.candidates}
        record = {
            "refresh_timestamp": ts,
            "active_symbols": sorted(active),
            "recall_counts": [list(pair) for pair in result.recall_counts],
            "recalled_provenance": [[symbol, list(lanes)] for symbol, lanes in result.recalled_provenance],
            "broad_candidates": [_serialize_candidate(candidate) | {"active": candidate.symbol in active} for candidate in broad],
        }
        handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
        handle.flush()
        return result

    runner.opportunity.discover = wrapped
    runner._challenge_observer_handle = handle  # type: ignore[attr-defined]


def _close_observer(runner: HistoricalPaperReplayRunner) -> None:
    handle = getattr(runner, "_challenge_observer_handle", None)
    if handle is not None:
        handle.close()


def parse_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_evidence(output: Path, dataset: HistoricalDataset, validation: dict, detections: list[dict], base_report: dict) -> dict:
    cycles = parse_jsonl(output / "pipeline_observations.jsonl")
    runtime_events = parse_jsonl(output / "events.jsonl")
    by_ts = {row["refresh_timestamp"]: row for row in cycles}
    signal_by_symbol: dict[str, list[dict]] = defaultdict(list)
    orders_by_symbol: dict[str, list[dict]] = defaultdict(list)
    fills_by_symbol: dict[str, list[dict]] = defaultdict(list)
    exits_by_symbol: dict[str, list[dict]] = defaultdict(list)

    for row in runtime_events:
        et = row.get("event_type")
        symbol = row.get("symbol")
        if et == "signal_event" and symbol:
            signal_by_symbol[symbol].append(row)
        elif et in {"order_lifecycle", "order_rejected"} and symbol:
            orders_by_symbol[symbol].append(row)
        elif et == "fill" and symbol:
            fills_by_symbol[symbol].append(row)
        elif et == "replay_end_position_close" and symbol:
            exits_by_symbol[symbol].append(row)

    closes = {}
    peaks = {}
    for symbol in dataset.manifest.symbols:
        rows = dataset.candles[(symbol, "5m")]
        closes[symbol] = [(int(r[6]), float(r[4])) for r in rows]
        peaks[symbol] = max((float(r[2]) for r in rows if _ts(SIMULATION_START) <= int(r[6]) <= _ts(SIMULATION_END)), default=None)

    threshold_rows: list[dict] = []
    causal: list[dict] = []
    for detection in detections:
        ts = detection["first_measurable_timestamp"]
        cycle = by_ts.get(ts)
        symbol = detection["symbol"]
        candidate = None
        if cycle:
            candidate = next((c for c in cycle["broad_candidates"] if c["symbol"] == symbol), None)
        sigs = [s for s in signal_by_symbol[symbol] if s.get("refresh_timestamp", s.get("timestamp")) <= ts]
        first_discovery = next((s for s in sigs), None)
        actionable = next((s for s in sigs if s.get("entry_allowed") is True and s.get("entry_state") in {"A", "A+"}), None)
        first_recall = next((r for r in cycles if r.get("refresh_timestamp") and r["refresh_timestamp"] <= ts and any(c["symbol"] == symbol for c in r.get("broad_candidates", []))), None)
        order = next((o for o in orders_by_symbol[symbol] if o.get("event_type") == "order_lifecycle"), None)
        fill = fills_by_symbol[symbol][0] if fills_by_symbol[symbol] else None
        exit_row = exits_by_symbol[symbol][0] if exits_by_symbol[symbol] else None

        stage = "not_recalled"
        reason = "NOT_IN_ELIGIBLE_RECALL_POOL_AT_OR_BEFORE_THRESHOLD"
        if first_recall is not None:
            cand_at_recall = next((c for c in first_recall["broad_candidates"] if c["symbol"] == symbol), None)
            if cand_at_recall:
                stage = "evaluated"
                reason = ""
                if cand_at_recall.get("entry_allowed") is False:
                    stage = "evaluated_not_actionable"
                    reason = ";".join(cand_at_recall.get("rejection_reasons", [])) or "ENTRY_NOT_ALLOWED"
                elif cand_at_recall.get("entry_allowed") is True:
                    stage = "actionable"
                    reason = ""
        if order is not None:
            stage = "ordered"
        if fill is not None:
            stage = "filled"
        if exit_row is not None:
            stage = "exited"

        market_move = detection["movement_pct"]
        observable_move = None
        discovery_timestamp = None
        actionable_timestamp = None
        for c in cycles:
            if c.get("refresh_timestamp") and c["refresh_timestamp"] <= ts:
                cand = next((cc for cc in c.get("broad_candidates", []) if cc["symbol"] == symbol), None)
                if cand:
                    if discovery_timestamp is None:
                        discovery_timestamp = c["refresh_timestamp"]
                        # price at first discovered cycle from historical close series
                        dt = datetime.fromisoformat(c["refresh_timestamp"])
                        observable_ts = int(dt.timestamp() * 1000)
                        prior = [p for t, p in closes[symbol] if t <= observable_ts]
                        if prior:
                            base = detection["base_price"]
                            observable_move = (prior[-1] / base - 1.0) * 100.0
                    if actionable_timestamp is None and cand.get("entry_allowed") is True:
                        actionable_timestamp = c["refresh_timestamp"]
        entry_price = None if order is None else order.get("price")
        exit_price = None if exit_row is None else exit_row.get("price")
        realized_return = None
        if entry_price and exit_price:
            realized_return = (float(exit_price) / float(entry_price) - 1.0) * 100.0
        peak_price = peaks[symbol]
        capture_ratio = None
        if entry_price and peak_price and peak_price > float(entry_price) and realized_return is not None:
            max_realizable = (peak_price / float(entry_price) - 1.0) * 100.0
            if max_realizable > 0:
                capture_ratio = realized_return / max_realizable

        causal_row = {
            "symbol": symbol,
            "window": detection["window"],
            "threshold_pct": detection["threshold_pct"],
            "historical_validation": validation[symbol],
            "first_measurable_timestamp": detection["first_measurable_timestamp"],
            "base_timestamp": detection["base_timestamp"],
            "market_move_pct": market_move,
            "observable_move_pct": observable_move,
            "discovery_timestamp": discovery_timestamp,
            "actionable_timestamp": actionable_timestamp,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "realized_return_pct": realized_return,
            "capture_ratio": capture_ratio,
            "detection_latency_seconds": None if discovery_timestamp is None else max(0.0, (datetime.fromisoformat(discovery_timestamp) - datetime.fromisoformat(detection["first_measurable_timestamp"])).total_seconds()),
            "decision_latency_seconds": None if discovery_timestamp is None or actionable_timestamp is None else max(0.0, (datetime.fromisoformat(actionable_timestamp) - datetime.fromisoformat(discovery_timestamp)).total_seconds()),
            "entry_latency_seconds": None,
            "stage_at_threshold": stage,
            "stage_reason": reason,
            "fast_recall_lanes": [] if candidate is None else candidate.get("recall_lanes", []),
            "deep_evaluation": candidate is not None,
            "score": None if candidate is None else candidate.get("opportunity_score"),
            "actionability": None if candidate is None else candidate.get("entry_allowed"),
            "decision_trace": None if candidate is None else candidate.get("decision_trace"),
            "order_event": order,
            "fill_event": fill,
            "exit_event": exit_row,
        }
        causal.append(causal_row)

    # Deduplicate repeated threshold rows into the required per-threshold/window table.
    table: list[dict] = []
    for threshold in MOVE_THRESHOLDS:
        for window in WINDOW_STEPS:
            subset = [d for d in detections if d["threshold_pct"] == threshold and d["window"] == window]
            validated_symbols = sorted({d["symbol"] for d in subset})
            funnel_rows = [c for c in causal if c["threshold_pct"] == threshold and c["window"] == window]
            eligible_count = sum(1 for c in funnel_rows if c["deep_evaluation"] or c["stage_at_threshold"] != "not_recalled")
            recalled_count = sum(1 for c in funnel_rows if c["fast_recall_lanes"])
            evaluated_count = sum(1 for c in funnel_rows if c["deep_evaluation"])
            actionable_count = sum(1 for c in funnel_rows if c["actionability"] is True)
            entries = sum(1 for c in funnel_rows if c["order_event"] is not None and c["order_event"].get("event_type") == "order_lifecycle")
            fills = sum(1 for c in funnel_rows if c["fill_event"] is not None)
            exits = sum(1 for c in funnel_rows if c["exit_event"] is not None)
            captured = sum(1 for c in funnel_rows if c["realized_return_pct"] is not None and c["realized_return_pct"] > 0)
            missed = len(funnel_rows) - captured
            table.append({
                "threshold_pct": threshold,
                "window": window,
                "candidate_count": len(validated_symbols),
                "historically_validated_count": len(validated_symbols),
                "eligible_count": eligible_count,
                "recalled_count": recalled_count,
                "evaluated_count": evaluated_count,
                "actionable_count": actionable_count,
                "entries": entries,
                "fills": fills,
                "exits": exits,
                "captured_count": captured,
                "missed_count": missed,
            })

    representatives: dict[str, dict | None] = {}
    representatives["strongest_validated_mover"] = max(causal, key=lambda x: float(x["market_move_pct"]), default=None)
    representatives["fastest_short_term_mover"] = min(
        [c for c in causal if c["window"] in {"5m", "15m", "30m", "1h"}],
        key=lambda x: abs((datetime.fromisoformat(x["first_measurable_timestamp"]) - datetime.fromisoformat(x["base_timestamp"])).total_seconds()),
        default=None,
    )
    representatives["mover_ge_70"] = next((c for c in causal if c["threshold_pct"] >= 70), None)
    representatives["mover_ge_100"] = next((c for c in causal if c["threshold_pct"] >= 100), None)
    representatives["failure_case"] = next((c for c in causal if c["stage_at_threshold"] in {"not_recalled", "evaluated_not_actionable"}), None)

    integrity = hashlib.sha256((output / "challenge_report.json").read_bytes()).hexdigest() if (output / "challenge_report.json").exists() else None
    report = {
        "title": "D2 EXPLOSIVE-MOVER CHALLENGE SET REPORT",
        "status": "COMPLETED",
        "scope_statement": "This test validates selected historical explosive movers only. It does not establish complete Binance-market coverage.",
        "universe_completeness": "NOT ESTABLISHED",
        "simulation_interval": f"{SIMULATION_START.isoformat()}/{SIMULATION_END.isoformat()}",
        "challenge_symbols": list(dataset.manifest.symbols),
        "challenge_symbol_count": len(dataset.manifest.symbols),
        "thresholds_pct": list(MOVE_THRESHOLDS),
        "windows": list(WINDOW_STEPS),
        "dataset_hash": dataset.manifest.integrity_sha256,
        "base_replay_report": base_report,
        "threshold_window_statistics": table,
        "causal_traces": causal,
        "representative_cases": representatives,
        "production_semantic_impact": "NONE",
        "current_exchange_info_used": False,
        "future_universe_information_used": False,
        "campaign_B": "BLOCKED",
        "broad_market_complete_universe_test": "BLOCKED",
    }
    (output / "challenge_report.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    (output / "causal_traces.json").write_text(json.dumps(causal, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    (output / "threshold_window_statistics.json").write_text(json.dumps(table, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("explosive_mover_challenge"))
    args = parser.parse_args()
    output = args.output
    dataset_root = output / "dataset"
    output.mkdir(parents=True, exist_ok=True)

    acquisition = acquire_dataset(dataset_root)
    dataset = HistoricalDataset.from_directory(dataset_root)
    detections = detect_moves(dataset)
    (output / "detected_movers.json").write_text(json.dumps(detections, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    replay_out = output / "replay"
    cfg = ReplayConfig(campaign="7D", acceleration_factor=600, end_policy="CLOSE_AT_END", active_top_n=10, broad_pool_top_n=20)
    runner = HistoricalPaperReplayRunner.build(dataset, replay_out, replay_config=cfg, starting_capital=200.0)
    observer = output / "pipeline_observations.jsonl"
    _install_observer(runner, observer)
    try:
        base_report = asyncio.run(runner.run_replay(dataset, replay_config=cfg))
    finally:
        _close_observer(runner)

    report = build_evidence(output, dataset, acquisition["validation"], detections, base_report)
    report["artifact_generation_sha256"] = hashlib.sha256((output / "challenge_report.json").read_bytes()).hexdigest()
    (output / "challenge_report.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    print("CHALLENGE_SET_COMPLETE")
    print("UNIVERSE_COMPLETENESS NOT_ESTABLISHED")
    print("CHALLENGE_SYMBOL_COUNT", len(dataset.manifest.symbols))
    print("DETECTED_MOVEMENT_ROWS", len(detections))
    print("DATASET_HASH", dataset.manifest.integrity_sha256)
    print("PROCESSED_EVENTS", base_report["processed_event_count"])
    print("ORDERS", base_report["orders"])
    print("FILLS", base_report["fills"])
    print("CLOSE_AT_END", base_report["end_of_run_policy"])
    print("LOOKAHEAD", base_report["lookahead_verification"])
    print("PAPER_ONLY", base_report["paper_only"])
    print("PRODUCTION_SEMANTIC_IMPACT NONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
