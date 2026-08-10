"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : application.application_runtime
Version      : 1.1.0
Status       : ORION Production V1.0
===============================================================================

Application Runtime Coordinator responsible for managing the application
lifecycle through the canonical DependencyContainer and Pipeline boundaries.
No service or execution component is constructed outside the composition root.
===============================================================================
"""

from __future__ import annotations

from typing import Iterable, Optional

from core.dependency_container import DependencyContainer
from core.pipeline import Pipeline, PipelineItemResult, PipelineSummary


class ApplicationRuntime:
    """Runtime facade over the canonical container-owned application pipeline."""

    def __init__(self, container: DependencyContainer) -> None:
        if container is None:
            raise ValueError("DependencyContainer is required.")
        self._container = container
        self._pipeline: Optional[Pipeline] = None

    def initialize(self) -> None:
        """Resolve the canonical Pipeline exactly once from the container."""
        if self._pipeline is None:
            self._pipeline = self._container.build_pipeline()

    def pipeline(self) -> Pipeline:
        """Return the initialized canonical pipeline."""
        if self._pipeline is None:
            self.initialize()
        assert self._pipeline is not None
        return self._pipeline

    def run_symbols(
        self,
        symbols: Iterable[str],
        timeframes: list[str],
        quantity: Optional[float] = None,
    ) -> tuple[PipelineSummary, list[PipelineItemResult]]:
        """Execute a symbol batch through the canonical application pipeline."""
        return self.pipeline().run_symbols(symbols, timeframes, quantity)

    def run_symbol(
        self,
        symbol: str,
        timeframes: list[str],
        quantity: Optional[float] = None,
    ) -> PipelineItemResult:
        """Execute one symbol through the canonical application pipeline."""
        return self.pipeline().run_symbol(symbol, timeframes, quantity)

    def summary(self) -> Optional[PipelineSummary]:
        """Return the latest pipeline summary without rebuilding the application."""
        return self.pipeline().statistics()

    def reset(self) -> None:
        """Clear application execution state while retaining container wiring."""
        self.pipeline().reset()

    def run(self) -> None:
        """Compatibility lifecycle entrypoint; initialize without inventing inputs."""
        self.initialize()

    def shutdown(self) -> None:
        """Release runtime-owned references; container ownership remains external."""
        self._pipeline = None

    def container(self) -> DependencyContainer:
        """Return the composition-root container managed by this runtime."""
        return self._container


# =============================================================================
# End Of File
# =============================================================================
