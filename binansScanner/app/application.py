"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : app.application
Version      : 1.0.0
Status       : ORION Production Candidate V1
===============================================================================

Orion Application Facade acting as the supreme official entry point for the
entire system. Responsible for application lifecycle management, workspace
initialization, configuration validation, and orchestrating the DependencyContainer
and Pipeline exclusively. Strictly enforcing clean architecture, pure facade design,
stateless execution, and zero domain or analytical business logic.
===============================================================================
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from core.dependency_container import (
    DependencyContainer,
    ContainerConfiguration,
)
from core.pipeline import (
    Pipeline,
    PipelineSummary,
    PipelineItemResult,
)

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class ApplicationError(Exception):
    """Base exception class for all application facade related failures."""
    pass


# =============================================================================
# Configuration Dataclass
# =============================================================================

@dataclass(frozen=True)
class ApplicationConfiguration:
    """Immutable configuration profile governing application workspace and execution parameters."""
    workspace: Path = field(default_factory=lambda: Path("./orion_workspace"))
    cache_directory: Path = field(default_factory=lambda: Path("./orion_workspace/cache"))
    logs_directory: Path = field(default_factory=lambda: Path("./orion_workspace/logs"))
    paper_trading: bool = True
    verbose_logging: bool = False


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting application operational context attributes into log entries."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# Main OrionApplication Class (Application Facade)
# =============================================================================

class OrionApplication:
    """
    Supreme Application Facade managing application startup, workspace preparation,
    container composition, pipeline execution, and lifecycle shutdown while keeping
    all analytical engines, storage providers, and core internals completely hidden.
    """

    VERSION = "ORION Production V1.0"

    def __init__(self, config: Optional[ApplicationConfiguration] = None) -> None:
        self._config = config if config is not None else ApplicationConfiguration()
        self._logger_instance = base_logger

        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "component": "OrionApplication",
                "state": "UNINITIALIZED",
            },
        )

        self._container: Optional[DependencyContainer] = None
        self._pipeline: Optional[Pipeline] = None
        self._startup_perf_counter: float = 0.0
        self._started_at: Optional[datetime] = None
        self._is_running: bool = False

        self._logger.info("OrionApplication instance instantiated.")

    # -------------------------------------------------------------------------
    # Public Methods (Lifecycle & Execution Facade)
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """Initialize the application workspace, logging, container composition, and pipeline."""
        self._startup_perf_counter = time.perf_counter()
        self._started_at = datetime.now(timezone.utc)

        self._logger.info("Starting OrionApplication...")

        try:
            # Step 1: Validate application configuration
            self._validate_configuration()

            # Step 2: Initialize physical workspace directories
            self._initialize_workspace()

            # Step 3: Initialize logging level and handlers
            self._initialize_logging()

            # Step 4: Build DependencyContainer via Composition Root
            self._container = self._build_container()

            # Step 5: Build Pipeline from Container
            self._pipeline = self._build_pipeline()

            self._is_running = True
            self._logger.extra["state"] = "RUNNING"
            self._logger.info(f"Application started successfully | Version={self.VERSION} | Workspace={self._config.workspace}")

        except Exception as e:
            self._logger.extra["state"] = "FAILED"
            self._logger.error(f"Fatal error during application startup: {e}")
            raise ApplicationError(f"Failed to start OrionApplication: {e}") from e

    def run_symbol(self, symbol: str, timeframes: list[str], quantity: Optional[float] = None) -> PipelineItemResult:
        """Execute analysis and execution workflow for a single trading symbol through the pipeline."""
        self._ensure_running()
        if self._pipeline is None:
            raise ApplicationError("Pipeline is not initialized.")

        try:
            self._logger.info(f"Application running symbol: {symbol}")
            return self._pipeline.run_symbol(symbol=symbol, timeframes=timeframes, quantity=quantity)
        except Exception as e:
            self._logger.error(f"Application failed to run symbol [{symbol}]: {e}")
            raise ApplicationError(f"Symbol execution failed: {e}") from e

    def run_symbols(self, symbols: Iterable[str], timeframes: list[str], quantity: Optional[float] = None) -> PipelineSummary:
        """Execute analysis and execution workflow across a batch of trading symbols through the pipeline."""
        self._ensure_running()
        if self._pipeline is None:
            raise ApplicationError("Pipeline is not initialized.")

        try:
            symbol_list = list(symbols)
            self._logger.info(f"Application running symbol batch: {symbol_list}")
            summary, _results = self._pipeline.run_symbols(
                symbols=symbol_list,
                timeframes=timeframes,
                quantity=quantity,
            )
            self._logger.info(
                "Application batch execution completed | "
                f"Processed={summary.processed_symbols} | "
                f"Successful={summary.successful_symbols}"
            )
            return summary
        except Exception as e:
            self._logger.error(f"Application failed to run symbol batch: {e}")
            raise ApplicationError(f"Batch symbol execution failed: {e}") from e

    def shutdown(self) -> None:
        """Safely shut down the application, reset container components, and flush states."""
        self._logger.info("Shutting down OrionApplication...")
        try:
            if self._pipeline is not None:
                self._pipeline.reset()
            if self._container is not None:
                self._container.reset()

            self._is_running = False
            self._logger.extra["state"] = "STOPPED"
            self._logger.info("Application stopped and shut down successfully.")
        except Exception as e:
            self._logger.error(f"Error during application shutdown: {e}")
            raise ApplicationError(f"Application shutdown failed: {e}") from e

    def reset(self) -> None:
        """Reset internal pipeline execution states and container caches."""
        self._ensure_running()
        if self._pipeline is not None:
            self._pipeline.reset()
        if self._container is not None:
            self._container.reset()
        self._logger.info("Application state reset successfully.")

    def summary(self) -> Optional[PipelineSummary]:
        """Return the aggregated summary metrics from the last pipeline execution run."""
        if self._pipeline is not None:
            return self._pipeline.statistics()
        return None

    def health(self) -> dict[str, Any]:
        """Perform system health checks and return operational metadata status."""
        running_time_ms = (time.perf_counter() - self._startup_perf_counter) * 1000.0 if self._is_running else 0.0
        pipeline_state = "READY" if self._pipeline is not None else "NOT_INITIALIZED"

        return {
            "status": "HEALTHY" if self._is_running else "STOPPED",
            "version": self.VERSION,
            "is_running": self._is_running,
            "pipeline_state": pipeline_state,
            "running_time_ms": running_time_ms,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "workspace": str(self._config.workspace),
        }

    def version(self) -> str:
        """Return the official production version string of the Orion Application."""
        return self.VERSION

    # -------------------------------------------------------------------------
    # Internal Methods (Protected Builders & Initializers)
    # -------------------------------------------------------------------------

    def _validate_configuration(self) -> None:
        if not self._config.workspace:
            raise ApplicationError("ApplicationConfiguration workspace path cannot be empty.")

    def _initialize_workspace(self) -> None:
        try:
            self._config.workspace.mkdir(parents=True, exist_ok=True)
            self._config.cache_directory.mkdir(parents=True, exist_ok=True)
            self._config.logs_directory.mkdir(parents=True, exist_ok=True)
            self._logger.info(f"Workspace directories initialized at: {self._config.workspace}")
        except Exception as e:
            raise ApplicationError(f"Failed to initialize workspace directories: {e}") from e

    def _initialize_logging(self) -> None:
        level = logging.DEBUG if self._config.verbose_logging else logging.INFO
        if not logging.getLogger().handlers:
            logging.basicConfig(
                level=level,
                format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            )
        self._logger_instance.setLevel(level)
        self._logger.info(f"Logging initialized with level: {logging.getLevelName(level)}")

    def _build_container(self) -> DependencyContainer:
        try:
            container_config = ContainerConfiguration(
                logger=self._logger_instance,
                paper_trading_enabled=self._config.paper_trading,
                cache_enabled=True,
            )
            container = DependencyContainer(config=container_config)
            self._logger.info("DependencyContainer built successfully within application facade.")
            return container
        except Exception as e:
            raise ApplicationError(f"Failed to build DependencyContainer: {e}") from e

    def _build_pipeline(self) -> Pipeline:
        if self._container is None:
            raise ApplicationError("DependencyContainer must be initialized before building the pipeline.")
        try:
            pipeline = self._container.build_pipeline()
            self._logger.info("Pipeline built successfully from DependencyContainer.")
            return pipeline
        except Exception as e:
            raise ApplicationError(f"Failed to build Pipeline from container: {e}") from e

    def _ensure_running(self) -> None:
        if not self._is_running or self._container is None or self._pipeline is None:
            raise ApplicationError("OrionApplication is not running. Call start() first.")


# =============================================================================
# End Of File
# =============================================================================
