"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : core.dependency_container
Version      : 1.4.0
Status       : ORION Production Candidate V1.4
===============================================================================

Composition Root of the ORION project responsible solely for object creation via
internal component factories, config-driven execution adapter selection,
dependency wiring, and singleton lifecycle management across all providers,
storage handlers, analytical engines, execution adapters, orchestrators,
and pipelines. Strictly enforcing clean architecture, pure dependency injection,
and zero business logic execution.
===============================================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Callable

from providers.binance_provider import BinanceProvider
from providers.market_data_provider import MarketDataProvider
from storage.market_storage import MarketStorage
from storage.sqlite_market_storage import SQLiteMarketStorage
from repositories.market_repository import MarketRepository
from services.market_service import MarketService

from engines.indicator_engine import IndicatorEngine
from engines.analysis_engine import AnalysisEngine
from engines.score_engine import ScoreEngine
from engines.decision_engine import DecisionEngine
from engines.report_engine import ReportEngine
from engines.validation_engine import ValidationEngine
from engines.execution_engine import (
    ExecutionEngine,
    PaperExecutionAdapter,
    ExecutionAdapter,
)

from core.orchestrator import (
    Orchestrator,
    OrchestratorConfig,
)

from core.pipeline import Pipeline

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class ContainerError(Exception):
    """Base exception class for all dependency container related failures."""
    pass


# =============================================================================
# Configuration Dataclass
# =============================================================================

@dataclass(frozen=True)
class ContainerConfiguration:
    """Immutable configuration profile governing container instantiation behavior."""
    logger: Optional[logging.Logger] = None
    orchestrator_config: Optional[OrchestratorConfig] = None
    paper_trading_enabled: bool = True
    cache_enabled: bool = True
    database_path: str = "market_data.db"
    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = False


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting container operation context attributes into log entries."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# Main DependencyContainer Class (Composition Root)
# =============================================================================

class DependencyContainer:
    """
    Pure Composition Root managing the singleton lifecycle and dependency wiring
    for all ORION production components using isolated internal factory methods,
    enforcing strict separation of concerns with zero business logic or exchange interaction.
    """

    def __init__(self, config: Optional[ContainerConfiguration] = None) -> None:
        self._config = config if config is not None else ContainerConfiguration()
        self._logger_instance = self._config.logger if self._config.logger is not None else base_logger

        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "component": "DependencyContainer",
                "operation": "init",
            },
        )

        # Singleton component cache stores
        self._binance_provider_instance: Optional[BinanceProvider] = None
        self._market_data_provider_instance: Optional[MarketDataProvider] = None
        self._market_storage_instance: Optional[MarketStorage] = None
        self._market_repository_instance: Optional[MarketRepository] = None
        self._market_service_instance: Optional[MarketService] = None

        self._indicator_engine_instance: Optional[IndicatorEngine] = None
        self._analysis_engine_instance: Optional[AnalysisEngine] = None
        self._score_engine_instance: Optional[ScoreEngine] = None
        self._decision_engine_instance: Optional[DecisionEngine] = None
        self._report_engine_instance: Optional[ReportEngine] = None
        self._validation_engine_instance: Optional[ValidationEngine] = None
        self._execution_adapter_instance: Optional[ExecutionAdapter] = None
        self._execution_engine_instance: Optional[ExecutionEngine] = None
        self._orchestrator_instance: Optional[Orchestrator] = None
        self._pipeline_instance: Optional[Pipeline] = None

        self._logger.info("DependencyContainer initialized successfully.")

    # -------------------------------------------------------------------------
    # Internal Component Factory Methods (Decoupled Concrete Instantiation)
    # -------------------------------------------------------------------------

    def _create_binance_provider(self) -> BinanceProvider:
        return BinanceProvider(
            api_key=self._config.binance_api_key,
            api_secret=self._config.binance_api_secret,
            testnet=self._config.binance_testnet,
        )

    def _create_market_data_provider(self) -> MarketDataProvider:
        return MarketDataProvider(
            data_source=self.build_binance_provider(),
            logger=self._logger_instance,
        )

    def _create_market_storage(self) -> SQLiteMarketStorage:
        return SQLiteMarketStorage(
            database_path=self._config.database_path,
            logger=self._logger_instance,
        )

    def _create_market_repository(self) -> MarketRepository:
        return MarketRepository(
            market_provider=self.build_market_data_provider(),
            storage=self.build_market_storage(),
            logger=self._logger_instance,
        )

    def _create_market_service(self) -> MarketService:
        return MarketService(
            repository=self.build_market_repository(),
            logger=self._logger_instance,
        )

    def _create_indicator_engine(self) -> IndicatorEngine:
        return IndicatorEngine()

    def _create_analysis_engine(self) -> AnalysisEngine:
        return AnalysisEngine()

    def _create_score_engine(self) -> ScoreEngine:
        return ScoreEngine()

    def _create_decision_engine(self) -> DecisionEngine:
        return DecisionEngine()

    def _create_report_engine(self) -> ReportEngine:
        return ReportEngine()

    def _create_validation_engine(self) -> ValidationEngine:
        return ValidationEngine()

    def _create_execution_adapter(self) -> ExecutionAdapter:
        if self._config.paper_trading_enabled:
            return PaperExecutionAdapter()
        return PaperExecutionAdapter()

    # -------------------------------------------------------------------------
    # Public Builder Methods (Strict Singleton Lifetime)
    # -------------------------------------------------------------------------

    def build_binance_provider(self) -> BinanceProvider:
        """Create or return the singleton instance of BinanceProvider."""
        if self._binance_provider_instance is None:
            try:
                self._binance_provider_instance = self._create_binance_provider()
                self._logger.info("BinanceProvider singleton instance created.")
            except Exception as e:
                raise ContainerError(f"Failed to build BinanceProvider: {e}") from e
        return self._binance_provider_instance

    def build_market_data_provider(self) -> MarketDataProvider:
        """Create or return the singleton instance of MarketDataProvider."""
        if self._market_data_provider_instance is None:
            try:
                self._market_data_provider_instance = self._create_market_data_provider()
                self._logger.info("MarketDataProvider singleton instance created.")
            except Exception as e:
                raise ContainerError(f"Failed to build MarketDataProvider: {e}") from e
        return self._market_data_provider_instance

    def build_market_storage(self) -> MarketStorage:
        """Create or return the singleton instance of MarketStorage (SQLiteMarketStorage)."""
        if self._market_storage_instance is None:
            try:
                self._market_storage_instance = self._create_market_storage()
                self._logger.info("MarketStorage singleton instance created.")
            except Exception as e:
                raise ContainerError(f"Failed to build MarketStorage: {e}") from e
        return self._market_storage_instance

    def build_market_repository(self) -> MarketRepository:
        """Create or return the singleton instance of MarketRepository."""
        if self._market_repository_instance is None:
            try:
                self._market_repository_instance = self._create_market_repository()
                self._logger.info("MarketRepository singleton instance created.")
            except Exception as e:
                raise ContainerError(f"Failed to build MarketRepository: {e}") from e
        return self._market_repository_instance

    def build_market_service(self) -> MarketService:
        """Create or return the singleton instance of MarketService."""
        if self._market_service_instance is None:
            try:
                self._market_service_instance = self._create_market_service()
                self._logger.info("MarketService singleton instance created.")
            except Exception as e:
                raise ContainerError(f"Failed to build MarketService: {e}") from e
        return self._market_service_instance

    def build_indicator_engine(self) -> IndicatorEngine:
        """Create or return the singleton instance of IndicatorEngine."""
        if self._indicator_engine_instance is None:
            try:
                self._indicator_engine_instance = self._create_indicator_engine()
                self._logger.info("IndicatorEngine singleton instance created.")
            except Exception as e:
                raise ContainerError(f"Failed to build IndicatorEngine: {e}") from e
        return self._indicator_engine_instance

    def build_analysis_engine(self) -> AnalysisEngine:
        """Create or return the singleton instance of AnalysisEngine."""
        if self._analysis_engine_instance is None:
            try:
                self._analysis_engine_instance = self._create_analysis_engine()
                self._logger.info("AnalysisEngine singleton instance created.")
            except Exception as e:
                raise ContainerError(f"Failed to build AnalysisEngine: {e}") from e
        return self._analysis_engine_instance

    def build_score_engine(self) -> ScoreEngine:
        """Create or return the singleton instance of ScoreEngine."""
        if self._score_engine_instance is None:
            try:
                self._score_engine_instance = self._create_score_engine()
                self._logger.info("ScoreEngine singleton instance created.")
            except Exception as e:
                raise ContainerError(f"Failed to build ScoreEngine: {e}") from e
        return self._score_engine_instance

    def build_decision_engine(self) -> DecisionEngine:
        """Create or return the singleton instance of DecisionEngine."""
        if self._decision_engine_instance is None:
            try:
                self._decision_engine_instance = self._create_decision_engine()
                self._logger.info("DecisionEngine singleton instance created.")
            except Exception as e:
                raise ContainerError(f"Failed to build DecisionEngine: {e}") from e
        return self._decision_engine_instance

    def build_report_engine(self) -> ReportEngine:
        """Create or return the singleton instance of ReportEngine."""
        if self._report_engine_instance is None:
            try:
                self._report_engine_instance = self._create_report_engine()
                self._logger.info("ReportEngine singleton instance created.")
            except Exception as e:
                raise ContainerError(f"Failed to build ReportEngine: {e}") from e
        return self._report_engine_instance

    def build_validation_engine(self) -> ValidationEngine:
        """Create or return the singleton instance of ValidationEngine."""
        if self._validation_engine_instance is None:
            try:
                self._validation_engine_instance = self._create_validation_engine()
                self._logger.info("ValidationEngine singleton instance created.")
            except Exception as e:
                raise ContainerError(f"Failed to build ValidationEngine: {e}") from e
        return self._validation_engine_instance

    def build_execution_engine(self) -> ExecutionEngine:
        """Create or return the singleton instance of ExecutionEngine wired with config-driven ExecutionAdapter."""
        if self._execution_engine_instance is None:
            try:
                if self._execution_adapter_instance is None:
                    self._execution_adapter_instance = self._create_execution_adapter()

                self._execution_engine_instance = ExecutionEngine(
                    adapter=self._execution_adapter_instance,
                    logger=self._logger_instance,
                )
                self._logger.info("ExecutionEngine singleton instance created with configured ExecutionAdapter.")
            except Exception as e:
                raise ContainerError(f"Failed to build ExecutionEngine: {e}") from e
        return self._execution_engine_instance

    def build_orchestrator(self) -> Orchestrator:
        """Create or return the singleton instance of Orchestrator wired with all core engines, provider, storage, and config."""
        if self._orchestrator_instance is None:
            try:
                market_service = self.build_market_service()
                indicator_engine = self.build_indicator_engine()
                analysis_engine = self.build_analysis_engine()
                score_engine = self.build_score_engine()
                decision_engine = self.build_decision_engine()
                report_engine = self.build_report_engine()
                validation_engine = self.build_validation_engine()
                
                orch_config = self._config.orchestrator_config
                if orch_config is None:
                    orch_config = OrchestratorConfig()

                self._orchestrator_instance = Orchestrator(
                    market_service=market_service,
                    indicator_engine=indicator_engine,
                    analysis_engine=analysis_engine,
                    score_engine=score_engine,
                    decision_engine=decision_engine,
                    report_engine=report_engine,
                    validation_engine=validation_engine,
                    config=orch_config,
                )
                self._logger.info("Orchestrator singleton instance created and fully wired.")
            except Exception as e:
                raise ContainerError(f"Failed to build Orchestrator: {e}") from e
        return self._orchestrator_instance

    def build_pipeline(self) -> Pipeline:
        """Create or return the singleton instance of Pipeline wired exclusively with Orchestrator and ExecutionEngine."""
        if self._pipeline_instance is None:
            try:
                orchestrator = self.build_orchestrator()
                execution_engine = self.build_execution_engine()

                self._pipeline_instance = Pipeline(
                    orchestrator=orchestrator,
                    execution_engine=execution_engine,
                    logger=self._logger_instance,
                )
                self._logger.info("Pipeline singleton instance created and fully wired.")
            except Exception as e:
                raise ContainerError(f"Failed to build Pipeline: {e}") from e
        return self._pipeline_instance

    def reset(self) -> None:
        """Reset all cached singleton instances to clear container state."""
        self._binance_provider_instance = None
        self._market_data_provider_instance = None
        self._market_storage_instance = None
        self._market_repository_instance = None
        self._market_service_instance = None

        self._indicator_engine_instance = None
        self._analysis_engine_instance = None
        self._score_engine_instance = None
        self._decision_engine_instance = None
        self._report_engine_instance = None
        self._validation_engine_instance = None
        self._execution_adapter_instance = None
        self._execution_engine_instance = None
        self._orchestrator_instance = None
        self._pipeline_instance = None

        self._logger.info("DependencyContainer singleton instances reset.")

    def logger(self) -> logging.Logger:
        """Return the shared logging instance used across all container-managed services."""
        return self._logger_instance


# =============================================================================
# End Of File
# =============================================================================