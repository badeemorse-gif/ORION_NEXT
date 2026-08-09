"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : core.orchestrator
Version      : 4.1.0
Status       : ORION Production Candidate V4 with ExecutionPlan integration
===============================================================================

Core Orchestrator Engine acting as the strict, stateless pipeline coordinator
for all ORION production modules. Fully enforcing pure Dependency Injection
for both the immutable OrchestratorConfig and all execution components,
while utilizing a uniform `.execute()` protocol across every engine,
storage handler, provider, and validator.
===============================================================================
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable

from models.market import MarketDataset
from models.execution import ExecutionPlan

base_logger = logging.getLogger(__name__)


# =============================================================================
# Configuration & Enums
# =============================================================================

@dataclass(frozen=True)
class OrchestratorConfig:
    """Immutable configuration profile for the Orchestrator engine (Fully Injected)."""
    ENGINE_VERSION: str = "4.1.0"
    PIPELINE_VERSION: str = "1.0.0"
    ENABLE_TIMING: bool = True
    ENABLE_LOGGING: bool = True


class PipelineStage(str, Enum):
    """Enumeration of all sequential pipeline execution stages."""
    INITIALIZE = "INITIALIZE"
    DOWNLOAD = "DOWNLOAD"
    STORE = "STORE"
    INDICATORS = "INDICATORS"
    PROFILE = "PROFILE"
    SCORE = "SCORE"
    DECISION = "DECISION"
    REPORT = "REPORT"
    VALIDATION = "VALIDATION"
    FINISHED = "FINISHED"


# =============================================================================
# Uniform Execution Protocols (Strict Dependency Inversion Principle - DIP)
# =============================================================================

@runtime_checkable
class ExecutableProvider(Protocol):
    """Protocol defining a strict uniform .execute() interface for market data providers."""

    def execute(self, symbol: str, timeframes: list[str]) -> MarketDataset:
        """Fetch and return market dataset via uniform execute call."""
        ...


@runtime_checkable
class ExecutableStorage(Protocol):
    """Protocol defining a strict uniform .execute() interface for storage handlers."""

    def execute(self, dataset: MarketDataset) -> None:
        """Persist or save market dataset via uniform execute call."""
        ...


@runtime_checkable
class ExecutableEngine(Protocol):
    """Protocol defining a strict uniform .execute() interface for analytical engines."""

    def execute(self, dataset: MarketDataset) -> MarketDataset:
        """Process dataset through engine analysis via uniform execute call."""
        ...


@runtime_checkable
class ExecutableValidator(Protocol):
    """Protocol defining a strict uniform .execute() interface for validation engines."""

    def execute(self, dataset: MarketDataset) -> Any:
        """Validate dataset integrity via uniform execute call and return validation result."""
        ...


# =============================================================================
# Custom Exceptions
# =============================================================================

class OrchestratorError(Exception):
    """Base exception class for all orchestrator related failures."""
    pass


class PipelineError(OrchestratorError):
    """Raised when any specific pipeline stage fails during orchestration."""
    pass


# =============================================================================
# Dataclasses (Statistics & Results)
# =============================================================================

@dataclass(slots=True)
class PipelineStatistics:
    """Immutable metrics capturing granular details of a pipeline execution cycle."""
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    elapsed_ms: float = 0.0
    current_stage: PipelineStage = PipelineStage.INITIALIZE
    completed_stage_count: int = 0
    success: bool = False
    error_message: Optional[str] = None


@dataclass(slots=True)
class OrchestratorResult:
    """Container holding final dataset, validation results, and execution statistics."""
    dataset: Optional[MarketDataset] = None
    validation: Optional[Any] = None
    statistics: PipelineStatistics = field(default_factory=PipelineStatistics)
    execution_payload: Optional[ExecutionPlan] = None


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting stage and timing metrics into every log entry."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# Main Orchestrator Class
# =============================================================================

class Orchestrator:
    """
    Stateless, fully dependency-injected central pipeline orchestrator executing all
    production components exclusively via direct uniform .execute() calls, accepting
    both components and OrchestratorConfig strictly through constructor injection,
    with zero internal knowledge of component-specific methods or analytical logic.
    """

    def __init__(
        self,
        provider: ExecutableProvider,
        storage: ExecutableStorage,
        indicator_engine: ExecutableEngine,
        profile_engine: ExecutableEngine,
        score_engine: ExecutableEngine,
        decision_engine: ExecutableEngine,
        report_engine: ExecutableEngine,
        validation_engine: ExecutableValidator,
        config: OrchestratorConfig,
    ) -> None:
        if not provider:
            raise OrchestratorError("ExecutableProvider dependency is required.")
        if not storage:
            raise OrchestratorError("ExecutableStorage dependency is required.")
        if not indicator_engine:
            raise OrchestratorError("IndicatorEngine ExecutableEngine dependency is required.")
        if not profile_engine:
            raise OrchestratorError("ProfileEngine ExecutableEngine dependency is required.")
        if not score_engine:
            raise OrchestratorError("ScoreEngine ExecutableEngine dependency is required.")
        if not decision_engine:
            raise OrchestratorError("DecisionEngine ExecutableEngine dependency is required.")
        if not report_engine:
            raise OrchestratorError("ReportEngine ExecutableEngine dependency is required.")
        if not validation_engine:
            raise OrchestratorError("ValidationEngine ExecutableValidator dependency is required.")
        if not config:
            raise OrchestratorError("OrchestratorConfig dependency is required.")

        # Bind dependencies and injected config strictly
        self._provider = provider
        self._storage = storage
        self._indicator_engine = indicator_engine
        self._profile_engine = profile_engine
        self._score_engine = score_engine
        self._decision_engine = decision_engine
        self._report_engine = report_engine
        self._validation_engine = validation_engine
        self._config = config

        self._last_result: Optional[OrchestratorResult] = None
        self._current_stage = PipelineStage.INITIALIZE

        self._logger = LoggerAdapter(
            base_logger,
            {
                "symbol": "NONE",
                "stage": self._current_stage.value,
                "elapsed_ms": 0.0,
                "operation": "init",
            },
        )

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def run(self, symbol: str, timeframes: list[str]) -> OrchestratorResult:
        """Alias for run_pipeline for orchestrating analysis execution."""
        return self.run_pipeline(symbol=symbol, timeframes=timeframes)

    def run_pipeline(self, symbol: str, timeframes: list[str]) -> OrchestratorResult:
        """
        Execute the complete analysis pipeline sequentially through all components
        exclusively via direct uniform .execute() calls. Each stage is independently
        wrapped with robust error handling and precise performance tracking.
        """
        perf_start = time.perf_counter()
        started_at = datetime.now(timezone.utc)
        completed_count = 0

        self._logger.extra.update({
            "symbol": symbol,
            "stage": self._current_stage.value,
            "operation": "run_pipeline",
        })
        self._log_stage("Pipeline execution started.")

        dataset: Optional[MarketDataset] = None
        validation_result: Optional[Any] = None
        error_msg: Optional[str] = None
        success = False

        try:
            # Stage 1: Initialization
            self._initialize()
            completed_count += 1

            # Stage 2: Download Market Data via Provider (.execute)
            dataset = self._download(symbol=symbol, timeframes=timeframes)
            completed_count += 1

            # Stage 3: Storage & Persistence (.execute)
            self._store(dataset=dataset)
            completed_count += 1

            # Stage 4: Indicator Calculation (.execute)
            dataset = self._run_indicators(dataset=dataset)
            completed_count += 1

            # Stage 5: Market Profile Generation (.execute)
            dataset = self._run_profile(dataset=dataset)
            completed_count += 1

            # Stage 6: Scoring Evaluation (.execute)
            dataset = self._run_score(dataset=dataset)
            completed_count += 1

            # Stage 7: Decision Classification (.execute)
            dataset = self._run_decision(dataset=dataset)
            completed_count += 1

            # Stage 8: Report Building (.execute)
            dataset = self._run_report(dataset=dataset)
            completed_count += 1

            # Stage 9: Validation Inspection (.execute)
            validation_result = self._run_validation(dataset=dataset)
            completed_count += 1

            # Stage 10: Finalization
            self._finalize()
            success = True

        except Exception as e:
            error_msg = str(e)
            self._logger.error(f"Pipeline failed during stage [{self._current_stage.value}]: {error_msg}")
            if not isinstance(e, PipelineError):
                raise PipelineError(f"Pipeline error for symbol {symbol} at stage {self._current_stage.value}: {e}") from e
            raise

        finally:
            elapsed_ms = (time.perf_counter() - perf_start) * 1000.0 if self._config.ENABLE_TIMING else 0.0
            finished_at = datetime.now(timezone.utc)

            stats = PipelineStatistics(
                started_at=started_at,
                finished_at=finished_at,
                elapsed_ms=elapsed_ms,
                current_stage=self._current_stage,
                completed_stage_count=completed_count,
                success=success,
                error_message=error_msg,
            )

            execution_payload = self._build_execution_payload(dataset=dataset)

            self._last_result = OrchestratorResult(
                dataset=dataset,
                validation=validation_result,
                statistics=stats,
                execution_payload=execution_payload,
            )

            self._logger.extra.update({
                "stage": self._current_stage.value,
                "elapsed_ms": f"{elapsed_ms:.2f}ms",
            })
            self._log_stage(f"Pipeline execution finalized. Success: {success}")

        return self._last_result

    def reset(self) -> None:
        """Reset orchestrator state and cached execution result."""
        self._current_stage = PipelineStage.INITIALIZE
        self._last_result = None
        self._logger.extra.update({"stage": self._current_stage.value, "elapsed_ms": 0.0})
        self._log_stage("Orchestrator state reset.")

    def statistics(self) -> Optional[PipelineStatistics]:
        """Return execution statistics from the last pipeline run if available."""
        if self._last_result:
            return self._last_result.statistics
        return None

    def last_result(self) -> Optional[OrchestratorResult]:
        """Return the complete result container from the last pipeline run."""
        return self._last_result

    # -------------------------------------------------------------------------
    # Internal Pipeline Stage Methods (Stateless & Strictly .execute() Based)
    # -------------------------------------------------------------------------

    def _initialize(self) -> None:
        self._change_stage(PipelineStage.INITIALIZE)
        self._log_stage("Initializing pipeline execution parameters.")

    def _download(self, symbol: str, timeframes: list[str]) -> MarketDataset:
        self._change_stage(PipelineStage.DOWNLOAD)
        self._log_stage(f"Executing market data fetch for {symbol} across timeframes: {timeframes}")
        try:
            dataset = self._provider.execute(symbol=symbol, timeframes=timeframes)
            if not dataset:
                raise PipelineError("Provider returned empty or None dataset.")
            return dataset
        except Exception as e:
            raise PipelineError(f"Download stage failed: {e}") from e

    def _store(self, dataset: MarketDataset) -> None:
        self._change_stage(PipelineStage.STORE)
        self._log_stage("Executing dataset persistence into storage cache.")
        try:
            self._storage.execute(dataset)
        except Exception as e:
            raise PipelineError(f"Storage stage failed: {e}") from e

    def _run_indicators(self, dataset: MarketDataset) -> MarketDataset:
        self._change_stage(PipelineStage.INDICATORS)
        self._log_stage("Executing indicator engine via .execute().")
        try:
            return self._indicator_engine.execute(dataset)
        except Exception as e:
            raise PipelineError(f"Indicator calculation stage failed: {e}") from e

    def _run_profile(self, dataset: MarketDataset) -> MarketDataset:
        self._change_stage(PipelineStage.PROFILE)
        self._log_stage("Executing profile engine via .execute().")
        try:
            return self._profile_engine.execute(dataset)
        except Exception as e:
            raise PipelineError(f"Profile building stage failed: {e}") from e

    def _run_score(self, dataset: MarketDataset) -> MarketDataset:
        self._change_stage(PipelineStage.SCORE)
        self._log_stage("Executing score engine via .execute().")
        try:
            return self._score_engine.execute(dataset)
        except Exception as e:
            raise PipelineError(f"Score evaluation stage failed: {e}") from e

    def _run_decision(self, dataset: MarketDataset) -> MarketDataset:
        self._change_stage(PipelineStage.DECISION)
        self._log_stage("Executing decision engine via .execute().")
        try:
            return self._decision_engine.execute(dataset)
        except Exception as e:
            raise PipelineError(f"Decision classification stage failed: {e}") from e

    def _run_report(self, dataset: MarketDataset) -> MarketDataset:
        self._change_stage(PipelineStage.REPORT)
        self._log_stage("Executing report engine via .execute().")
        try:
            return self._report_engine.execute(dataset)
        except Exception as e:
            raise PipelineError(f"Report generation stage failed: {e}") from e

    def _run_validation(self, dataset: MarketDataset) -> Any:
        self._change_stage(PipelineStage.VALIDATION)
        self._log_stage("Executing validation engine via .execute().")
        try:
            return self._validation_engine.execute(dataset)
        except Exception as e:
            raise PipelineError(f"Validation inspection stage failed: {e}") from e

    def _finalize(self) -> None:
        self._change_stage(PipelineStage.FINISHED)
        self._log_stage("Pipeline successfully completed all stages.")

    # -------------------------------------------------------------------------
    # Internal Helper Methods
    # -------------------------------------------------------------------------

    def _build_execution_payload(self, dataset: Optional[MarketDataset]) -> Optional[ExecutionPlan]:
        if not dataset:
            return None
        
        try:
            symbol = getattr(dataset, "symbol", "UNKNOWN")
            decision_obj = getattr(dataset, "decision", None)
            
            side = "HOLD"
            confidence = 0.0
            if decision_obj is not None:
                if hasattr(decision_obj, "decision"):
                    dec_val = decision_obj.decision
                    side = dec_val.value if hasattr(dec_val, "value") else str(dec_val)
                elif isinstance(decision_obj, str):
                    side = decision_obj
                
                if hasattr(decision_obj, "confidence"):
                    confidence = float(getattr(decision_obj, "confidence", 0.0))

            price = 0.0
            if hasattr(dataset, "dataframes") and isinstance(dataset.dataframes, dict):
                for tf, df in dataset.dataframes.items():
                    if df is not None and not df.empty and "close" in df.columns:
                        price = float(df["close"].iloc[-1])
                        break

            quantity = 1.0

            return ExecutionPlan(
                symbol=symbol,
                side=side,
                price=price,
                quantity=quantity,
                confidence=confidence,
            )
        except Exception:
            return None

    def _change_stage(self, stage: PipelineStage) -> None:
        self._current_stage = stage
        self._logger.extra["stage"] = stage.value

    def _log_stage(self, message: str) -> None:
        if self._config.ENABLE_LOGGING:
            self._logger.info(message)


# =============================================================================
# End Of File
# =============================================================================