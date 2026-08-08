"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : application.application_runtime
Version      : 1.0.0
Status       : ORION Production V1.0 INITIAL
===============================================================================

Application Runtime Coordinator responsible solely for managing the core execution
lifecycle (initialization, execution routing, and shutdown) using components
resolved exclusively from the DependencyContainer.
===============================================================================
"""

from __future__ import annotations

from typing import Optional

from core.dependency_container import DependencyContainer
from core.pipeline import Pipeline


# =============================================================================
# Application Runtime Coordinator
# =============================================================================

class ApplicationRuntime:
    """
    Runtime coordinator managing system lifecycle execution over the core pipeline
    resolved via the DependencyContainer composition root.
    """

    def __init__(self, container: DependencyContainer) -> None:
        self._container = container
        self._pipeline: Optional[Pipeline] = None

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def initialize(self) -> None:
        """
        Initializes the application runtime by building the pipeline from the container
        if not already initialized.
        """
        if self._pipeline is None:
            self._pipeline = self._container.build_pipeline()

    def pipeline(self) -> Pipeline:
        """
        Returns the active pipeline instance.
        Raises RuntimeError if the runtime has not been initialized.
        """
        if self._pipeline is None:
            raise RuntimeError("ApplicationRuntime has not been initialized. Call initialize() first.")
        return self._pipeline

    def run(self) -> None:
        """
        Initializes the runtime if necessary and triggers the runtime execution flow.
        """
        if self._pipeline is None:
            self.initialize()
        # Placeholder for actual pipeline execution loop in subsequent integration phases
        pass

    def shutdown(self) -> None:
        """
        Performs cleanup and shuts down runtime resources.
        """
        pass

    def container(self) -> DependencyContainer:
        """
        Returns the managed DependencyContainer instance.
        """
        return self._container


# =============================================================================
# End Of File
# =============================================================================