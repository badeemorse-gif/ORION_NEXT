"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : scheduler.scheduler_service
Version      : 1.0.0
Status       : ORION Production V1.0 INITIAL
===============================================================================

Scheduler Service Facade orchestrating the communication between the JobRegistry
and the SchedulerEngine to provide a unified, clean interface for the rest
of the system without containing low-level scheduling logic, threads, or loops.
===============================================================================
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from scheduler.scheduler_engine import SchedulerEngine
from scheduler.scheduler_jobs import JobRegistry, RegisteredJob
from scheduler.scheduler_models import (
    ScheduledJob,
    SchedulerState,
)

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class SchedulerServiceError(Exception):
    """Base exception class for all scheduler service related errors."""
    pass


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting scheduler service context attributes into log entries."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# Scheduler Service Facade
# =============================================================================

class SchedulerService:
    """
    Facade service coordinating job registrations, removals, and lifecycle control
    between the job registry and the underlying scheduler execution engine.
    """

    def __init__(
        self,
        engine: Optional[SchedulerEngine] = None,
        registry: Optional[JobRegistry] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._logger_instance = logger if logger is not None else base_logger
        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "component": "SchedulerService",
                "operation": "init",
            },
        )

        self._engine = engine if engine is not None else SchedulerEngine(logger=self._logger_instance)
        self._registry = registry if registry is not None else JobRegistry(logger=self._logger_instance)

        self._logger.info("SchedulerService initialized successfully.")

    def _get_logger(self, operation: Optional[str] = None) -> LoggerAdapter:
        return LoggerAdapter(
            self._logger_instance,
            {
                "component": "SchedulerService",
                "operation": operation,
            },
        )

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def register_job(self, job: ScheduledJob, callback: Callable[[], None]) -> None:
        """
        Registers a job in the job registry and propagates it to the scheduler engine.
        """
        logger = self._get_logger(operation="register_job")
        logger.info(f"Registering job '{job.job_id}' ('{job.job_name}') through scheduler service.")

        try:
            self._registry.register(job=job, callback=callback)
            self._engine.register_job(job=job, callback=callback)
            logger.info(f"Job '{job.job_id}' registered successfully across service components.")
        except Exception as err:
            logger.error(f"Failed to register job '{job.job_id}': {err}")
            raise SchedulerServiceError(f"Failed to register job '{job.job_id}': {err}") from err

    def remove_job(self, job_id: str) -> None:
        """
        Removes a job from both the job registry and the scheduler engine.
        """
        logger = self._get_logger(operation="remove_job")
        logger.info(f"Removing job '{job_id}' through scheduler service.")

        try:
            self._registry.remove(job_id=job_id)
            self._engine.remove_job(job_id=job_id)
            logger.info(f"Job '{job_id}' removed successfully across service components.")
        except Exception as err:
            logger.error(f"Failed to remove job '{job_id}': {err}")
            raise SchedulerServiceError(f"Failed to remove job '{job_id}': {err}") from err

    def start(self) -> None:
        """
        Starts the underlying scheduler engine loop.
        """
        logger = self._get_logger(operation="start")
        logger.info("Starting scheduler engine via scheduler service.")
        try:
            self._engine.start()
        except Exception as err:
            logger.error(f"Failed to start scheduler engine: {err}")
            raise SchedulerServiceError(f"Failed to start scheduler engine: {err}") from err

    def stop(self) -> None:
        """
        Stops the underlying scheduler engine loop.
        """
        logger = self._get_logger(operation="stop")
        logger.info("Stopping scheduler engine via scheduler service.")
        try:
            self._engine.stop()
        except Exception as err:
            logger.error(f"Failed to stop scheduler engine: {err}")
            raise SchedulerServiceError(f"Failed to stop scheduler engine: {err}") from err

    def state(self) -> SchedulerState:
        """
        Returns an immutable snapshot of the scheduler engine runtime status.
        """
        try:
            return self._engine.state()
        except Exception as err:
            self._get_logger(operation="state").error(f"Failed to retrieve scheduler state: {err}")
            raise SchedulerServiceError(f"Failed to retrieve scheduler state: {err}") from err

    def job_exists(self, job_id: str) -> bool:
        """
        Checks whether a job exists in the job registry.
        """
        try:
            return self._registry.exists(job_id=job_id)
        except Exception as err:
            self._get_logger(operation="job_exists").error(f"Failed to check job existence for '{job_id}': {err}")
            raise SchedulerServiceError(f"Failed to check job existence for '{job_id}': {err}") from err

    def registered_jobs(self) -> tuple[RegisteredJob, ...]:
        """
        Returns an immutable tuple containing all registered jobs from the job registry.
        """
        try:
            return self._registry.all_jobs()
        except Exception as err:
            self._get_logger(operation="registered_jobs").error(f"Failed to retrieve registered jobs: {err}")
            raise SchedulerServiceError(f"Failed to retrieve registered jobs: {err}") from err


# =============================================================================
# End Of File
# =============================================================================