import logging
from typing import List, Optional
import pandas as pd

from models.analysis import AnalysisResult
from models.market import MarketDataset, TimeframeData

logger = logging.getLogger(__name__)


class AnalysisEngine:
    """Analyzes market datasets across timeframes after indicator calculations.

    Adheres to clean architecture principles by avoiding direct trade executions,
    final score calculations, external API dependencies, or usage of legacy structures.
    Consumes indicator outputs to produce an aggregate AnalysisResult without heavy dependencies.
    """

    REQUIRED_INDICATORS: List[str] = [
        "ema_9",
        "ema_20",
        "ema_50",
        "rsi_14",
        "adx_14",
        "momentum_5",
    ]

    def __init__(self, default_timeframe: Optional[str] = None) -> None:
        """Initializes the AnalysisEngine.

        Args:
            default_timeframe: Optional preferred timeframe to use for analysis.
              If not specified, defaults to the first available timeframe or '1h'.
        """
        self.default_timeframe = default_timeframe

    def analyze(self, dataset: MarketDataset) -> AnalysisResult:
        """Analyzes the market dataset and returns structured analysis insights.

        Args:
            dataset: The MarketDataset with pre-calculated indicators.

        Returns:
            An AnalysisResult summarizing market state, strength, signals, and warnings.
        """
        if not dataset or not dataset.timeframes:
            logger.warning(
                "MarketDataset is empty or contains no timeframes for analysis."
            )
            return AnalysisResult(
                market_state="NEUTRAL", strength=0.0, warnings=["EMPTY_DATASET"]
            )

        # Select target timeframe based on flexible configuration or fallback hierarchy
        target_tf_data, tf_name = self._select_primary_timeframe(dataset)
        if (
            not target_tf_data
            or target_tf_data.df is None
            or target_tf_data.df.empty
        ):
            logger.warning("No valid timeframe data found for analysis.")
            return AnalysisResult(
                market_state="NEUTRAL",
                strength=0.0,
                warnings=["NO_VALID_TIMEFRAME_DATA"],
            )

        df = target_tf_data.df
        signals: List[str] = []
        warnings: List[str] = []

        # Check data sufficiency based on timeframe indicator quality
        if (
            getattr(target_tf_data, "indicator_quality", "SUFFICIENT")
            == "INSUFFICIENT_DATA"
        ):
            warnings.append("INSUFFICIENT_DATA_QUALITY")
            signals.append("LOW_CONFIDENCE_DATA")

        # General check for required technical indicators
        missing_indicators = [
            ind for ind in self.REQUIRED_INDICATORS if ind not in df.columns
        ]
        if missing_indicators:
            logger.warning(
                f"Missing required indicators in timeframe {tf_name}: {missing_indicators}"
            )
            warnings.append("MISSING_REQUIRED_INDICATORS")
            signals.append("LOW_CONFIDENCE_DATA")

        # 1. Trend Analysis via EMAs
        market_state = self._determine_market_state(df, signals)

        # 2. Strength Evaluation via normalized components
        strength = self._calculate_market_strength(df, signals)

        logger.info(
            f"Market analysis complete for timeframe [{tf_name}]. State: {market_state}, Strength: {strength:.2f}"
        )
        return AnalysisResult(
            market_state=market_state,
            strength=round(strength, 2),
            signals=signals,
            warnings=warnings,
        )

    def _select_primary_timeframe(
        self, dataset: MarketDataset
    ) -> tuple[Optional[TimeframeData], Optional[str]]:
        """Selects the most appropriate timeframe based on configuration or priority fallback."""
        if self.default_timeframe and self.default_timeframe in dataset.timeframes:
            return dataset.timeframes[self.default_timeframe], self.default_timeframe

        preferred_order = ["1h", "4h", "15m", "1d", "1min"]
        for tf in preferred_order:
            if tf in dataset.timeframes:
                return dataset.timeframes[tf], tf

        # Fallback to the first available timeframe if preferred ones are missing
        if dataset.timeframes:
            first_key = list(dataset.timeframes.keys())[0]
            return dataset.timeframes[first_key], first_key

        return None, None

    def _determine_market_state(
        self,
        df: pd.DataFrame,
        signals: List[str]
    ) -> str:
        """Determines market trend state (BULLISH, BEARISH, NEUTRAL, MIXED) using EMA alignments."""
        required_cols = ["ema_9", "ema_20", "ema_50"]
        if not all(col in df.columns for col in required_cols):
            logger.debug("EMA columns missing for market state determination.")
            return "NEUTRAL"

        last_row = df.iloc[-1]
        ema9 = last_row["ema_9"]
        ema20 = last_row["ema_20"]
        ema50 = last_row["ema_50"]

        if pd.isna(ema9) or pd.isna(ema20) or pd.isna(ema50):
            return "NEUTRAL"

        if ema9 > ema20 > ema50:
            signals.append("EMA_ALIGNMENT_BULLISH")
            return "BULLISH"
        elif ema9 < ema20 < ema50:
            signals.append("EMA_ALIGNMENT_BEARISH")
            return "BEARISH"
        else:
            signals.append("EMA_MIXED")
            return "NEUTRAL"

    def _calculate_market_strength(
        self,
        df: pd.DataFrame,
        signals: List[str]
    ) -> float:
        """Calculates normalized market movement strength score (0 to 100) using Python pure logic."""
        score_components = []

        # RSI Evaluation (0 to 100 magnitude distance from center 50)
        if "rsi_14" in df.columns:
            last_rsi = df["rsi_14"].iloc[-1]
            if not pd.isna(last_rsi):
                if last_rsi >= 70:
                    signals.append("RSI_OVERBOUGHT")
                elif last_rsi <= 30:
                    signals.append("RSI_OVERSOLD")

                rsi_strength = min(abs(last_rsi - 50.0) * 2.0, 100.0)
                score_components.append(rsi_strength)

        # ADX Evaluation (Trend Strength 0 to 100)
        if "adx_14" in df.columns:
            last_adx = df["adx_14"].iloc[-1]
            if not pd.isna(last_adx):
                if last_adx > 25:
                    signals.append("STRONG_TREND")
                else:
                    signals.append("WEAK_TREND")

                adx_strength = min(max(last_adx, 0.0), 100.0)
                score_components.append(adx_strength)

        # Momentum Evaluation (Normalized via percentage/rolling volatility or clipped scale)
        if "momentum_5" in df.columns and "close" in df.columns:
            last_mom = df["momentum_5"].iloc[-1]
            last_close = df["close"].iloc[-1]
            if not pd.isna(last_mom) and not pd.isna(last_close) and last_close > 0:
                # Relative percentage momentum normalization to handle different asset scales (BTC vs DOGE)
                rel_momentum = (last_mom / last_close) * 100.0
                if rel_momentum > 0:
                    signals.append("MOMENTUM_POSITIVE")
                elif rel_momentum < 0:
                    signals.append("MOMENTUM_NEGATIVE")

                # Scale percentage momentum into a 0-100 score bounds (e.g., 5% move = 100 strength)
                mom_strength = min(abs(rel_momentum) * 20.0, 100.0)
                score_components.append(mom_strength)

        if not score_components:
            return 50.0

        # Pure Python average calculation without numpy dependency
        mean_strength = sum(score_components) / len(score_components)
        return min(max(mean_strength, 0.0), 100.0)