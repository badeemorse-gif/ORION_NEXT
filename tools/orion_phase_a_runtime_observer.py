"""D1 Phase A actual ORION runtime observer. Experimental / observation-only."""
from __future__ import annotations
import argparse, hashlib, json, os, secrets, sys, math
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "binansScanner"))

from core.orchestrator import Orchestrator, OrchestratorConfig, OrchestratorResult, PipelineError
from engines.analysis_engine import AnalysisEngine
from engines.decision_engine import DecisionEngine
from engines.indicator_engine import IndicatorEngine
from engines.opportunity_relative_ranking import OpportunityRankingInput, OpportunityRelativeRanker
from engines.profile_engine import ProfileEngine
from engines.score_engine import ScoreEngine
from engines.validation_engine import ValidationEngine
from enums import Timeframe
from models.market import MarketDataset
from models.opportunity import Opportunity, OpportunityDirection
from models.signal_journal import SignalJournal, SignalJournalEntry, SignalObservation
from providers.binance_provider import BinanceProvider
from providers.market_data_provider import MarketDataProvider

REQUIRED_SYMBOLS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT")
REQUIRED_TIMEFRAMES = ("1h", "4h", "1d")
UNAVAILABLE_AT_BOUNDARY = "UNAVAILABLE_AT_BOUNDARY"
OBSERVER_VERSION = "1.2.0"
BINANCE_MARKET_DATA_ONLY_URL = "https://data-api.binance.vision/api"
CLOSED_CANDLE_LOOKBACK = 250
LOOKBACK_REQUEST_BUFFER = 2
CRITICAL_PROFILE_INDICATORS = ("ema_9", "ema_20", "ema_50", "ema_100", "ema_200", "adx_14", "rsi_14", "momentum_5", "momentum_10", "mfi_14", "atr_14")
_TIMEFRAME_DELTAS = {Timeframe.H1: timedelta(hours=1), Timeframe.H4: timedelta(hours=4), Timeframe.D1: timedelta(days=1)}
_PRIMARY_TIMEFRAME_UNAVAILABLE_REASON = ("ORION runtime produced a symbol-level DecisionResult from the canonical primary timeframe; "
                                         "no independent DecisionResult exists for this timeframe.")


def _canon(x): return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
def _sha(x): return hashlib.sha256(_canon(x)).hexdigest()
def _now(): return datetime.now(timezone.utc)
def _session(): return f"EXP-{_now().strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(6)}"
def _commit(x):
    x = x.strip().lower()
    if len(x) != 40 or any(c not in "0123456789abcdef" for c in x): raise ValueError("baseline_commit must be a full 40-character Git SHA")
    return x


def _universe(symbols, tfs):
    symbols = tuple(str(x).strip().upper() for x in symbols)
    tfs = tuple(str(x).strip() for x in tfs)
    if not symbols:
        raise ValueError("symbols must contain at least one Phase-A symbol")
    unknown = tuple(x for x in symbols if x not in REQUIRED_SYMBOLS)
    if unknown:
        raise ValueError(f"symbols must be members of REQUIRED_SYMBOLS: {list(unknown)}")
    if len(set(symbols)) != len(symbols):
        raise ValueError("symbols must not contain duplicates")
    if tfs != REQUIRED_TIMEFRAMES:
        raise ValueError(f"timeframes must be exactly {list(REQUIRED_TIMEFRAMES)}")
    return symbols, tfs


class _NoOpStorage:
    def execute(self, dataset):
        if not isinstance(dataset, MarketDataset): raise TypeError("storage boundary requires MarketDataset")


class _ClosedLookbackMarketSource:
    def __init__(self, source, closed_candles=CLOSED_CANDLE_LOOKBACK):
        if closed_candles < 1: raise ValueError("closed_candles must be positive")
        self._source = source; self._mapper = source._mapper; self.closed_candles = closed_candles
    def download_timeframe(self, symbol, timeframe, limit=1000):
        request_limit = max(self.closed_candles + LOOKBACK_REQUEST_BUFFER, limit if limit < self.closed_candles else 0)
        frame = self._source.download_timeframe(symbol=symbol, timeframe=timeframe, limit=request_limit)
        delta = _TIMEFRAME_DELTAS[timeframe]; closed = frame.loc[(frame.index + delta) <= _now()]
        if len(closed) < self.closed_candles:
            raise RuntimeError(f"INSUFFICIENT_CLOSED_LOOKBACK:{symbol}:{timeframe.value}:requested={request_limit}:closed={len(closed)}:required={self.closed_candles}")
        return closed.tail(self.closed_candles).copy()


def build_runtime_orchestrator(provider, config=None):
    return Orchestrator(provider=provider, storage=_NoOpStorage(), indicator_engine=IndicatorEngine(), analysis_engine=AnalysisEngine(), profile_engine=ProfileEngine(), score_engine=ScoreEngine(), decision_engine=DecisionEngine(), validation_engine=ValidationEngine(), config=config or OrchestratorConfig())


@dataclass(frozen=True, slots=True)
class ObservationRuntimeConfig:
    baseline_commit: str; configuration: Mapping[str, Any]; configuration_fingerprint: str; universe_identity: str; session_id: str; runtime_commit: str

@dataclass(frozen=True, slots=True)
class ObservationExtraction:
    observation: SignalObservation | None; unavailable_fields: tuple[str, ...] = (); status: str = "OBSERVED"

@dataclass(frozen=True, slots=True)
class RuntimeObservationRun:
    config: ObservationRuntimeConfig; journal: SignalJournal; records: tuple[dict[str, Any], ...]; runtime_results: tuple[dict[str, Any], ...]


def create_runtime_config(*, baseline_commit, symbols, timeframes, configuration, runtime_commit=None, session_id=None):
    symbols, timeframes = _universe(symbols, timeframes); u = {"symbols": list(symbols), "timeframes": list(timeframes)}
    return ObservationRuntimeConfig(_commit(baseline_commit), dict(configuration), _sha(configuration), f"UNIV-{_sha(u)[:12]}", session_id or _session(), runtime_commit or os.environ.get("GITHUB_SHA", UNAVAILABLE_AT_BOUNDARY))


def _direction(x): return {"FAVORABLE": OpportunityDirection.LONG, "UNFAVORABLE": OpportunityDirection.SHORT}.get(x or "")

def _tf(r, tf):
    if r.profile is None: return None
    m = tuple(x for x in r.profile.timeframes if x.timeframe == tf); return m[0] if len(m) == 1 else None


def _primary_timeframe(orchestrator, result):
    """Identify the exact primary timeframe using AnalysisEngine's canonical selector."""
    if result.dataset is None: return None
    engine = getattr(orchestrator, "_analysis_engine", None); selector = getattr(engine, "_select_primary_timeframe", None)
    if callable(selector):
        _, selected = selector(result.dataset); return selected.value if selected is not None else None
    _, selected = AnalysisEngine()._select_primary_timeframe(result.dataset)
    return selected.value if selected is not None else None


def build_ranking_inputs(r, timeframes=REQUIRED_TIMEFRAMES):
    if not (r.dataset and r.profile and r.score and r.decision): return ()
    direction = _direction(r.decision.decision)
    if direction is None: return ()
    out = []
    for tf in timeframes:
        if _tf(r, tf) is None: continue
        try:
            if r.dataset.get_timeframe(Timeframe(tf)) is None: continue
        except ValueError: continue
        out.append(OpportunityRankingInput(Opportunity(r.profile.symbol, tf, direction, generated_at=r.statistics.finished_at or _now()), r.score, r.profile, r.dataset))
    return tuple(out)


def _volume(r, tf):
    try:
        f = r.dataset.get_timeframe(Timeframe(tf)) if r.dataset else None
        return None if f is None or f.dataframe.empty else float(f.dataframe["volume"].iloc[-1])
    except (AttributeError, KeyError, TypeError, ValueError): return None


def _reasons(r):
    v = []
    if r.decision: v += r.decision.reasons + r.decision.warnings
    if r.score: v += r.score.factors + r.score.warnings
    if r.analysis: v += r.analysis.signals + r.analysis.warnings
    return tuple(dict.fromkeys(str(x) for x in v if str(x)))


def _critical_indicator_status(r):
    result = {}
    if r.dataset is None: return result
    for tf in REQUIRED_TIMEFRAMES:
        frame = r.dataset.get_timeframe(Timeframe(tf))
        if frame is None:
            result[tf] = {"candles": 0, "missing": list(CRITICAL_PROFILE_INDICATORS), "non_finite": list(CRITICAL_PROFILE_INDICATORS), "finite": False, "ema_200_finite": False, "indicator_metadata_present": False}; continue
        missing = [x for x in CRITICAL_PROFILE_INDICATORS if x not in frame.dataframe.columns]; non_finite = []
        for name in CRITICAL_PROFILE_INDICATORS:
            if name not in frame.dataframe.columns: continue
            try:
                if not math.isfinite(float(frame.dataframe[name].iloc[-1])): non_finite.append(name)
            except (TypeError, ValueError): non_finite.append(name)
        metadata = frame.dataframe.attrs.get("indicator_result")
        result[tf] = {"candles": len(frame.dataframe), "missing": missing, "non_finite": non_finite, "finite": not missing and not non_finite, "ema_200_finite": "ema_200" not in missing and "ema_200" not in non_finite, "indicator_metadata_present": metadata is not None, "indicator_metadata_type": type(metadata).__name__ if metadata is not None else None, "indicator_metadata_quality": getattr(metadata, "quality", None), "indicator_failed_indicators": list(getattr(metadata, "failed_indicators", [])) if metadata is not None else []}
    return result


def _observation_common(r, tf, timestamp):
    missing = []
    if r.analysis is None: missing += ["analysis.market_state", "analysis.strength"]
    if r.profile is None: missing += ["profile.trend", "profile.trend_strength", "profile.momentum", "profile.volume_strength", "profile.volatility", "profile.volatility_level", "profile.liquidity"]
    if r.score is None: missing.append("raw_score")
    if r.decision is None: missing += ["decision", "confidence"]
    profile_tf = _tf(r, tf); vol = _volume(r, tf)
    if profile_tf is None: missing.append(f"profile.timeframe:{tf}")
    if vol is None: missing.append("volume")
    regime = r.profile.market.market_phase if r.profile else None; liquidity = profile_tf.characteristics.liquidity if profile_tf else None
    if not regime: missing.append("market_regime")
    if liquidity is None: missing.append("liquidity")
    return missing, profile_tf, vol, regime, liquidity


def extract_wait_observation(r, tf, *, timestamp):
    missing, profile_tf, vol, regime, liquidity = _observation_common(r, tf, timestamp)
    if missing: return ObservationExtraction(None, tuple(dict.fromkeys(missing)), UNAVAILABLE_AT_BOUNDARY)
    assert r.score and r.decision and profile_tf and vol is not None and liquidity is not None
    c = profile_tf.characteristics
    return ObservationExtraction(SignalObservation(timestamp=timestamp, symbol=r.profile.symbol, timeframe=tf, raw_score=float(r.score.score), directional_raw_strength=None, context_score=None, composite=None, relative_rank=None, relative_percentile=None, confidence=float(r.decision.confidence), decision="WAIT", market_regime=str(regime), volume=vol, relative_volume=None, volatility=float(c.volatility), relative_volatility=None, liquidity=float(liquidity), momentum=None, multi_timeframe_alignment=None, reasons=_reasons(r)))


def extract_observation(r, ranked, *, timestamp):
    missing, tf, vol, regime, liquidity = _observation_common(r, ranked.opportunity.timeframe, timestamp)
    if missing: return ObservationExtraction(None, tuple(dict.fromkeys(missing)), UNAVAILABLE_AT_BOUNDARY)
    assert r.score and r.decision and tf and vol is not None and liquidity is not None
    return ObservationExtraction(SignalObservation(timestamp=timestamp, symbol=ranked.opportunity.symbol, timeframe=ranked.opportunity.timeframe, raw_score=float(r.score.score), directional_raw_strength=float(ranked.directional_raw_strength), context_score=float(ranked.context_score), composite=float(ranked.composite_score), relative_rank=float(ranked.relative_rank) if ranked.relative_rank is not None else None, relative_percentile=float(ranked.percentile) if ranked.percentile is not None else None, confidence=float(r.decision.confidence), decision=r.decision.decision, market_regime=str(regime), volume=vol, relative_volume=float(ranked.context.relative_volume), volatility=float(tf.characteristics.volatility), relative_volatility=float(ranked.context.relative_volatility), liquidity=float(liquidity), momentum=float(ranked.context.momentum), multi_timeframe_alignment=f"{ranked.context.mtf_alignment:.6f}", reasons=_reasons(r)))


class PhaseARuntimeObserver:
    def __init__(self, config, *, orchestrator_factory, ranker=None): self.config = config; self.factory = orchestrator_factory; self.ranker = ranker or OpportunityRelativeRanker()

    def run(self, symbols, timeframes):
        symbols, timeframes = _universe(symbols, timeframes); results = []; runtime = []
        for symbol in symbols:
            orchestrator = self.factory()
            try:
                result = orchestrator.run(symbol, list(timeframes)); status = "SUCCESS"
            except PipelineError as exc:
                result = orchestrator.last_result()
                if result is None: raise
                status = "PIPELINE_BLOCKED"
                runtime.append({"symbol": symbol, "status": status, "stage": result.statistics.current_stage.value, "error": str(exc), "primary_timeframe": _primary_timeframe(orchestrator, result), "critical_indicators": _critical_indicator_status(result), "profile_warnings": list(result.profile.warnings) if result.profile else [], "profile_blocks": list(result.profile.blocks) if result.profile else [], "profile_status": "BLOCKED" if result.statistics.current_stage.value == "PROFILE" else ("PASS" if result.profile and result.profile.is_tradeable else "BLOCKED"), "score_status": "PRODUCED" if result.score else "NOT_PRODUCED", "decision_status": "PRODUCED" if result.decision else "NOT_PRODUCED", "execution": {"paper": False, "live": False}})
            else:
                runtime.append({"symbol": symbol, "status": status, "stage": result.statistics.current_stage.value, "primary_timeframe": _primary_timeframe(orchestrator, result), "critical_indicators": _critical_indicator_status(result), "profile_warnings": list(result.profile.warnings) if result.profile else [], "profile_blocks": list(result.profile.blocks) if result.profile else [], "profile_status": "PASS" if result.profile and result.profile.is_tradeable else "BLOCKED", "score_status": "PRODUCED" if result.score else "NOT_PRODUCED", "decision_status": "PRODUCED" if result.decision else "NOT_PRODUCED", "execution": {"paper": False, "live": False}})
            results.append((symbol, orchestrator, result))
        stamps = [r.dataset.metadata.downloaded_at for _, _, r in results if r.dataset]; ts = max(stamps) if stamps else _now(); journal = SignalJournal(); records = []
        for symbol, orchestrator, result in results:
            primary = _primary_timeframe(orchestrator, result); decision = result.decision.decision if result.decision else None; direction = _direction(decision)
            for tf in timeframes:
                if tf != primary:
                    records.append(self._unavailable(symbol, tf, ts, ("decision_result",), _PRIMARY_TIMEFRAME_UNAVAILABLE_REASON, primary_timeframe=primary))
            if primary is None:
                records.append(self._unavailable(symbol, "UNRESOLVED", ts, ("primary_timeframe",), "ORION primary analysis timeframe could not be identified.", primary_timeframe=None)); continue
            if result.statistics.current_stage.value == "PROFILE" and result.decision is None:
                records.append(self._blocked_record(symbol, primary, ts, result)); continue
            if decision == "WAIT":
                ex = extract_wait_observation(result, primary, timestamp=ts)
                if ex.observation: journal = journal.record(SignalJournalEntry(observation=ex.observation))
                records.append(self._record(ex, result, symbol, primary, ts, primary)); continue
            if direction is None:
                records.append(self._unavailable(symbol, primary, ts, ("directional_raw_strength", "context_score", "composite", "relative_rank", "relative_percentile"), "Decision did not produce a directional signal.", primary_timeframe=primary)); continue
            ranked = self.ranker.rank(build_ranking_inputs(result, (primary,)))
            item = next((x for x in ranked if x.opportunity.symbol == symbol and x.opportunity.timeframe == primary and x.opportunity.direction == direction), None)
            if item is None:
                records.append(self._unavailable(symbol, primary, ts, ("directional_raw_strength", "context_score", "composite", "relative_rank", "relative_percentile"), "Canonical D3 ranking input was unavailable for the actual primary timeframe.", primary_timeframe=primary)); continue
            ex = extract_observation(result, item, timestamp=ts)
            if ex.observation: journal = journal.record(SignalJournalEntry(observation=ex.observation))
            records.append(self._record(ex, result, symbol, primary, ts, primary))
        return RuntimeObservationRun(self.config, journal, tuple(records), tuple(runtime))

    def _unavailable(self, symbol, tf, ts, fields, reason, *, primary_timeframe):
        return {"status": UNAVAILABLE_AT_BOUNDARY, "session_id": self.config.session_id, "baseline_commit": self.config.baseline_commit, "configuration_fingerprint": self.config.configuration_fingerprint, "universe_id": self.config.universe_identity, "runtime_commit": self.config.runtime_commit, "observed_at_utc": ts.isoformat(), "symbol": symbol, "timeframe": tf, "primary_timeframe": primary_timeframe, "unavailable_fields": list(fields), "reason": reason}

    def _blocked_record(self, symbol, tf, ts, result):
        return {"status": "PIPELINE_BLOCKED", "session_id": self.config.session_id, "baseline_commit": self.config.baseline_commit, "configuration_fingerprint": self.config.configuration_fingerprint, "universe_id": self.config.universe_identity, "runtime_commit": self.config.runtime_commit, "observed_at_utc": ts.isoformat(), "symbol": symbol, "timeframe": tf, "primary_timeframe": tf, "stage": result.statistics.current_stage.value, "error": result.statistics.error_message, "profile_warnings": list(result.profile.warnings) if result.profile else [], "profile_blocks": list(result.profile.blocks) if result.profile else [], "execution": {"paper": False, "live": False}}

    def _record(self, ex, result, symbol, tf, ts, primary_timeframe):
        rec = self._unavailable(symbol, tf, ts, ex.unavailable_fields, "Canonical field was unavailable at the runtime boundary.", primary_timeframe=primary_timeframe)
        if ex.observation:
            rec["status"] = ex.status; rec["observation"] = asdict(ex.observation); rec["source_outputs"] = {"analysis": {"market_state": result.analysis.market_state, "strength": result.analysis.strength}, "profile": {"trend": result.profile.market.trend, "trend_strength": result.profile.market.trend_strength, "momentum": result.profile.market.momentum, "volume_strength": result.profile.market.volume_strength, "volatility": result.profile.market.volatility, "volatility_level": result.profile.market.volatility_level, "liquidity": result.profile.market.liquidity}, "score": {"raw_score": result.score.score, "category": result.score.category}, "decision": {"decision": result.decision.decision, "confidence": result.decision.confidence}}; rec.pop("unavailable_fields", None); rec.pop("reason", None)
        return rec


def write_artifacts(run, artifact_root, universe):
    root = artifact_root.expanduser().resolve()
    if root == ROOT or ROOT in root.parents: raise ValueError("artifact_root must be outside ORION_NEXT")
    d = root / "signal-observations" / run.config.session_id; d.mkdir(parents=True, exist_ok=False)
    def write(path, value): path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    write(d / "session.json", {"session_id": run.config.session_id, "status": "STOPPED", "observer_version": OBSERVER_VERSION, "baseline_commit": run.config.baseline_commit, "configuration_fingerprint": run.config.configuration_fingerprint, "universe_id": run.config.universe_identity, "runtime_commit": run.config.runtime_commit, "stopped_at_utc": _now().isoformat()})
    write(d / "run_config.json", {"baseline_commit": run.config.baseline_commit, "configuration": run.config.configuration, "configuration_fingerprint": run.config.configuration_fingerprint, "universe_id": run.config.universe_identity, "runtime_commit": run.config.runtime_commit, "observer_version": OBSERVER_VERSION})
    write(d / "universe_input.json", universe); write(d / "configuration_fingerprint.json", {"algorithm": "sha256", "configuration_fingerprint": run.config.configuration_fingerprint})
    (d / "runtime_results.jsonl").write_text("".join(json.dumps(x, sort_keys=True, default=str) + "\n" for x in run.runtime_results), encoding="utf-8")
    (d / "observations.jsonl").write_text("".join(json.dumps(x, sort_keys=True, default=str) + "\n" for x in run.records), encoding="utf-8")
    return d


def main(argv=None):
    parser = argparse.ArgumentParser(); parser.add_argument("--baseline", required=True); parser.add_argument("--artifact-root", required=True); parser.add_argument("--runtime-commit")
    args = parser.parse_args(argv); symbols, timeframes = _universe(REQUIRED_SYMBOLS, REQUIRED_TIMEFRAMES)
    configuration = {"observer_version": OBSERVER_VERSION, "market_source": "BINANCE_API", "symbols": list(symbols), "timeframes": list(timeframes), "lookback": {"closed_candles": CLOSED_CANDLE_LOOKBACK, "request_buffer": LOOKBACK_REQUEST_BUFFER}, "execution": {"paper": False, "live": False}, "ranking": {"cohort": ["timeframe", "direction"]}}
    config = create_runtime_config(baseline_commit=args.baseline, symbols=symbols, timeframes=timeframes, configuration=configuration, runtime_commit=args.runtime_commit)
    source = BinanceProvider(api_key=os.environ.get("BINANCE_API_KEY", ""), api_secret=os.environ.get("BINANCE_API_SECRET", ""), testnet=False); source._client._client.API_URL = BINANCE_MARKET_DATA_ONLY_URL
    provider = MarketDataProvider(source=_ClosedLookbackMarketSource(source, CLOSED_CANDLE_LOOKBACK))
    run = PhaseARuntimeObserver(config, orchestrator_factory=lambda: build_runtime_orchestrator(provider)).run(symbols, timeframes)
    artifact_dir = write_artifacts(run, Path(args.artifact_root), {"symbols": list(symbols), "timeframes": list(timeframes)})
    observed = sum(x.get("status") == "OBSERVED" for x in run.records); unavailable = sum(x.get("status") == UNAVAILABLE_AT_BOUNDARY for x in run.records); blocked = sum(x.get("status") == "PIPELINE_BLOCKED" for x in run.records)
    allowed_runtime = all(x.get("status") == "SUCCESS" or (x.get("status") == "PIPELINE_BLOCKED" and x.get("stage") == "PROFILE") for x in run.runtime_results)
    complete_matrix = observed + unavailable + blocked == len(symbols) * len(timeframes)
    payload = {"status": "PASS" if complete_matrix and allowed_runtime else "FAIL", "session_id": config.session_id, "observations": observed, "boundary_unavailable": unavailable, "blocked_records": blocked, "closed_candles": CLOSED_CANDLE_LOOKBACK, "artifact_directory": str(artifact_dir), "primary_timeframes": {x["symbol"]: x.get("primary_timeframe") for x in run.runtime_results}}
    print(json.dumps(payload, sort_keys=True)); return 0 if complete_matrix and allowed_runtime else 2

if __name__ == "__main__": raise SystemExit(main())
