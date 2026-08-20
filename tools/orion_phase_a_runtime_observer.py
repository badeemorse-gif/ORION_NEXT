"""D1 Phase A actual ORION runtime observer. Experimental / observation-only."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import secrets
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "binansScanner"))

from core.orchestrator import Orchestrator, OrchestratorConfig, OrchestratorResult, PipelineError  # noqa: E402
from engines.analysis_engine import AnalysisEngine  # noqa: E402
from engines.decision_engine import DecisionEngine  # noqa: E402
from engines.indicator_engine import IndicatorEngine  # noqa: E402
from engines.profile_engine import ProfileEngine  # noqa: E402
from engines.score_engine import ScoreEngine  # noqa: E402
from engines.validation_engine import ValidationEngine  # noqa: E402
from enums import Timeframe  # noqa: E402
from models.market import MarketDataset  # noqa: E402
from models.signal_journal import SignalJournal, SignalJournalEntry, SignalObservation  # noqa: E402
from providers.binance_provider import BinanceProvider  # noqa: E402
from providers.market_data_provider import MarketDataProvider  # noqa: E402

REQUIRED_SYMBOLS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT")
REQUIRED_TIMEFRAMES = ("1h", "4h", "1d")
UNAVAILABLE_AT_BOUNDARY = "UNAVAILABLE_AT_BOUNDARY"
OBSERVER_VERSION = "1.3.0"
BINANCE_MARKET_DATA_ONLY_URL = "https://data-api.binance.vision/api"
CLOSED_CANDLE_LOOKBACK = 250
LOOKBACK_REQUEST_BUFFER = 2
CRITICAL_PROFILE_INDICATORS = (
    "ema_9", "ema_20", "ema_50", "ema_100", "ema_200",
    "adx_14", "rsi_14", "momentum_5", "momentum_10", "mfi_14", "atr_14",
)
_TIMEFRAME_DELTAS = {
    Timeframe.H1: timedelta(hours=1),
    Timeframe.H4: timedelta(hours=4),
    Timeframe.D1: timedelta(days=1),
}
_PRIMARY_TIMEFRAME_UNAVAILABLE_REASON = (
    "ORION runtime produced a symbol-level DecisionResult from the canonical primary timeframe; "
    "no independent DecisionResult exists for this timeframe."
)


def _canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _sha(value: Any) -> str:
    return hashlib.sha256(_canon(value)).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _session() -> str:
    return f"EXP-{_now().strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(6)}"


def _commit(value: str) -> str:
    value = value.strip().lower()
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("baseline_commit must be a full 40-character Git SHA")
    return value


def _universe(symbols, timeframes):
    symbols = tuple(str(value).strip().upper() for value in symbols)
    timeframes = tuple(str(value).strip() for value in timeframes)
    if not symbols:
        raise ValueError("symbols must not be empty")
    if len(symbols) != len(set(symbols)):
        raise ValueError("symbols must not contain duplicates")
    if any(symbol not in REQUIRED_SYMBOLS for symbol in symbols):
        raise ValueError(f"symbols must be members of {list(REQUIRED_SYMBOLS)}")
    if timeframes != REQUIRED_TIMEFRAMES:
        raise ValueError(f"timeframes must be exactly {list(REQUIRED_TIMEFRAMES)}")
    return symbols, timeframes


class _NoOpStorage:
    def execute(self, dataset):
        if not isinstance(dataset, MarketDataset):
            raise TypeError("storage boundary requires MarketDataset")


class _ClosedLookbackMarketSource:
    def __init__(self, source, closed_candles=CLOSED_CANDLE_LOOKBACK):
        if closed_candles < 1:
            raise ValueError("closed_candles must be positive")
        self._source = source
        self._mapper = source._mapper
        self.closed_candles = closed_candles

    def download_timeframe(self, symbol, timeframe, limit=1000):
        request_limit = max(
            self.closed_candles + LOOKBACK_REQUEST_BUFFER,
            limit if limit < self.closed_candles else 0,
        )
        frame = self._source.download_timeframe(symbol=symbol, timeframe=timeframe, limit=request_limit)
        delta = _TIMEFRAME_DELTAS[timeframe]
        closed = frame.loc[(frame.index + delta) <= _now()]
        if len(closed) < self.closed_candles:
            raise RuntimeError(
                f"INSUFFICIENT_CLOSED_LOOKBACK:{symbol}:{timeframe.value}:"
                f"requested={request_limit}:closed={len(closed)}:required={self.closed_candles}"
            )
        return closed.tail(self.closed_candles).copy()


def build_runtime_orchestrator(provider, config=None):
    return Orchestrator(
        provider=provider,
        storage=_NoOpStorage(),
        indicator_engine=IndicatorEngine(),
        analysis_engine=AnalysisEngine(),
        profile_engine=ProfileEngine(),
        score_engine=ScoreEngine(),
        decision_engine=DecisionEngine(),
        validation_engine=ValidationEngine(),
        config=config or OrchestratorConfig(),
    )


@dataclass(frozen=True, slots=True)
class ObservationRuntimeConfig:
    baseline_commit: str
    configuration: Mapping[str, Any]
    configuration_fingerprint: str
    universe_identity: str
    session_id: str
    runtime_commit: str


@dataclass(frozen=True, slots=True)
class ObservationExtraction:
    observation: SignalObservation | None
    unavailable_fields: tuple[str, ...] = ()
    status: str = "OBSERVED"


@dataclass(frozen=True, slots=True)
class RuntimeObservationRun:
    config: ObservationRuntimeConfig
    journal: SignalJournal
    records: tuple[dict[str, Any], ...]
    runtime_results: tuple[dict[str, Any], ...]


def create_runtime_config(*, baseline_commit, symbols, timeframes, configuration, runtime_commit=None, session_id=None):
    symbols, timeframes = _universe(symbols, timeframes)
    universe = {"symbols": list(symbols), "timeframes": list(timeframes)}
    return ObservationRuntimeConfig(
        _commit(baseline_commit),
        dict(configuration),
        _sha(configuration),
        f"UNIV-{_sha(universe)[:12]}",
        session_id or _session(),
        runtime_commit or os.environ.get("GITHUB_SHA", UNAVAILABLE_AT_BOUNDARY),
    )


def _tf(result: OrchestratorResult, timeframe: str):
    if result.profile is None:
        return None
    matches = tuple(x for x in result.profile.timeframes if x.timeframe == timeframe)
    return matches[0] if len(matches) == 1 else None


def _primary_timeframe(orchestrator, result):
    if result.dataset is None:
        return None
    engine = getattr(orchestrator, "_analysis_engine", None)
    selector = getattr(engine, "_select_primary_timeframe", None)
    if not callable(selector):
        return None
    _, selected = selector(result.dataset)
    return selected.value if selected is not None else None


def _volume(result, timeframe):
    try:
        frame = result.dataset.get_timeframe(Timeframe(timeframe)) if result.dataset else None
        if frame is None or frame.dataframe.empty:
            return None
        return float(frame.dataframe["volume"].iloc[-1])
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def _reasons(result):
    reasons = []
    if result.decision:
        reasons.extend(result.decision.reasons)
        reasons.extend(result.decision.warnings)
    if result.score:
        reasons.extend(result.score.factors)
        reasons.extend(result.score.warnings)
    if result.analysis:
        reasons.extend(result.analysis.signals)
        reasons.extend(result.analysis.warnings)
    return tuple(dict.fromkeys(str(value) for value in reasons if str(value)))


def _critical_indicator_status(result):
    status = {}
    if result.dataset is None:
        return status
    for timeframe in REQUIRED_TIMEFRAMES:
        frame = result.dataset.get_timeframe(Timeframe(timeframe))
        if frame is None:
            status[timeframe] = {
                "candles": 0,
                "missing": list(CRITICAL_PROFILE_INDICATORS),
                "non_finite": list(CRITICAL_PROFILE_INDICATORS),
                "finite": False,
                "ema_200_finite": False,
                "indicator_metadata_present": False,
            }
            continue
        missing = [name for name in CRITICAL_PROFILE_INDICATORS if name not in frame.dataframe.columns]
        non_finite = []
        for name in CRITICAL_PROFILE_INDICATORS:
            if name not in frame.dataframe.columns:
                continue
            try:
                if not math.isfinite(float(frame.dataframe[name].iloc[-1])):
                    non_finite.append(name)
            except (TypeError, ValueError):
                non_finite.append(name)
        metadata = frame.dataframe.attrs.get("indicator_result")
        status[timeframe] = {
            "candles": len(frame.dataframe),
            "missing": missing,
            "non_finite": non_finite,
            "finite": not missing and not non_finite,
            "ema_200_finite": "ema_200" not in missing and "ema_200" not in non_finite,
            "indicator_metadata_present": metadata is not None,
            "indicator_metadata_type": type(metadata).__name__ if metadata is not None else None,
            "indicator_metadata_quality": getattr(metadata, "quality", None),
            "indicator_failed_indicators": list(getattr(metadata, "failed_indicators", [])) if metadata is not None else [],
        }
    return status


def _observation_common(result, timeframe):
    missing = []
    if result.analysis is None:
        missing.extend(["analysis.market_state", "analysis.strength"])
    if result.profile is None:
        missing.extend([
            "profile.trend", "profile.trend_strength", "profile.momentum",
            "profile.volume_strength", "profile.volatility", "profile.volatility_level",
            "profile.liquidity",
        ])
    if result.score is None:
        missing.append("raw_score")
    if result.decision is None:
        missing.extend(["decision", "confidence"])
    profile_tf = _tf(result, timeframe)
    volume = _volume(result, timeframe)
    if profile_tf is None:
        missing.append(f"profile.timeframe:{timeframe}")
    if volume is None:
        missing.append("volume")
    regime = result.profile.market.market_phase if result.profile else None
    liquidity = profile_tf.characteristics.liquidity if profile_tf else None
    if not regime:
        missing.append("market_regime")
    if liquidity is None:
        missing.append("liquidity")
    return missing, profile_tf, volume, regime, liquidity


def extract_wait_observation(result, timeframe, *, timestamp):
    missing, profile_tf, volume, regime, liquidity = _observation_common(result, timeframe)
    if missing:
        return ObservationExtraction(None, tuple(dict.fromkeys(missing)), UNAVAILABLE_AT_BOUNDARY)
    assert result.score and result.decision and profile_tf and volume is not None and liquidity is not None
    characteristics = profile_tf.characteristics
    return ObservationExtraction(
        SignalObservation(
            observation_id=f"{result.profile.symbol}:{timeframe}:{timestamp.isoformat()}",
            timestamp=timestamp,
            symbol=result.profile.symbol,
            timeframe=timeframe,
            raw_score=float(result.score.score),
            directional_raw_strength=None,
            context_score=None,
            composite=None,
            relative_rank=None,
            relative_percentile=None,
            confidence=float(result.decision.confidence),
            decision="WAIT",
            market_regime=str(regime),
            volume=volume,
            relative_volume=None,
            volatility=float(characteristics.volatility),
            relative_volatility=None,
            liquidity=float(liquidity),
            momentum=None,
            multi_timeframe_alignment=None,
            reasons=_reasons(result),
        )
    )


def extract_observation(result, timeframe, *, timestamp):
    missing, profile_tf, volume, regime, liquidity = _observation_common(result, timeframe)
    if missing:
        return ObservationExtraction(None, tuple(dict.fromkeys(missing)), UNAVAILABLE_AT_BOUNDARY)
    assert result.score and result.decision and profile_tf and volume is not None and liquidity is not None
    characteristics = profile_tf.characteristics
    return ObservationExtraction(
        SignalObservation(
            observation_id=f"{result.profile.symbol}:{timeframe}:{timestamp.isoformat()}",
            timestamp=timestamp,
            symbol=result.profile.symbol,
            timeframe=timeframe,
            raw_score=float(result.score.score),
            directional_raw_strength=None,
            context_score=None,
            composite=None,
            relative_rank=None,
            relative_percentile=None,
            confidence=float(result.decision.confidence),
            decision=result.decision.decision,
            market_regime=str(regime),
            volume=volume,
            relative_volume=None,
            volatility=float(characteristics.volatility),
            relative_volatility=None,
            liquidity=float(liquidity),
            momentum=None,
            multi_timeframe_alignment=None,
            reasons=_reasons(result),
        )
    )


class PhaseARuntimeObserver:
    def __init__(self, config, *, orchestrator_factory, ranker=None):
        self.config = config
        self.factory = orchestrator_factory

    def run(self, symbols, timeframes):
        symbols, timeframes = _universe(symbols, timeframes)
        results = []
        runtime = []
        for symbol in symbols:
            orchestrator = self.factory()
            try:
                result = orchestrator.run(symbol, list(timeframes))
                status = "SUCCESS"
            except PipelineError as exc:
                result = orchestrator.last_result()
                if result is None:
                    raise
                status = "PIPELINE_BLOCKED"
                runtime.append({"symbol": symbol, "status": status, "stage": result.statistics.current_stage.value, "error": str(exc), "primary_timeframe": _primary_timeframe(orchestrator, result), "critical_indicators": _critical_indicator_status(result), "profile_warnings": list(result.profile.warnings) if result.profile else [], "profile_blocks": list(result.profile.blocks) if result.profile else [], "profile_status": "BLOCKED" if result.statistics.current_stage.value == "PROFILE" else ("PASS" if result.profile and result.profile.is_tradeable else "BLOCKED"), "score_status": "PRODUCED" if result.score else "NOT_PRODUCED", "decision_status": "PRODUCED" if result.decision else "NOT_PRODUCED", "execution": {"paper": False, "live": False}})
            else:
                runtime.append({"symbol": symbol, "status": status, "stage": result.statistics.current_stage.value, "primary_timeframe": _primary_timeframe(orchestrator, result), "critical_indicators": _critical_indicator_status(result), "profile_warnings": list(result.profile.warnings) if result.profile else [], "profile_blocks": list(result.profile.blocks) if result.profile else [], "profile_status": "PASS" if result.profile and result.profile.is_tradeable else "BLOCKED", "score_status": "PRODUCED" if result.score else "NOT_PRODUCED", "decision_status": "PRODUCED" if result.decision else "NOT_PRODUCED", "execution": {"paper": False, "live": False}})
            results.append((symbol, orchestrator, result))

        stamps = [result.dataset.metadata.downloaded_at for _, _, result in results if result.dataset]
        timestamp = max(stamps) if stamps else _now()
        journal = SignalJournal()
        records = []

        for symbol, orchestrator, result in results:
            primary = _primary_timeframe(orchestrator, result)
            decision = result.decision.decision if result.decision else None
            if result.statistics.current_stage.value == "PROFILE" and result.decision is None:
                records.append(self._blocked_record(symbol, primary, timestamp, result))
                continue
            for timeframe in timeframes:
                if timeframe != primary:
                    records.append(self._unavailable(symbol, timeframe, timestamp, ("decision_result",), _PRIMARY_TIMEFRAME_UNAVAILABLE_REASON, primary_timeframe=primary))
            if primary is None:
                records.append(self._unavailable(symbol, "UNRESOLVED", timestamp, ("primary_timeframe",), "ORION primary analysis timeframe could not be identified.", primary_timeframe=None))
                continue
            if decision == "WAIT":
                extraction = extract_wait_observation(result, primary, timestamp=timestamp)
            elif decision in {"FAVORABLE", "UNFAVORABLE"}:
                extraction = extract_observation(result, primary, timestamp=timestamp)
            else:
                extraction = ObservationExtraction(None, ("decision",), UNAVAILABLE_AT_BOUNDARY)
            if extraction.observation is not None:
                journal = journal.record(SignalJournalEntry(observation=extraction.observation))
            records.append(self._record(extraction, result, symbol, primary, timestamp, primary))
        return RuntimeObservationRun(self.config, journal, tuple(records), tuple(runtime))

    def _unavailable(self, symbol, timeframe, timestamp, fields, reason, *, primary_timeframe):
        return {"status": UNAVAILABLE_AT_BOUNDARY, "session_id": self.config.session_id, "baseline_commit": self.config.baseline_commit, "configuration_fingerprint": self.config.configuration_fingerprint, "universe_id": self.config.universe_identity, "runtime_commit": self.config.runtime_commit, "observed_at_utc": timestamp.isoformat(), "symbol": symbol, "timeframe": timeframe, "primary_timeframe": primary_timeframe, "unavailable_fields": list(fields), "reason": reason}

    def _blocked_record(self, symbol, timeframe, timestamp, result):
        return {"status": "PIPELINE_BLOCKED", "session_id": self.config.session_id, "baseline_commit": self.config.baseline_commit, "configuration_fingerprint": self.config.configuration_fingerprint, "universe_id": self.config.universe_identity, "runtime_commit": self.config.runtime_commit, "observed_at_utc": timestamp.isoformat(), "symbol": symbol, "timeframe": timeframe, "primary_timeframe": timeframe, "stage": result.statistics.current_stage.value, "error": result.statistics.error_message, "profile_warnings": list(result.profile.warnings) if result.profile else [], "profile_blocks": list(result.profile.blocks) if result.profile else [], "execution": {"paper": False, "live": False}}

    def _record(self, extraction, result, symbol, timeframe, timestamp, primary_timeframe):
        record = self._unavailable(symbol, timeframe, timestamp, extraction.unavailable_fields, "Canonical field was unavailable at the runtime boundary.", primary_timeframe=primary_timeframe)
        if extraction.observation is not None:
            record["status"] = extraction.status
            record["observation"] = asdict(extraction.observation)
            record["source_outputs"] = {"analysis": {"market_state": result.analysis.market_state, "strength": result.analysis.strength}, "profile": {"trend": result.profile.market.trend, "trend_strength": result.profile.market.trend_strength, "momentum": result.profile.market.momentum, "volume_strength": result.profile.market.volume_strength, "volatility": result.profile.market.volatility, "volatility_level": result.profile.market.volatility_level, "liquidity": result.profile.market.liquidity}, "score": {"raw_score": result.score.score, "category": result.score.category}, "decision": {"decision": result.decision.decision, "confidence": result.decision.confidence}}
            record.pop("unavailable_fields", None)
            record.pop("reason", None)
        return record


def write_artifacts(run, artifact_root, universe):
    root = artifact_root.expanduser().resolve()
    if root == ROOT or ROOT in root.parents:
        raise ValueError("artifact_root must be outside ORION_NEXT")
    directory = root / "signal-observations" / run.config.session_id
    directory.mkdir(parents=True, exist_ok=False)
    def write(path, value): path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    write(directory / "session.json", {"session_id": run.config.session_id, "status": "STOPPED", "observer_version": OBSERVER_VERSION, "baseline_commit": run.config.baseline_commit, "configuration_fingerprint": run.config.configuration_fingerprint, "universe_id": run.config.universe_identity, "runtime_commit": run.config.runtime_commit, "stopped_at_utc": _now().isoformat()})
    write(directory / "run_config.json", {"baseline_commit": run.config.baseline_commit, "configuration": run.config.configuration, "configuration_fingerprint": run.config.configuration_fingerprint, "universe_id": run.config.universe_identity, "runtime_commit": run.config.runtime_commit, "observer_version": OBSERVER_VERSION})
    write(directory / "universe_input.json", universe)
    write(directory / "configuration_fingerprint.json", {"algorithm": "sha256", "configuration_fingerprint": run.config.configuration_fingerprint})
    (directory / "runtime_results.jsonl").write_text("".join(json.dumps(value, sort_keys=True, default=str) + "\n" for value in run.runtime_results), encoding="utf-8")
    (directory / "observations.jsonl").write_text("".join(json.dumps(value, sort_keys=True, default=str) + "\n" for value in run.records), encoding="utf-8")
    return directory


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--runtime-commit")
    args = parser.parse_args(argv)
    symbols, timeframes = _universe(REQUIRED_SYMBOLS, REQUIRED_TIMEFRAMES)
    configuration = {"observer_version": OBSERVER_VERSION, "market_source": "BINANCE_API", "symbols": list(symbols), "timeframes": list(timeframes), "lookback": {"closed_candles": CLOSED_CANDLE_LOOKBACK, "request_buffer": LOOKBACK_REQUEST_BUFFER}, "execution": {"paper": False, "live": False}, "ranking": {"status": "DEFERRED", "reason": "D3 is deferred; ranking boundary is not consumed by the observer."}}
    config = create_runtime_config(baseline_commit=args.baseline, symbols=symbols, timeframes=timeframes, configuration=configuration, runtime_commit=args.runtime_commit)
    source = BinanceProvider(api_key=os.environ.get("BINANCE_API_KEY", ""), api_secret=os.environ.get("BINANCE_API_SECRET", ""), testnet=False)
    source._client._client.API_URL = BINANCE_MARKET_DATA_ONLY_URL
    provider = MarketDataProvider(source=_ClosedLookbackMarketSource(source, CLOSED_CANDLE_LOOKBACK))
    run = PhaseARuntimeObserver(config, orchestrator_factory=lambda: build_runtime_orchestrator(provider)).run(symbols, timeframes)
    artifact_dir = write_artifacts(run, Path(args.artifact_root), {"symbols": list(symbols), "timeframes": list(timeframes)})
    observed = sum(value.get("status") == "OBSERVED" for value in run.records)
    unavailable = sum(value.get("status") == UNAVAILABLE_AT_BOUNDARY for value in run.records)
    blocked = sum(value.get("status") == "PIPELINE_BLOCKED" for value in run.records)
    allowed_runtime = all(value.get("status") == "SUCCESS" or (value.get("status") == "PIPELINE_BLOCKED" and value.get("stage") == "PROFILE") for value in run.runtime_results)
    complete_matrix = observed + unavailable + blocked == len(symbols) * len(timeframes)
    primary_bound = all(value.get("primary_timeframe") in REQUIRED_TIMEFRAMES for value in run.runtime_results)
    payload = {"status": "PASS" if complete_matrix and allowed_runtime and primary_bound else "FAIL", "session_id": config.session_id, "observations": observed, "boundary_unavailable": unavailable, "blocked_records": blocked, "closed_candles": CLOSED_CANDLE_LOOKBACK, "artifact_directory": str(artifact_dir), "primary_timeframes": {value["symbol"]: value.get("primary_timeframe") for value in run.runtime_results}, "d3_status": "DEFERRED"}
    print(json.dumps(payload, sort_keys=True))
    return 0 if complete_matrix and allowed_runtime and primary_bound else 2

if __name__ == "__main__": raise SystemExit(main())
