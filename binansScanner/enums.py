"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : enums.py
Version      : 1.0.0
===============================================================================

Domain enumerations used throughout the project.

This module defines all fixed domain values used by the system.
Magic strings are strictly prohibited outside this module.
===============================================================================
"""

from __future__ import annotations

from enum import Enum, IntEnum, auto


# =============================================================================
# Trade Modes
# =============================================================================

class TradeMode(Enum):
    """
    Market analysis mode determined by Data Profile Engine.
    """

    FULL_ANALYSIS = auto()
    LIMITED_ANALYSIS = auto()
    NEW_LISTING = auto()
    INSUFFICIENT_DATA = auto()


# =============================================================================
# Decision Types
# =============================================================================

class DecisionType(Enum):
    """
    Final decision produced by Decision Engine.
    """

    ENTRY_NOW = auto()
    WAIT_PULLBACK = auto()
    WAIT_CONFIRMATION = auto()
    WATCHLIST = auto()
    SKIP = auto()
    REJECT = auto()


# =============================================================================
# Decision Priority
# =============================================================================

class DecisionPriority(IntEnum):
    """
    Higher value = higher execution priority.
    """

    REJECT = 0
    SKIP = 1
    WATCHLIST = 2
    WAIT_CONFIRMATION = 3
    WAIT_PULLBACK = 4
    ENTRY_NOW = 5


# =============================================================================
# Profile Status
# =============================================================================

class ProfileStatus(Enum):
    """
    Data profile generation status.
    """

    VALID = auto()
    PARTIAL = auto()
    INVALID = auto()


# =============================================================================
# Data Health
# =============================================================================

class DataHealth(Enum):
    """
    Dataset quality classification.
    """

    EXCELLENT = auto()
    GOOD = auto()
    ACCEPTABLE = auto()
    POOR = auto()
    INVALID = auto()


# =============================================================================
# Timeframes
# =============================================================================

class Timeframe(Enum):
    """
    Supported Binance Spot timeframes.
    """

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


# =============================================================================
# Trend Direction
# =============================================================================

class TrendDirection(Enum):
    """
    Trend classification.
    """

    STRONG_BULLISH = auto()
    BULLISH = auto()
    SIDEWAYS = auto()
    BEARISH = auto()
    STRONG_BEARISH = auto()


# =============================================================================
# Market Phase
# =============================================================================

class MarketPhase(Enum):
    """
    Market structure phase.
    """

    ACCUMULATION = auto()
    MARKUP = auto()
    DISTRIBUTION = auto()
    MARKDOWN = auto()
    UNKNOWN = auto()


# =============================================================================
# Signal Strength
# =============================================================================

class SignalStrength(Enum):
    """
    Signal strength classification.
    """

    VERY_WEAK = auto()
    WEAK = auto()
    MODERATE = auto()
    STRONG = auto()
    VERY_STRONG = auto()


# =============================================================================
# Engine Status
# =============================================================================

class EngineStatus(Enum):
    """
    Execution status of internal engines.
    """

    SUCCESS = auto()
    WARNING = auto()
    ERROR = auto()
    SKIPPED = auto()


# =============================================================================
# Risk Level
# =============================================================================

class RiskLevel(Enum):
    """
    Risk classification.
    """

    VERY_LOW = auto()
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    VERY_HIGH = auto()


# =============================================================================
# Report Format
# =============================================================================

class ReportFormat(Enum):
    """
    Supported report formats.
    """

    TEXT = auto()
    JSON = auto()
    CSV = auto()


# =============================================================================
# End Of File
# =============================================================================