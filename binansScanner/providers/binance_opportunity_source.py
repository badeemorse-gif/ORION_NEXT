"""Bulk Binance Spot market source for dynamic opportunity discovery."""
from __future__ import annotations
from dataclasses import dataclass
import json, math, statistics, time
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from models.opportunity import MarketMetrics

@dataclass(slots=True)
class _CacheEntry:
    expires_at: float
    value: Any

class BinanceSpotOpportunitySource:
    BASE_URL="https://api.binance.com/api/v3"; HISTORY_INTERVAL="1d"; HISTORY_LIMIT=31; MIN_HISTORY_CANDLES=22
    def __init__(self, ttl_seconds: float=30.0, timeout_seconds: float=10.0, clock=time.monotonic)->None:
        if ttl_seconds<0 or timeout_seconds<=0: raise ValueError("invalid cache/timeout configuration")
        self.ttl_seconds=ttl_seconds; self.timeout_seconds=timeout_seconds; self._clock=clock; self._cache={}
    def _get_json(self,path:str,params:Mapping[str,Any]|None=None)->Any:
        query=f"?{urlencode(params or {})}" if params else ""; request=Request(f"{self.BASE_URL}/{path}{query}",headers={"Accept":"application/json"})
        with urlopen(request,timeout=self.timeout_seconds) as response: return json.load(response)
    def _cached(self,key,loader):
        now=self._clock(); entry=self._cache.get(key)
        if entry is not None and entry.expires_at>now: return entry.value
        value=loader(); self._cache[key]=_CacheEntry(now+self.ttl_seconds,value); return value
    def exchange_info(self): return self._cached("exchange_info",lambda:self._get_json("exchangeInfo"))
    @staticmethod
    def _ema(values,period):
        if len(values)<period: raise ValueError("insufficient history for EMA")
        alpha=2.0/(period+1.0); ema=statistics.fmean(values[:period])
        for value in values[period:]: ema=alpha*value+(1-alpha)*ema
        return ema
    @classmethod
    def _history_features(cls,rows):
        closes=[float(row[4]) for row in rows if isinstance(row,Sequence) and len(row)>4]
        if len(closes)<cls.MIN_HISTORY_CANDLES: raise ValueError("insufficient price history")
        returns=[math.log(closes[i]/closes[i-1]) for i in range(1,len(closes)) if closes[i]>0 and closes[i-1]>0]
        if len(returns)<cls.MIN_HISTORY_CANDLES-1: raise ValueError("insufficient return history")
        volatility=statistics.stdev(returns); ema_fast=cls._ema(closes[-21:],7); ema_slow=cls._ema(closes[-21:],21)
        trend_direction=max(-1.0,min(1.0,(ema_fast/ema_slow-1.0)/0.05)) if ema_slow>0 else 0.0
        recent=returns[-7:]; positive=sum(v>0 for v in recent)/len(recent); negative=sum(v<0 for v in recent)/len(recent); persistence=max(positive,negative); trend_quality=min(1.0,abs(trend_direction))*persistence
        roc_3=closes[-1]/closes[-4]-1.0; roc_7=closes[-1]/closes[-8]-1.0; momentum_raw=roc_3-(roc_7/7.0*3.0); momentum_direction=max(-1.0,min(1.0,momentum_raw/0.03)); momentum_quality=min(1.0,abs(momentum_direction))
        return volatility,trend_quality,trend_direction,persistence,momentum_quality,momentum_direction
    def metrics_bulk(self,symbols:Sequence[str])->Mapping[str,MarketMetrics]:
        wanted={s.upper() for s in symbols}
        if not wanted:return {}
        tickers=self._cached("ticker_24h",lambda:self._get_json("ticker/24hr")); books=self._cached("book_ticker",lambda:self._get_json("ticker/bookTicker"))
        ticker_by={str(r.get("symbol","")).upper():r for r in tickers if isinstance(r,Mapping)}; book_by={str(r.get("symbol","")).upper():r for r in books if isinstance(r,Mapping)}; result={}
        for symbol in sorted(wanted):
            ticker=ticker_by.get(symbol)
            if ticker is None: continue
            try:
                last=float(ticker["lastPrice"]); quote=float(ticker["quoteVolume"]); change=float(ticker["priceChangePercent"]); weighted=float(ticker["weightedAvgPrice"]); book=book_by.get(symbol); spread=None
                if book is not None:
                    bid=float(book["bidPrice"]); ask=float(book["askPrice"])
                    if bid>0 and ask>=bid: spread=((ask-bid)/((ask+bid)/2))*10000
                history=self._cached(f"klines_{symbol}",lambda symbol=symbol:self._get_json("klines",{"symbol":symbol,"interval":self.HISTORY_INTERVAL,"limit":self.HISTORY_LIMIT}))
                volatility,trend_quality,trend_direction,persistence,momentum_quality,momentum_direction=self._history_features(history)
                deviation=abs(last/weighted-1.0) if weighted>0 else math.inf; structure=max(0.0,1.0-min(deviation/0.05,1.0)) if math.isfinite(deviation) else 0.0; volume_quality=min(math.log1p(max(quote,0.0))/math.log1p(100_000_000.0),1.0)
                result[symbol]=MarketMetrics(symbol,quote,volatility,spread,True,last,volume_quality,trend_quality,momentum_quality,structure,change,weighted,trend_direction,persistence,momentum_direction)
            except (KeyError,TypeError,ValueError,statistics.StatisticsError,ZeroDivisionError): continue
        return result
