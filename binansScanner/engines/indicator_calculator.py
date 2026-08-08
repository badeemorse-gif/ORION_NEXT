"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : engines.indicator_calculator
Version      : 2.0.0
Status       : ORION Canonical Indicator Calculator
===============================================================================

Pure technical-indicator calculation component.

The calculator is responsible only for mathematical transformations of a
canonical OHLCV DataFrame.

It does not:
    - mutate MarketDataset state;
    - manage readiness flags;
    - perform analysis;
    - build profiles;
    - calculate scores;
    - make decisions;
    - execute trades;
    - generate reports.

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
    Canonical technical-indicator calculator.

    The ORION baseline indicators are always produced:

        EMA 9
        EMA 20
        EMA 50
        RSI 14
        ADX 14
        Momentum 5

    Additional indicators may also be produced for downstream analytical use.
    """

    REQUIRED_INDICATORS: tuple[str, ...] = (
        "ema_9",
        "ema_20",
        "ema_50",
        "rsi_14",
        "adx_14",
        "momentum_5",
    )

    def apply_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply the complete canonical indicator set.

        The input DataFrame is copied so callers do not receive unexpected
        mutation of their original market-data object.
        """

        self._validate_input(df)

        result = df.copy()

        result = self.apply_price_action(result)
        result = self.apply_trend_indicators(result)
        result = self.apply_momentum_indicators(result)
        result = self.apply_volume_indicators(result)
        result = self.apply_volatility_indicators(result)

        return result

    # =========================================================================
    # Price Action
    # =========================================================================

    def apply_price_action(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Calculate canonical price-action derivatives."""

        high = df["high"]
        low = df["low"]
        close = df["close"]
        open_price = df["open"]

        hl2_value = (high + low) / 2.0
        hlc3_value = (high + low + close) / 3.0

        df["typical_price"] = hlc3_value
        df["median_price"] = hl2_value
        df["hl2"] = hl2_value
        df["hlc3"] = hlc3_value
        df["ohlc4"] = (
            open_price + high + low + close
        ) / 4.0

        return df

    # =========================================================================
    # Trend
    # =========================================================================

    def apply_trend_indicators(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Calculate trend indicators."""

        close = df["close"]
        high = df["high"]
        low = df["low"]

        try:
            # Canonical ORION EMA set.
            df["ema_9"] = ta.ema(
                close,
                length=9,
            )

            df["ema_20"] = ta.ema(
                close,
                length=20,
            )

            df["ema_50"] = ta.ema(
                close,
                length=50,
            )

            # Extended trend indicators retained for future analytical use.
            df["ema_100"] = ta.ema(
                close,
                length=100,
            )

            df["ema_200"] = ta.ema(
                close,
                length=200,
            )

            df["sma_20"] = ta.sma(
                close,
                length=20,
            )

            df["sma_50"] = ta.sma(
                close,
                length=50,
            )

            adx_df = ta.adx(
                high=high,
                low=low,
                close=close,
                length=14,
            )

            if adx_df is not None and not adx_df.empty:
                df["adx_14"] = adx_df.iloc[:, 0]
                df["di_plus"] = adx_df.iloc[:, 1]
                df["di_minus"] = adx_df.iloc[:, 2]
            else:
                df["adx_14"] = np.nan

            supertrend_df = ta.supertrend(
                high=high,
                low=low,
                close=close,
                length=7,
                multiplier=3.0,
            )

            if (
                supertrend_df is not None
                and not supertrend_df.empty
            ):
                df["supertrend_val"] = (
                    supertrend_df.iloc[:, 0]
                )
                df["supertrend_dir"] = (
                    supertrend_df.iloc[:, 1]
                )

            ichimoku_result = ta.ichimoku(
                high=high,
                low=low,
                close=close,
            )

            if (
                isinstance(ichimoku_result, tuple)
                and len(ichimoku_result) > 0
            ):
                ichimoku_df = ichimoku_result[0]

                if (
                    ichimoku_df is not None
                    and not ichimoku_df.empty
                ):
                    ichimoku_df = (
                        ichimoku_df
                        .add_prefix("ichimoku_")
                        .rename(
                            columns=lambda column: column.lower()
                        )
                    )

                    df = df.join(
                        ichimoku_df,
                        how="left",
                    )

        except Exception as exc:
            raise RuntimeError(
                f"Error calculating trend indicators: {exc}"
            ) from exc

        return df

    # =========================================================================
    # Momentum
    # =========================================================================

    def apply_momentum_indicators(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Calculate canonical and extended momentum indicators."""

        close = df["close"]
        high = df["high"]
        low = df["low"]

        try:
            df["rsi_14"] = ta.rsi(
                close,
                length=14,
            )

            macd_df = ta.macd(
                close,
                fast=12,
                slow=26,
                signal=9,
            )

            if macd_df is not None and not macd_df.empty:
                df["macd"] = macd_df.iloc[:, 0]
                df["macd_signal"] = macd_df.iloc[:, 1]
                df["macd_hist"] = macd_df.iloc[:, 2]

            stoch_df = ta.stoch(
                high=high,
                low=low,
                close=close,
                k=14,
                d=3,
            )

            if stoch_df is not None and not stoch_df.empty:
                df["stoch_k"] = stoch_df.iloc[:, 0]
                df["stoch_d"] = stoch_df.iloc[:, 1]

            df["cci_14"] = ta.cci(
                high=high,
                low=low,
                close=close,
                length=14,
            )

            df["willr_14"] = ta.willr(
                high=high,
                low=low,
                close=close,
                length=14,
            )

            df["roc_10"] = ta.roc(
                close,
                length=10,
            )

            # Canonical ORION momentum.
            df["momentum_5"] = ta.mom(
                close,
                length=5,
            )

            # Extended momentum retained separately.
            df["momentum_10"] = ta.mom(
                close,
                length=10,
            )

        except Exception as exc:
            raise RuntimeError(
                f"Error calculating momentum indicators: {exc}"
            ) from exc

        return df

    # =========================================================================
    # Volume
    # =========================================================================

    def apply_volume_indicators(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Calculate volume indicators."""

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        try:
            df["obv"] = ta.obv(
                close,
                volume,
            )

            df["cmf_20"] = ta.cmf(
                high=high,
                low=low,
                close=close,
                volume=volume,
                length=20,
            )

            try:
                df["vwap"] = ta.vwap(
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            except Exception:
                df["vwap"] = np.nan

            df["mfi_14"] = ta.mfi(
                high=high,
                low=low,
                close=close,
                volume=volume,
                length=14,
            )

        except Exception as exc:
            raise RuntimeError(
                f"Error calculating volume indicators: {exc}"
            ) from exc

        return df

    # =========================================================================
    # Volatility
    # =========================================================================

    def apply_volatility_indicators(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Calculate volatility indicators."""

        close = df["close"]
        high = df["high"]
        low = df["low"]

        try:
            df["atr_14"] = ta.atr(
                high=high,
                low=low,
                close=close,
                length=14,
            )

            bbands_df = ta.bbands(
                close,
                length=20,
                std=2.0,
            )

            if bbands_df is not None and not bbands_df.empty:
                df["bb_lower"] = bbands_df.iloc[:, 0]
                df["bb_middle"] = bbands_df.iloc[:, 1]
                df["bb_upper"] = bbands_df.iloc[:, 2]
                df["bb_bandwidth"] = bbands_df.iloc[:, 3]
                df["bb_percent"] = bbands_df.iloc[:, 4]

            kc_df = ta.kc(
                high=high,
                low=low,
                close=close,
                length=20,
                scalar=2.0,
            )

            if kc_df is not None and not kc_df.empty:
                df["kc_lower"] = kc_df.iloc[:, 0]
                df["kc_middle"] = kc_df.iloc[:, 1]
                df["kc_upper"] = kc_df.iloc[:, 2]

            dc_df = ta.donchian(
                high=high,
                low=low,
                lower_length=20,
                upper_length=20,
            )

            if dc_df is not None and not dc_df.empty:
                df["dc_lower"] = dc_df.iloc[:, 0]
                df["dc_middle"] = dc_df.iloc[:, 1]
                df["dc_upper"] = dc_df.iloc[:, 2]

        except Exception as exc:
            raise RuntimeError(
                f"Error calculating volatility indicators: {exc}"
            ) from exc

        return df

    # =========================================================================
    # Validation
    # =========================================================================

    def validate_required_indicators(
        self,
        df: pd.DataFrame,
    ) -> None:
        """
        Verify that every canonical ORION indicator exists.

        This is deliberately separate from calculation so that downstream
        layers can validate a prepared DataFrame without recalculating it.
        """

        missing = [
            column
            for column in self.REQUIRED_INDICATORS
            if column not in df.columns
        ]

        if missing:
            raise ValueError(
                "Missing canonical indicators: "
                + ", ".join(missing)
            )

    def _validate_input(
        self,
        df: pd.DataFrame,
    ) -> None:
        """Validate canonical OHLCV input."""

        if not isinstance(df, pd.DataFrame):
            raise TypeError(
                "IndicatorCalculator expects pandas.DataFrame."
            )

        if df.empty:
            raise ValueError(
                "IndicatorCalculator cannot process an empty DataFrame."
            )

        required_columns = {
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        missing = required_columns - set(df.columns)

        if missing:
            raise ValueError(
                "Missing required OHLCV columns: "
                + ", ".join(sorted(missing))
            )

        if not isinstance(
            df.index,
            pd.DatetimeIndex,
        ):
            raise ValueError(
                "Indicator input index must be DatetimeIndex."
            )

        if df.index.tz is None:
            raise ValueError(
                "Indicator input index must be timezone-aware."
            )

        if not df.index.is_monotonic_increasing:
            raise ValueError(
                "Indicator input index must be chronologically sorted."
            )

        if df.index.duplicated().any():
            raise ValueError(
                "Indicator input contains duplicate timestamps."
            )

        if df[
            [
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        ].isna().any().any():
            raise ValueError(
                "Indicator input contains NaN OHLCV values."
            )

        if np.isinf(
            df[
                [
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                ]
            ].to_numpy()
        ).any():
            raise ValueError(
                "Indicator input contains infinite OHLCV values."
            )

        if (
            df[
                [
                    "open",
                    "high",
                    "low",
                    "close",
                ]
            ] < 0
        ).any().any():
            raise ValueError(
                "Indicator input contains negative prices."
            )

        if (df["volume"] < 0).any():
            raise ValueError(
                "Indicator input contains negative volume."
            )