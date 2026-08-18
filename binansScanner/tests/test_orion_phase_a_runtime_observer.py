from __future__ import annotations
import ast, sys, unittest
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from core.orchestrator import OrchestratorResult, PipelineError, PipelineStage, PipelineStatistics
from enums import DataHealth, Timeframe
from models.analysis import AnalysisResult
from models.decision import DecisionResult
from models.market import MarketDataset, MarketMetadata, TimeframeData
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics, TimeframeProfile
from models.score import ScoreResult
from models.signal_journal import SignalJournal, SignalJournalEntry
from tools.orion_phase_a_runtime_observer import REQUIRED_SYMBOLS, REQUIRED_TIMEFRAMES, UNAVAILABLE_AT_BOUNDARY, PhaseARuntimeObserver, build_ranking_inputs, create_runtime_config, extract_observation, extract_wait_observation

class TestPhaseARuntimeObserver(unittest.TestCase):
    @staticmethod
    def _result(symbol="BTCUSDT",decision="FAVORABLE",score=31.5):
        import pandas as pd
        now=datetime(2026,8,17,20,0,tzinfo=timezone.utc)
        dataset=MarketDataset(MarketMetadata(symbol,"BINANCE","BINANCE_API","1.0.0",now,now))
        frame=pd.DataFrame({"open":[100.,101.,102.],"high":[101.,102.,103.],"low":[99.,100.,101.],"close":[100.5,101.5,102.5],"volume":[100.,100.,150.]},index=pd.date_range(now,periods=3,freq="h",tz="UTC"))
        for tf in (Timeframe.H1,Timeframe.H4,Timeframe.D1): dataset.add_timeframe(TimeframeData(tf,frame,DataHealth.GOOD,3,now,now))
        ch=MarketCharacteristics(trend="Bullish",trend_strength="Strong",momentum="Buy",volume_strength="Strong",volatility=.02,volatility_level="Normal",liquidity=.9,market_phase="Markup",confidence=80.)
        profile=ProfileResult(symbol,ch,ProfileStatistics(confidence_limit=80.,completion_ratio=1.,total_candles=9),tuple(TimeframeProfile(tf,ch,3,now,now,DataHealth.GOOD) for tf in REQUIRED_TIMEFRAMES),is_tradeable=True,generated_at=now)
        return OrchestratorResult(dataset=dataset,analysis=AnalysisResult("BULLISH",20.,["TEST_SIGNAL"]),profile=profile,score=ScoreResult(score,"BULLISH",["TEST_FACTOR"]),decision=DecisionResult(decision,abs(score) if decision!="WAIT" else 0.,["TEST_REASON"]),statistics=PipelineStatistics(finished_at=now,current_stage=PipelineStage.FINISHED,completed_stage_count=8,success=True))

    def test_required_universe_and_binding(self):
        self.assertEqual(REQUIRED_SYMBOLS,("BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","ADAUSDT")); self.assertEqual(REQUIRED_TIMEFRAMES,("1h","4h","1d"))
        c=create_runtime_config(baseline_commit="c54dc67792776da905a3efb1f667c1869c15db3d",symbols=REQUIRED_SYMBOLS,timeframes=REQUIRED_TIMEFRAMES,configuration={"execution":{"paper":False,"live":False}},session_id="EXP-20260817T200000Z-abcdef123456",runtime_commit="ce97cb6064dc0d0cfd02e15d4f30f1d80b824c2c")
        self.assertEqual(c.baseline_commit,"c54dc67792776da905a3efb1f667c1869c15db3d"); self.assertEqual(len(c.configuration_fingerprint),64); self.assertTrue(c.universe_identity.startswith("UNIV-"))

    def test_valid_subset_and_unknown_symbol_rejected(self):
        btc = create_runtime_config(baseline_commit="c54dc67792776da905a3efb1f667c1869c15db3d",symbols=("BTCUSDT",),timeframes=REQUIRED_TIMEFRAMES,configuration={},session_id="EXP-20260817T200000Z-abcdef123456",runtime_commit="1ef2acf4ea262100bb560feaf33e7f6b21441dfa")
        ada = create_runtime_config(baseline_commit="c54dc67792776da905a3efb1f667c1869c15db3d",symbols=("ADAUSDT",),timeframes=REQUIRED_TIMEFRAMES,configuration={},session_id="EXP-20260817T200000Z-abcdef123456",runtime_commit="1ef2acf4ea262100bb560feaf33e7f6b21441dfa")
        self.assertEqual(btc.universe_identity[:5],"UNIV-"); self.assertEqual(ada.universe_identity[:5],"UNIV-")
        with self.assertRaises(ValueError):
            create_runtime_config(baseline_commit="c54dc67792776da905a3efb1f667c1869c15db3d",symbols=("DOGEUSDT",),timeframes=REQUIRED_TIMEFRAMES,configuration={},session_id="EXP-20260817T200000Z-abcdef123456",runtime_commit="1ef2acf4ea262100bb560feaf33e7f6b21441dfa")

    def test_real_contract_result_extraction_and_d3_inputs(self):
        r=self._result(); inputs=build_ranking_inputs(r); self.assertEqual(len(inputs),3); self.assertIs(inputs[0].score,r.score); self.assertIs(inputs[0].profile,r.profile); self.assertIs(inputs[0].dataset,r.dataset)

    def test_observation_preserves_orion_outputs(self):
        from engines.opportunity_relative_ranking import OpportunityRelativeRanker
        r=self._result(score=31.5); ranked=OpportunityRelativeRanker().rank(build_ranking_inputs(r)); item=next(x for x in ranked if x.opportunity.timeframe=="1h")
        ex=extract_observation(r,item,timestamp=datetime(2026,8,17,20,0,tzinfo=timezone.utc)); self.assertEqual(ex.status,"OBSERVED"); self.assertIsNotNone(ex.observation); o=ex.observation; assert o is not None
        self.assertEqual(o.raw_score,31.5); self.assertEqual(o.decision,"FAVORABLE"); self.assertEqual(o.market_regime,"Markup"); self.assertEqual(o.timeframe,"1h"); self.assertNotIn("outcome_1h",o.__dataclass_fields__)

    def test_d3_cohort_is_timeframe_and_direction(self):
        from engines.opportunity_relative_ranking import OpportunityRelativeRanker
        ranked=OpportunityRelativeRanker().rank(build_ranking_inputs(self._result("BTCUSDT"))+build_ranking_inputs(self._result("ETHUSDT"))); counts={(x.opportunity.symbol,x.opportunity.timeframe):x.peer_count for x in ranked}
        self.assertEqual(counts[("BTCUSDT","1h")],2); self.assertEqual(counts[("ETHUSDT","4h")],2)

    def test_d6_journal_compatibility_and_no_outcome(self):
        from engines.opportunity_relative_ranking import OpportunityRelativeRanker
        r=self._result(); item=OpportunityRelativeRanker().rank(build_ranking_inputs(r))[0]; o=extract_observation(r,item,timestamp=datetime(2026,8,17,20,0,tzinfo=timezone.utc)).observation; assert o is not None
        journal=SignalJournal().record(SignalJournalEntry(observation=o)); self.assertEqual(len(journal),1); self.assertIsNone(journal.entries[0].outcome)

    def test_missing_boundary_is_not_guessed(self):
        from engines.opportunity_relative_ranking import OpportunityRelativeRanker
        r0=self._result(); broken=ProfileResult(symbol=r0.profile.symbol,market=MarketCharacteristics(trend="Bullish",market_phase="",confidence=80.),statistics=r0.profile.statistics,timeframes=r0.profile.timeframes,is_tradeable=True)
        r=OrchestratorResult(dataset=r0.dataset,analysis=r0.analysis,profile=broken,score=r0.score,decision=r0.decision,statistics=r0.statistics); item=OpportunityRelativeRanker().rank(build_ranking_inputs(r))[0]
        ex=extract_observation(r,item,timestamp=datetime(2026,8,17,20,0,tzinfo=timezone.utc)); self.assertEqual(ex.status,UNAVAILABLE_AT_BOUNDARY); self.assertIn("market_regime",ex.unavailable_fields); self.assertIsNone(ex.observation)

    def test_wait_does_not_create_guessed_direction(self): self.assertEqual(build_ranking_inputs(self._result(decision="WAIT")),())

    def test_wait_extracts_one_signal_time_observation(self):
        r=self._result(decision="WAIT"); ex=extract_wait_observation(r,"1h",timestamp=datetime(2026,8,17,20,0,tzinfo=timezone.utc)); self.assertEqual(ex.status,"OBSERVED"); self.assertIsNotNone(ex.observation); self.assertEqual(ex.observation.timeframe,"1h"); self.assertEqual(ex.observation.decision,"WAIT"); self.assertIsNone(ex.observation.directional_raw_strength); self.assertIsNone(ex.observation.context_score); self.assertIsNone(ex.observation.composite); self.assertIsNone(ex.observation.relative_rank); self.assertIsNone(ex.observation.relative_percentile)

    def test_point_in_time_and_future_leakage(self):
        p=ROOT/"tools"/"orion_phase_a_runtime_observer.py"; text=p.read_text(encoding="utf-8"); tree=ast.parse(text); imported=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Import): imported += [a.name for a in n.names]
            elif isinstance(n,ast.ImportFrom): imported.append(n.module or "")
        self.assertNotIn("engines.execution_engine",imported); self.assertNotIn("models.execution",imported)
        for forbidden in ("SignalOutcome","forward_outcome_validation","outcome_1h","outcome_4h","outcome_24h","mfe","mae"): self.assertNotIn(forbidden,text)

    def test_symbol_level_decision_creates_at_most_one_observation(self):
        class Stub:
            def __init__(self): self.result=None
            def run(self,symbol,timeframes): self.result=TestPhaseARuntimeObserver._result(symbol=symbol); return self.result
            def last_result(self): return self.result
        c=create_runtime_config(baseline_commit="c54dc67792776da905a3efb1f667c1869c15db3d",symbols=REQUIRED_SYMBOLS,timeframes=REQUIRED_TIMEFRAMES,configuration={"execution":{"paper":False,"live":False}},session_id="EXP-20260817T200000Z-abcdef123456",runtime_commit="5db73bfb079655fd32e2127289f181938006a167")
        run=PhaseARuntimeObserver(c,orchestrator_factory=Stub).run(("BTCUSDT",),REQUIRED_TIMEFRAMES); observed=[x for x in run.records if x["status"]=="OBSERVED"]; self.assertEqual(len(observed),1); self.assertEqual(len(run.journal),1); self.assertEqual(observed[0]["timeframe"],"1h"); self.assertEqual(observed[0]["primary_timeframe"],"1h")
        unavailable=[x for x in run.records if x["status"]==UNAVAILABLE_AT_BOUNDARY]; self.assertEqual({x["timeframe"] for x in unavailable},{"4h","1d"})
        for x in unavailable: self.assertEqual(x["reason"],"ORION runtime produced a symbol-level DecisionResult from the canonical primary timeframe; no independent DecisionResult exists for this timeframe.")

    def test_wait_creates_one_observation_and_no_4h_1d_duplicates(self):
        class Stub:
            def __init__(self): self.result=None
            def run(self,symbol,timeframes): self.result=TestPhaseARuntimeObserver._result(symbol=symbol,decision="WAIT"); return self.result
            def last_result(self): return self.result
        c=create_runtime_config(baseline_commit="c54dc67792776da905a3efb1f667c1869c15db3d",symbols=REQUIRED_SYMBOLS,timeframes=REQUIRED_TIMEFRAMES,configuration={},session_id="EXP-20260817T200000Z-abcdef123456",runtime_commit="5db73bfb079655fd32e2127289f181938006a167")
        run=PhaseARuntimeObserver(c,orchestrator_factory=Stub).run(("BTCUSDT",),REQUIRED_TIMEFRAMES); self.assertEqual(len(run.journal),1); self.assertEqual([e.observation.timeframe for e in run.journal.entries],["1h"])

    def test_directional_creates_at_most_one_signal_observation(self):
        class Stub:
            def __init__(self): self.result=None
            def run(self,symbol,timeframes): self.result=TestPhaseARuntimeObserver._result(symbol=symbol,decision="FAVORABLE"); return self.result
            def last_result(self): return self.result
        c=create_runtime_config(baseline_commit="c54dc67792776da905a3efb1f667c1869c15db3d",symbols=REQUIRED_SYMBOLS,timeframes=REQUIRED_TIMEFRAMES,configuration={},session_id="EXP-20260817T200000Z-abcdef123456",runtime_commit="5db73bfb079655fd32e2127289f181938006a167")
        run=PhaseARuntimeObserver(c,orchestrator_factory=Stub).run(("BTCUSDT",),REQUIRED_TIMEFRAMES); observed=[x for x in run.records if x["status"]=="OBSERVED"]; self.assertEqual(len(observed),1); self.assertEqual(observed[0]["timeframe"],"1h")

    def test_profile_blocked_creates_no_successful_observation(self):
        class Stub:
            def __init__(self): self.result=None
            def run(self,symbol,timeframes):
                r=TestPhaseARuntimeObserver._result(symbol=symbol); r.statistics.current_stage=PipelineStage.PROFILE; r.statistics.success=False; r.statistics.error_message="Profile intelligence blocked before Score/Decision: Extreme market risk"; r.score=None; r.decision=None; self.result=r; raise PipelineError(r.statistics.error_message)
            def last_result(self): return self.result
        c=create_runtime_config(baseline_commit="c54dc67792776da905a3efb1f667c1869c15db3d",symbols=REQUIRED_SYMBOLS,timeframes=REQUIRED_TIMEFRAMES,configuration={},session_id="EXP-20260817T200000Z-abcdef123456",runtime_commit="5db73bfb079655fd32e2127289f181938006a167")
        run=PhaseARuntimeObserver(c,orchestrator_factory=Stub).run(("ADAUSDT",),REQUIRED_TIMEFRAMES); self.assertEqual(len([x for x in run.records if x["status"]=="OBSERVED"]),0); self.assertIn("PIPELINE_BLOCKED",{x["status"] for x in run.records})

    def test_no_score_or_decision_recalculation_in_observer(self):
        class Stub:
            def __init__(self): self.result=None
            def run(self,symbol,timeframes): self.result=TestPhaseARuntimeObserver._result(symbol=symbol); return self.result
            def last_result(self): return self.result
        c=create_runtime_config(baseline_commit="c54dc67792776da905a3efb1f667c1869c15db3d",symbols=REQUIRED_SYMBOLS,timeframes=REQUIRED_TIMEFRAMES,configuration={},session_id="EXP-20260817T200000Z-abcdef123456",runtime_commit="5db73bfb079655fd32e2127289f181938006a167")
        run=PhaseARuntimeObserver(c,orchestrator_factory=Stub).run(("BTCUSDT",),REQUIRED_TIMEFRAMES); obs=next(x for x in run.records if x["status"]=="OBSERVED"); self.assertEqual(obs["source_outputs"]["score"]["raw_score"],31.5); self.assertEqual(obs["source_outputs"]["decision"]["decision"],"FAVORABLE")

if __name__=="__main__": unittest.main()
