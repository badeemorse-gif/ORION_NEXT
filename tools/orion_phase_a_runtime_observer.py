"""D1 Phase A actual ORION runtime observer. Experimental / observation-only."""
from __future__ import annotations
import argparse, hashlib, json, os, secrets, sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "binansScanner"))
from core.orchestrator import Orchestrator, OrchestratorConfig, OrchestratorResult, PipelineError
from engines.analysis_engine import AnalysisEngine
from engines.decision_engine import DecisionEngine
from engines.indicator_engine import IndicatorEngine
from engines.opportunity_relative_ranking import OpportunityRankingInput, OpportunityRelativeRanker, RankedOpportunity
from engines.profile_engine import ProfileEngine
from engines.score_engine import ScoreEngine
from engines.validation_engine import ValidationEngine
from enums import Timeframe
from models.market import MarketDataset
from models.opportunity import Opportunity, OpportunityDirection
from models.signal_journal import SignalJournal, SignalJournalEntry, SignalObservation
from providers.binance_provider import BinanceProvider
from providers.market_data_provider import MarketDataProvider
REQUIRED_SYMBOLS = ("BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","ADAUSDT")
REQUIRED_TIMEFRAMES = ("1h","4h","1d")
UNAVAILABLE_AT_BOUNDARY = "UNAVAILABLE_AT_BOUNDARY"
OBSERVER_VERSION = "1.0.0"
BINANCE_MARKET_DATA_ONLY_URL = "https://data-api.binance.vision/api"
def _canon(x: Any) -> bytes: return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
def _sha(x: Any) -> str: return hashlib.sha256(_canon(x)).hexdigest()
def _now() -> datetime: return datetime.now(timezone.utc)
def _session() -> str: return f"EXP-{_now().strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(6)}"
def _commit(x: str) -> str:
    x=x.strip().lower()
    if len(x)!=40 or any(c not in "0123456789abcdef" for c in x): raise ValueError("baseline_commit must be a full 40-character Git SHA")
    return x
def _universe(symbols: Sequence[str],tfs: Sequence[str]):
    symbols=tuple(str(x).strip().upper() for x in symbols); tfs=tuple(str(x).strip() for x in tfs)
    if symbols!=REQUIRED_SYMBOLS: raise ValueError(f"symbols must be exactly {list(REQUIRED_SYMBOLS)}")
    if tfs!=REQUIRED_TIMEFRAMES: raise ValueError(f"timeframes must be exactly {list(REQUIRED_TIMEFRAMES)}")
    return symbols,tfs
class _NoOpStorage:
    def execute(self,dataset: MarketDataset)->None:
        if not isinstance(dataset,MarketDataset): raise TypeError("storage boundary requires MarketDataset")
def build_runtime_orchestrator(provider: MarketDataProvider,config: OrchestratorConfig|None=None)->Orchestrator:
    return Orchestrator(provider=provider,storage=_NoOpStorage(),indicator_engine=IndicatorEngine(),analysis_engine=AnalysisEngine(),profile_engine=ProfileEngine(),score_engine=ScoreEngine(),decision_engine=DecisionEngine(),validation_engine=ValidationEngine(),config=config or OrchestratorConfig())
@dataclass(frozen=True,slots=True)
class ObservationRuntimeConfig:
    baseline_commit:str; configuration:Mapping[str,Any]; configuration_fingerprint:str; universe_identity:str; session_id:str; runtime_commit:str
@dataclass(frozen=True,slots=True)
class ObservationExtraction:
    observation:SignalObservation|None; unavailable_fields:tuple[str,...]=(); status:str="OBSERVED"
@dataclass(frozen=True,slots=True)
class RuntimeObservationRun:
    config:ObservationRuntimeConfig; journal:SignalJournal; records:tuple[dict[str,Any],...]; runtime_results:tuple[dict[str,Any],...]
def create_runtime_config(*,baseline_commit:str,symbols:Sequence[str],timeframes:Sequence[str],configuration:Mapping[str,Any],runtime_commit:str|None=None,session_id:str|None=None)->ObservationRuntimeConfig:
    symbols,timeframes=_universe(symbols,timeframes); u={"symbols":list(symbols),"timeframes":list(timeframes)}
    return ObservationRuntimeConfig(_commit(baseline_commit),dict(configuration),_sha(configuration),f"UNIV-{_sha(u)[:12]}",session_id or _session(),runtime_commit or os.environ.get("GITHUB_SHA",UNAVAILABLE_AT_BOUNDARY))
def _direction(x:str|None): return {"FAVORABLE":OpportunityDirection.LONG,"UNFAVORABLE":OpportunityDirection.SHORT}.get(x or "")
def _tf(r:OrchestratorResult,tf:str):
    if r.profile is None:return None
    m=tuple(x for x in r.profile.timeframes if x.timeframe==tf); return m[0] if len(m)==1 else None
def build_ranking_inputs(r:OrchestratorResult,timeframes:Sequence[str]=REQUIRED_TIMEFRAMES):
    if not(r.dataset and r.profile and r.score and r.decision):return ()
    direction=_direction(r.decision.decision)
    if direction is None:return ()
    out=[]
    for tf in timeframes:
        if _tf(r,tf) is None:continue
        try:
            if r.dataset.get_timeframe(Timeframe(tf)) is None:continue
        except ValueError:continue
        out.append(OpportunityRankingInput(Opportunity(r.profile.symbol,tf,direction,generated_at=r.statistics.finished_at or _now()),r.score,r.profile,r.dataset))
    return tuple(out)
def _volume(r:OrchestratorResult,tf:str):
    try:
        f=r.dataset.get_timeframe(Timeframe(tf)) if r.dataset else None
        return None if f is None or f.dataframe.empty else float(f.dataframe["volume"].iloc[-1])
    except (AttributeError,KeyError,TypeError,ValueError):return None
def _reasons(r:OrchestratorResult):
    v=[]
    if r.decision:v+=r.decision.reasons+r.decision.warnings
    if r.score:v+=r.score.factors+r.score.warnings
    if r.analysis:v+=r.analysis.signals+r.analysis.warnings
    return tuple(dict.fromkeys(str(x) for x in v if str(x)))
def extract_observation(r:OrchestratorResult,ranked:RankedOpportunity,*,timestamp:datetime):
    missing=[]
    if r.analysis is None:missing += ["analysis.market_state","analysis.strength"]
    if r.profile is None:missing += ["profile.trend","profile.trend_strength","profile.momentum","profile.volume_strength","profile.volatility","profile.volatility_level","profile.liquidity"]
    if r.score is None:missing.append("raw_score")
    if r.decision is None:missing += ["decision","confidence"]
    tf=_tf(r,ranked.opportunity.timeframe); vol=_volume(r,ranked.opportunity.timeframe)
    if tf is None:missing.append(f"profile.timeframe:{ranked.opportunity.timeframe}")
    if vol is None:missing.append("volume")
    regime=r.profile.market.market_phase if r.profile else None; liquidity=tf.characteristics.liquidity if tf else None
    if not regime:missing.append("market_regime")
    if liquidity is None:missing.append("liquidity")
    if missing:return ObservationExtraction(None,tuple(dict.fromkeys(missing)),UNAVAILABLE_AT_BOUNDARY)
    assert r.score and r.decision and tf and vol is not None and liquidity is not None
    return ObservationExtraction(SignalObservation(timestamp=timestamp,symbol=ranked.opportunity.symbol,timeframe=ranked.opportunity.timeframe,raw_score=float(r.score.score),directional_raw_strength=float(ranked.directional_raw_strength),context_score=float(ranked.context_score),composite=float(ranked.composite_score),relative_rank=float(ranked.relative_rank) if ranked.relative_rank is not None else None,relative_percentile=float(ranked.percentile) if ranked.percentile is not None else None,confidence=float(r.decision.confidence),decision=r.decision.decision,market_regime=str(regime),volume=vol,relative_volume=float(ranked.context.relative_volume),volatility=float(tf.characteristics.volatility),relative_volatility=float(ranked.context.relative_volatility),liquidity=float(liquidity),momentum=float(ranked.context.momentum),multi_timeframe_alignment=f"{ranked.context.mtf_alignment:.6f}",reasons=_reasons(r)))
class PhaseARuntimeObserver:
    def __init__(self,config:ObservationRuntimeConfig,*,orchestrator_factory:Callable[[],Orchestrator],ranker:OpportunityRelativeRanker|None=None):self.config=config;self.factory=orchestrator_factory;self.ranker=ranker or OpportunityRelativeRanker()
    def run(self,symbols:Sequence[str],timeframes:Sequence[str]):
        symbols,timeframes=_universe(symbols,timeframes);results=[];runtime=[]
        for symbol in symbols:
            o=self.factory()
            try:r=o.run(symbol,list(timeframes));runtime.append({"symbol":symbol,"status":"SUCCESS","stage":r.statistics.current_stage.value})
            except PipelineError as exc:
                r=o.last_result()
                if r is None:raise
                runtime.append({"symbol":symbol,"status":"PIPELINE_BLOCKED","stage":r.statistics.current_stage.value,"error":str(exc)})
            results.append((symbol,r))
        stamps=[r.dataset.metadata.downloaded_at for _,r in results if r.dataset]; ts=max(stamps) if stamps else _now()
        ranked=self.ranker.rank(tuple(i for _,r in results for i in build_ranking_inputs(r,timeframes)))
        by_key={(x.opportunity.symbol,x.opportunity.timeframe,x.opportunity.direction):x for x in ranked};journal=SignalJournal();records=[]
        for symbol,r in results:
            direction=_direction(r.decision.decision if r.decision else None)
            for tf in timeframes:
                if direction is None:
                    records.append(self._unavailable(symbol,tf,ts,("directional_raw_strength","context_score","composite","relative_rank","relative_percentile"),"Decision did not produce a directional signal."));continue
                item=by_key.get((symbol,tf,direction))
                if item is None:
                    records.append(self._unavailable(symbol,tf,ts,(f"profile.timeframe:{tf}",),"Required timeframe was unavailable at the runtime boundary."));continue
                ex=extract_observation(r,item,timestamp=ts)
                if ex.observation:journal=journal.record(SignalJournalEntry(observation=ex.observation))
                records.append(self._record(ex,r,symbol,tf,ts))
        return RuntimeObservationRun(self.config,journal,tuple(records),tuple(runtime))
    def _unavailable(self,symbol,tf,ts,fields,reason):return {"status":UNAVAILABLE_AT_BOUNDARY,"session_id":self.config.session_id,"baseline_commit":self.config.baseline_commit,"configuration_fingerprint":self.config.configuration_fingerprint,"universe_id":self.config.universe_identity,"runtime_commit":self.config.runtime_commit,"observed_at_utc":ts.isoformat(),"symbol":symbol,"timeframe":tf,"unavailable_fields":list(fields),"reason":reason}
    def _record(self,ex,r,symbol,tf,ts):
        rec=self._unavailable(symbol,tf,ts,ex.unavailable_fields,"Canonical field was unavailable at the runtime boundary.")
        if ex.observation:
            rec["status"]=ex.status;rec["observation"]=asdict(ex.observation);rec["source_outputs"]={"analysis":{"market_state":r.analysis.market_state,"strength":r.analysis.strength},"profile":{"trend":r.profile.market.trend,"trend_strength":r.profile.market.trend_strength,"momentum":r.profile.market.momentum,"volume_strength":r.profile.market.volume_strength,"volatility":r.profile.market.volatility,"volatility_level":r.profile.market.volatility_level,"liquidity":r.profile.market.liquidity},"score":{"raw_score":r.score.score,"category":r.score.category},"decision":{"decision":r.decision.decision,"confidence":r.decision.confidence}};rec.pop("unavailable_fields",None);rec.pop("reason",None)
        return rec
def write_artifacts(run:RuntimeObservationRun,artifact_root:Path,universe:Mapping[str,Any]):
    root=artifact_root.expanduser().resolve()
    if root==ROOT or ROOT in root.parents: raise ValueError("artifact_root must be outside ORION_NEXT")
    d=root/"signal-observations"/run.config.session_id;d.mkdir(parents=True,exist_ok=False)
    def write(path,value): path.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    write(d/"session.json",{"session_id":run.config.session_id,"status":"STOPPED","observer_version":OBSERVER_VERSION,"baseline_commit":run.config.baseline_commit,"configuration_fingerprint":run.config.configuration_fingerprint,"universe_id":run.config.universe_identity,"runtime_commit":run.config.runtime_commit,"stopped_at_utc":_now().isoformat()})
    write(d/"run_config.json",{"baseline_commit":run.config.baseline_commit,"configuration":run.config.configuration,"configuration_fingerprint":run.config.configuration_fingerprint,"universe_id":run.config.universe_identity,"runtime_commit":run.config.runtime_commit,"observer_version":OBSERVER_VERSION})
    write(d/"universe_input.json",universe);write(d/"configuration_fingerprint.json",{"algorithm":"sha256","configuration_fingerprint":run.config.configuration_fingerprint})
    (d/"runtime_results.jsonl").write_text("".join(json.dumps(x,sort_keys=True)+"\n" for x in run.runtime_results),encoding="utf-8");(d/"observations.jsonl").write_text("".join(json.dumps(x,sort_keys=True)+"\n" for x in run.records),encoding="utf-8");return d
def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument("--baseline",required=True);p.add_argument("--artifact-root",required=True);p.add_argument("--runtime-commit");a=p.parse_args(argv);symbols,tfs=_universe(REQUIRED_SYMBOLS,REQUIRED_TIMEFRAMES)
    cfg={"observer_version":OBSERVER_VERSION,"market_source":"BINANCE_API","symbols":list(symbols),"timeframes":list(tfs),"execution":{"paper":False,"live":False},"ranking":{"cohort":["timeframe","direction"]}}
    config=create_runtime_config(baseline_commit=a.baseline,symbols=symbols,timeframes=tfs,configuration=cfg,runtime_commit=a.runtime_commit);source=BinanceProvider(api_key=os.environ.get("BINANCE_API_KEY",""),api_secret=os.environ.get("BINANCE_API_SECRET",""),testnet=False);source._client._client.API_URL=BINANCE_MARKET_DATA_ONLY_URL;provider=MarketDataProvider(source=source)
    run=PhaseARuntimeObserver(config,orchestrator_factory=lambda:build_runtime_orchestrator(provider)).run(symbols,tfs);d=write_artifacts(run,Path(a.artifact_root),{"symbols":list(symbols),"timeframes":list(tfs)});count=sum(x.get("status")=="OBSERVED" for x in run.records);print(json.dumps({"status":"PASS" if count else "NO_COMPLETE_SIGNAL","session_id":config.session_id,"observations":count,"artifact_directory":str(d)},sort_keys=True));return 0 if count else 2
if __name__=="__main__":raise SystemExit(main())