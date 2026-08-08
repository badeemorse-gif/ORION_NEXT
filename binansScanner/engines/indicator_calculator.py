"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : engines.indicator_calculator
Version      : 1.0.0
Status       : ORION Production Calculator Component
===============================================================================

Standalone mathematical calculator component responsible for computing all
technical indicators (EMA, RSI, MACD, ATR, ADX, etc.) using vectorized operations.
===============================================================================
"""

from __future__ import annotations

import logging
import numpy as np
import pandas as pd
import pandas_ta as ta

logger = logging.getLogger(__name__)


class IndicatorCalculator:
    """
    Encapsulates all mathematical computations and vectorized indicator applications
    separating the calculation logic from coordination.
    """

    def apply_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Applies price action, trend, momentum, volume, and volatility indicators.
        """
        df = self.apply_price_action(df)
        df = self.apply_trend_indicators(df)
        df = self.apply_momentum_indicators(df)
        df = self.apply_volume_indicators(df)
        df = self.apply_volatility_indicators(df)
        df = self.remove_nan(df)
        return df

    def apply_price_action(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate price action derivations efficiently."""
        high = df["high"]
        low = df["low"]
        close = df["close"]
        open_p = df["open"]

        hl2_val = (high + low) / 2.0
        hlc3_val = (high + low + close) / 3.0

        df["typical_price"] = hlc3_val
        df["median_price"] = hl2_val
        df["hl2"] = hl2_val
        df["hlc3"] = hlc3_val
        df["ohlc4"] = (open_p + high + low + close) / 4.0
        return df

    def apply_trend_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate trend indicators: EMA, SMA, ADX, SuperTrend, Ichimoku."""
        close = df["close"]
        high = df["high"]
        low = df["low"]

        try:
            df["ema_20"] = ta.ema(close, length=20)
            df["ema_50"] = ta.ema(close, length=50)
            df["ema_100"] = ta.ema(close, length=100)
            df["ema_200"] = ta.ema(close, length=200)

            df["sma_20"] = ta.sma(close, length=20)
            df["sma_50"] = ta.sma(close, length=50)

            adx_df = ta.adx(high=high, low=low, close=close, length=14)
            if adx_df is not None and not adx_df.empty:
                df["adx_14"] = adx_df.iloc[:, 0]
                df["di_plus"] = adx_df.iloc[:, 1]
                df["di_minus"] = adx_df.iloc[:, 2]

            supertrend_df = ta.supertrend(high=high, low=low, close=close, length=7, multiplier=3.0)
            if supertrend_df is not None and not supertrend_df.empty:
                df["supertrend_val"] = supertrend_df.iloc[:, 0]
                df["supertrend_dir"] = supertrend_df.iloc[:, 1]

            ichimoku_tuple = ta.ichimoku(high=high, low=low, close=close)
            if ichimoku_tuple is not None and isinstance(ichimoku_tuple, tuple) and len(ichimoku_tuple) > 0:
                ichimoku_df = ichimoku_tuple[0]
                if ichimoku_df is not None and not ichimoku_df.empty:
                    ichimoku_df = ichimoku_df.add_prefix("ichimoku_").rename(columns=lambda x: x.lower())
                    df = df.join(ichimoku_df)
        except Exception as e:
            raise RuntimeError(f"Error calculating trend indicators: {e}") from e

        return df

    def apply_momentum_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate momentum indicators: RSI, MACD, Stochastic, CCI, Williams %R, ROC, Momentum."""
        close = df["close"]
        high = df["high"]
        low = df["low"]

        try:
            df["rsi_14"] = ta.rsi(close, length=14)

            macd_df = ta.macd(close, fast=12, slow=26, signal=9)
            if macd_df is not None and not macd_df.empty:
                df["macd"] = macd_df.iloc[:, 0]
                df["macd_signal"] = macd_df.iloc[:, 1]
                df["macd_hist"] = macd_df.iloc[:, 2]

            stoch_df = ta.stoch(high=high, low=low, close=close, k=14, d=3)
            if stoch_df is not None and not stoch_df.empty:
                df["stoch_k"] = stoch_df.iloc[:, 0]
                df["stoch_d"] = stoch_df.iloc[:, 1]

            df["cci_14"] = ta.cci(high=high, low=low, close=close, length=14)
            df["willr_14"] = ta.willr(high=high, low=low, close=close, length=14)
            df["roc_10"] = ta.roc(close, length=10)
            df["momentum_10"] = ta.mom(close, length=10)
        except Exception as e:
            raise RuntimeError(f"Error calculating momentum indicators: {e}") from e

        return df

    def apply_volume_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate volume indicators: OBV, CMF, VWAP, MFI."""
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        try:
            df["obv"] = ta.obv(close, volume)
            df["cmf_20"] = ta.cmf(high=high, low=low, close=close, volume=volume, length=20)
            
            try:
                df["vwap"] = ta.vwap(high=high, low=low, close=close, volume=volume)
            except Exception:
                df["vwap"] = np.nan

            df["mfi_14"] = ta.mfi(high=high, low=low, close=close, volume=volume, length=14)
        except Exception as e:
            raise RuntimeError(f"Error calculating volume indicators: {e}") from e

        return df

    def apply_volatility_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate volatility indicators: ATR, Bollinger Bands, Keltner Channel, Donchian Channel."""
        close = df["close"]
        high = df["high"]
        low = df["low"]

        try:
            df["atr_14"] = ta.atr(high=high, low=low, close=close, length=14)

            bbands_df = ta.bbands(close, length=20, std=2.0)
            if bbands_df is not None and not bbands_df.empty:
                df["bb_lower"] = bbands_df.iloc[:, 0]
                df["bb_middle"] = bbands_df.iloc[:, 1]
                df["bb_upper"] = bbands_df.iloc[:, 2]
                df["bb_bandwidth"] = bbands_df.iloc[:, 3]
                df["bb_percent"] = bbands_df.iloc[:, 4]

            kc_df = ta.kc(high=high, low=low, close=close, length=20, scalar=2.0)
            if kc_df is not None and not kc_df.empty:
                df["kc_lower"] = kc_df.iloc[:, 0]
                df["kc_middle"] = kc_df.iloc[:, 1]
                df["kc_upper"] = kc_df.iloc[:, 2]

            dc_df = ta.donchian(high=high, low=low, lower_length=20, upper_length=20)
            if dc_df is not None and not dc_df.empty:
                df["dc_lower"] = dc_df.iloc[:, 0]
                df["dc_middle"] = dc_df.iloc[:, 1]
                df["dc_upper"] = dc_df.iloc[:, 2]
        except Exception as e:
            raise RuntimeError(f"Error calculating volatility indicators: {e}") from e

        return df

    def remove_nan(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean up NaN values."""
        fillable_cols = [col for col in df.columns if col not in {"open", "high", "low", "close", "volume"}]
        if fillable_cols:
            df[fillable_cols] = df[fillable_cols].ffill()
        return df