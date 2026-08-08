"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : scheduler.scheduler_jobs
Version      : 1.0.1
Status       : ORION Production V1.0 APPROVED
===============================================================================

Job Registry container responsible solely for storing, registering, retrieving,
and managing job definitions and their associated callbacks without executing
threads, loops, or scheduling logic.
===============================================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

from scheduler.scheduler_models import ScheduledJob

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class SchedulerJobsError(Exception):
    """Base exception class for all scheduler jobs registry related errors."""
    pass


# =============================================================================
# Registered Job Container
# =============================================================================

@dataclass(frozen=True, slots=True)
class RegisteredJob:
    """Immutable structure pairing a job definition with its executable callback."""
    definition: ScheduledJob
    callback: Callable[[], None]


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting scheduler jobs registry context attributes into log entries."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# Job Registry
# =============================================================================

class JobRegistry:
    """
    Registry responsible for storing job definitions and callbacks cleanly
    isolated from runtime scheduling and thread mechanics.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger_instance = logger if logger is not None else base_logger
        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "component": "JobRegistry",
                "operation": "init",
            },
        )

        self._jobs: dict[str, RegisteredJob] = {}
        self._logger.info("JobRegistry initialized successfully.")

    def _get_logger(self, operation: Optional[str] = None) -> LoggerAdapter:
        return LoggerAdapter(
            self._logger_instance,
            {
                "component": "JobRegistry",
                "operation": operation,
            },
        )

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def register(self, job: ScheduledJob, callback: Callable[[], None]) -> None:
        """
        Registers or updates a job definition and its execution callback in the registry.
        """
        logger = self._get_logger(operation="register")
        logger.info(f"Registering job '{job.job_id}' ('{job.job_name}') in job registry.")

        if not job.job_id:
            raise SchedulerJobsError("Cannot register job with empty job_id.")

        self._jobs[job.job_id] = RegisteredJob(
            definition=job,
            callback=callback,
        )
        logger.info(f"Job '{job.job_id}' registered in registry successfully.")

    def remove(self, job_id: str) -> None:
        """
        Removes a registered job from the registry by its identifier.
        """
        logger = self._get_logger(operation="remove")
        logger.info(f"Removing job '{job_id}' from job registry.")

        if job_id in self._jobs:
            del self._jobs[job_id]
            logger.info(f"Job '{job_id}' removed from registry successfully.")
        else:
            logger.warning(f"Job '{job_id}' not found in registry for removal.")

    def get(self, job_id: str) -> RegisteredJob:
        """
        Retrieves a registered job by its identifier. Raises SchedulerJobsError if not found.
        """
        logger = self._get_logger(operation="get")
        
        if job_id not in self._jobs:
            logger.error(f"Job '{job_id}' not found in registry.")
            raise SchedulerJobsError(f"Job '{job_id}' not found in registry.")

        return self._jobs[job_id]

    def exists(self, job_id: str) -> bool:
        """
        Checks whether a job exists in the registry.
        """
        return job_id in self._jobs

    def all_jobs(self) -> tuple[RegisteredJob, ...]:
        """
        Returns an immutable tuple containing all currently registered jobs.
        """
        return tuple(self._jobs.values())


# =============================================================================
# End Of File
# =============================================================================