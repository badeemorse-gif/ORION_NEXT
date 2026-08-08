"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : scheduler.scheduler_models
Version      : 1.0.1
Status       : ORION Production V1.0 APPROVED
===============================================================================

Scheduler data models representing immutable data structures for job definitions,
execution states, and scheduler health snapshots without thread or runtime logic.
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class JobStatus(Enum):
    """Enumeration of valid execution states for a scheduled job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class ScheduledJob:
    """Immutable job definition structure representing a scheduled task configuration."""
    job_id: str
    job_name: str
    interval_seconds: int
    enabled: bool
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class JobExecution:
    """Immutable record tracking the lifecycle state and execution timestamps of a scheduled job."""
    job_id: str
    started_at: datetime
    finished_at: datetime | None
    status: JobStatus
    error_message: str | None


@dataclass(frozen=True, slots=True)
class SchedulerState:
    """Immutable runtime snapshot detailing the operational status of the scheduler."""
    running: bool
    active_jobs: int
    last_tick: datetime | None


# =============================================================================
# End Of File
# =============================================================================