"""Canonical DecisionResult -> ExecutionPlan planning boundary for ORION."""
from __future__ import annotations

from models.decision import DecisionResult
from models.execution import ExecutionPlan, ExecutionSide
from models.market import MarketDataset


class ExecutionPlanBuilder:
    """Build execution intent without coupling planning to Orchestrator."""

    _DECISION_TO_SIDE = {
        "FAVORABLE": ExecutionSide.BUY,
        "UNFAVORABLE": ExecutionSide.SELL,
        "WAIT": ExecutionSide.HOLD,
    }

    def build(
        self,
        dataset: MarketDataset | None,
        decision: DecisionResult | None,
    ) -> ExecutionPlan | None:
        """Translate a completed decision and current market price into a plan."""
        if dataset is None or decision is None:
            return None

        decision_name = str(decision.decision).strip().upper()
        side = self._DECISION_TO_SIDE.get(decision_name, ExecutionSide.NONE)
        price = self._latest_close(dataset)

        return ExecutionPlan(
            symbol=dataset.symbol,
            side=side,
            price=price,
            quantity=1.0,
            confidence=float(decision.confidence),
            reason="; ".join(decision.reasons),
        )

    @staticmethod
    def _latest_close(dataset: MarketDataset) -> float:
        for timeframe_data in dataset.timeframes.values():
            dataframe = timeframe_data.dataframe
            if dataframe is not None and not dataframe.empty and "close" in dataframe.columns:
                return float(dataframe["close"].iloc[-1])
        return 0.0


__all__ = ["ExecutionPlanBuilder"]
