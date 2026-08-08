"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : scheduler.scheduler_engine
Version      : 1.1.0
Status       : ORION Production V1.1 APPROVED
===============================================================================

Lightweight custom Scheduler Engine responsible solely for managing job registrations,
intervals, and thread-safe execution loops using pure standard library threading
and time mechanisms without external scheduler dependencies.
===============================================================================
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional

from scheduler.scheduler_models import (
    ScheduledJob,
    SchedulerState,
)

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class SchedulerEngineError(Exception):
    """Base exception class for all scheduler engine related errors."""
    pass


# =============================================================================
# Internal Runtime Job Container
# =============================================================================

@dataclass(slots=True)
class _RuntimeJob:
    """Internal mutable representation tracking a registered job and its next scheduled execution time."""
    job: ScheduledJob
    callback: Callable[[], None]
    next_run: float


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting scheduler engine operation context attributes into log entries."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# Scheduler Engine
# =============================================================================

class SchedulerEngine:
    """
    Lightweight, thread-safe scheduler engine orchestrating periodic tasks
    within a single background worker thread using standard python primitives.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger_instance = logger if logger is not None else base_logger
        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "component": "SchedulerEngine",
                "operation": "init",
            },
        )

        self._jobs: dict[str, _RuntimeJob] = {}
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._lock: threading.Lock = threading.Lock()
        self._last_tick: Optional[datetime] = None

        self._logger.info("SchedulerEngine initialized successfully.")

    def _get_logger(self, operation: Optional[str] = None) -> LoggerAdapter:
        return LoggerAdapter(
            self._logger_instance,
            {
                "component": "SchedulerEngine",
                "operation": operation,
            },
        )

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def register_job(self, job: ScheduledJob, callback: Callable[[], None]) -> None:
        """
        Registers or updates a scheduled job along with its execution callback.
        """
        logger = self._get_logger(operation="register_job")
        logger.info(f"Registering job '{job.job_id}' ('{job.job_name}') with interval {job.interval_seconds}s.")

        with self._lock:
            interval = max(1, job.interval_seconds)
            next_run = time.time() + interval
            self._jobs[job.job_id] = _RuntimeJob(
                job=job,
                callback=callback,
                next_run=next_run,
            )
        logger.info(f"Job '{job.job_id}' registered successfully.")

    def remove_job(self, job_id: str) -> None:
        """
        Removes a registered job by its identifier.
        """
        logger = self._get_logger(operation="remove_job")
        logger.info(f"Removing job '{job_id}'.")

        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                logger.info(f"Job '{job_id}' removed successfully.")
            else:
                logger.warning(f"Job '{job_id}' not found for removal.")

    def start(self) -> None:
        """
        Starts the background scheduler loop if not already running.
        """
        logger = self._get_logger(operation="start")
        
        with self._lock:
            if self._running:
                logger.warning("Scheduler engine is already running.")
                return

            self._running = True
            self._thread = threading.Thread(
                target=self._run_loop,
                name="ORION-Scheduler-Thread",
                daemon=True,
            )
            self._thread.start()
            logger.info("Scheduler engine started successfully.")

    def stop(self) -> None:
        """
        Stops the background scheduler loop and waits for thread termination.
        """
        logger = self._get_logger(operation="stop")

        with self._lock:
            if not self._running:
                logger.warning("Scheduler engine is not running.")
                return

            self._running = False

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=3.0)
            self._thread = None

        logger.info("Scheduler engine stopped successfully.")

    def state(self) -> SchedulerState:
        """
        Returns an immutable snapshot of the scheduler runtime status.
        """
        with self._lock:
            active_count = sum(1 for rj in self._jobs.values() if rj.job.enabled)
            return SchedulerState(
                running=self._running,
                active_jobs=active_count,
                last_tick=self._last_tick,
            )

    # -------------------------------------------------------------------------
    # Internal Loop
    # -------------------------------------------------------------------------

    def _run_loop(self) -> None:
        """
        Background execution loop evaluating and dispatching due jobs every second.
        """
        logger = self._get_logger(operation="_run_loop")
        logger.info("Scheduler worker thread loop started.")

        while True:
            with self._lock:
                if not self._running:
                    break

            try:
                now = time.time()
                self._last_tick = datetime.now()

                due_callbacks: list[Callable[[], None]] = []

                with self._lock:
                    for job_id, runtime_job in self._jobs.items():
                        if not runtime_job.job.enabled:
                            continue

                        if now >= runtime_job.next_run:
                            due_callbacks.append(runtime_job.callback)
                            # Advance next run time
                            interval = max(1, runtime_job.job.interval_seconds)
                            runtime_job.next_run = now + interval

                # Execute due callbacks outside the lock to prevent deadlocks
                for cb in due_callbacks:
                    try:
                        cb()
                    except Exception as cb_err:
                        logger.error(f"Error executing scheduled job callback: {cb_err}")

            except Exception as loop_err:
                logger.error(f"Error in scheduler background loop: {loop_err}")

            # Sleep in small increments to respond swiftly to stop state changes
            time.sleep(1.0)

        logger.info("Scheduler worker thread loop terminated.")


# =============================================================================
# End Of File
# =============================================================================