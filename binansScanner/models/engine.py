"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : models.engine
Version      : 1.0.0
===============================================================================

Engine domain models.

These models describe the execution state of every engine
inside the scanner pipeline.
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from enums import EngineStatus


# =============================================================================
# Engine Metrics
# =============================================================================

@dataclass(slots=True)
class EngineMetrics:
    """
    Performance metrics collected during engine execution.
    """

    execution_time_ms: float

    processed_symbols: int

    successful_symbols: int

    failed_symbols: int

    skipped_symbols: int


# =============================================================================
# Engine Error
# =============================================================================

@dataclass(slots=True)
class EngineError:
    """
    Represents one execution error.
    """

    symbol: Optional[str]

    message: str

    exception_type: str

    timestamp: datetime


# =============================================================================
# Engine Result
# =============================================================================

@dataclass(slots=True)
class EngineResult:
    """
    Final execution result produced by any engine.
    """

    engine_name: str

    status: EngineStatus

    metrics: EngineMetrics

    errors: list[EngineError]

    started_at: datetime

    finished_at: datetime

    @property
    def execution_time_ms(self) -> float:
        """
        Returns total execution time.
        """
        return self.metrics.execution_time_ms

    @property
    def is_success(self) -> bool:
        """
        Returns True when engine execution completed successfully.
        """
        return self.status == EngineStatus.SUCCESS

    @property
    def has_errors(self) -> bool:
        """
        Returns True when execution contains errors.
        """
        return len(self.errors) > 0


# =============================================================================
# End Of File
# =============================================================================
