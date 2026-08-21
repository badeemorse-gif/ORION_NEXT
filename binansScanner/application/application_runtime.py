"""Canonical application runtime facade, including paper pending-order lifecycle."""
from __future__ import annotations

from typing import Iterable, Optional

from core.dependency_container import DependencyContainer
from core.pipeline import Pipeline, PipelineItemResult, PipelineSummary
from services.pending_order_runtime import PaperPendingOrderRuntime


class ApplicationRuntime:
    """Runtime facade over the canonical container-owned application pipeline."""

    def __init__(self, container: DependencyContainer) -> None:
        if container is None:
            raise ValueError("DependencyContainer is required.")
        self._container = container
        self._pipeline: Optional[Pipeline] = None

    def initialize(self) -> None:
        if self._pipeline is None:
            self._pipeline = self._container.build_pipeline()

    def pipeline(self) -> Pipeline:
        if self._pipeline is None:
            self.initialize()
        assert self._pipeline is not None
        return self._pipeline

    def pending_order_runtime(self) -> PaperPendingOrderRuntime:
        """Return the container-owned D5 pending-order runtime used by the Paper Bot path."""
        return self._container.build_pending_order_runtime()

    def run_symbols(self, symbols: Iterable[str], timeframes: list[str], quantity: Optional[float] = None) -> tuple[PipelineSummary, list[PipelineItemResult]]:
        return self.pipeline().run_symbols(symbols, timeframes, quantity)

    def run_symbol(self, symbol: str, timeframes: list[str], quantity: Optional[float] = None) -> PipelineItemResult:
        return self.pipeline().run_symbol(symbol, timeframes, quantity)

    def summary(self) -> Optional[PipelineSummary]:
        return self.pipeline().statistics()

    def reset(self) -> None:
        self.pipeline().reset()
        self._container.build_pending_order_runtime().reset()

    def run(self) -> None:
        self.initialize()

    def shutdown(self) -> None:
        self._pipeline = None

    def container(self) -> DependencyContainer:
        return self._container
