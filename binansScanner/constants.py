"""
===============================================================================
Badee Binance Scanner
Architecture: ORION
Module: constants.py
Version: 1.0.0
===============================================================================

Central immutable constants used across the entire project.

Rules:
- This module contains ONLY architectural constants.
- No business logic.
- No helper functions.
- No trading strategy values.
- User-configurable values belong to settings.py.
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass


# =============================================================================
# Project Constants
# =============================================================================

@dataclass(frozen=True, slots=True)
class ProjectConstants:
    """
    Global project information.

    These values identify the project architecture and are not intended
    to change during runtime.
    """

    PROJECT_NAME: str = "Badee Binance Scanner"
    PROJECT_VERSION: str = "1.0.0"
    ARCHITECTURE_NAME: str = "ORION"
    ARCHITECTURE_VERSION: str = "1.0"
    AUTHOR: str = "Badee"
    DEFAULT_EXCHANGE: str = "binance"
    DEFAULT_MARKET_TYPE: str = "spot"
    DEFAULT_QUOTE_ASSET: str = "USDT"
    DEFAULT_TIMEZONE: str = "UTC"
    DEFAULT_ENCODING: str = "utf-8"


# =============================================================================
# Market Constants
# =============================================================================

@dataclass(frozen=True, slots=True)
class MarketConstants:
    """
    Market data architecture constants.

    These values define the market data contract used across
    the entire analysis pipeline.
    """

    SUPPORTED_TIMEFRAMES: tuple[str, ...] = (
        "15m",
        "1h",
        "4h",
    )
    DEFAULT_TIMEFRAME: str = "15m"
    MAX_HISTORY_CANDLES: int = 300
    MIN_REQUIRED_CANDLES: int = 60
    MAX_NEW_CANDLES_PER_UPDATE: int = 50
    OHLCV_COLUMNS: tuple[str, ...] = (
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    )
    TIMESTAMP_COLUMN: str = "timestamp"
    PRICE_COLUMNS: tuple[str, ...] = (
        "open",
        "high",
        "low",
        "close",
    )
    VOLUME_COLUMN: str = "volume"
    REQUIRED_COLUMNS: tuple[str, ...] = (
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    )


# =============================================================================
# Storage Constants
# =============================================================================

@dataclass(frozen=True, slots=True)
class StorageConstants:
    """
    Local cache and storage constants.
    """

    CACHE_DIRECTORY: str = "market_cache"
    PARQUET_EXTENSION: str = ".parquet"
    TEMP_DIRECTORY: str = "temp"
    BACKUP_DIRECTORY: str = "backup"
    LOG_DIRECTORY: str = "logs"
    REPORT_DIRECTORY: str = "reports"
    DATE_FORMAT: str = "%Y-%m-%d"
    DATETIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"
    PARQUET_ENGINE: str = "pyarrow"
    COMPRESSION: str = "snappy"
    INDEX_COLUMN: str = "timestamp"


# =============================================================================
# Indicator Constants
# =============================================================================

@dataclass(frozen=True, slots=True)
class IndicatorConstants:
    """
    Technical indicator default parameters.

    These are architectural defaults used by the indicator engine.
    Trading strategy thresholds belong to settings.py.
    """

    EMA_FAST_PERIOD: int = 9
    EMA_MEDIUM_PERIOD: int = 20
    EMA_TREND_PERIOD: int = 21
    EMA_SLOW_PERIOD: int = 50
    EMA_LONG_PERIOD: int = 200
    RSI_PERIOD: int = 14
    ADX_PERIOD: int = 14
    ATR_PERIOD: int = 14
    VWAP_SOURCE: str = "typical_price"
    MOMENTUM_PERIOD: int = 5
    VOLUME_AVERAGE_PERIOD: int = 20
    DISTANCE_EMA_PERIOD: int = 20
    CANDLE_STRENGTH_LOOKBACK: int = 1


# =============================================================================
# Scanner Constants
# =============================================================================

@dataclass(frozen=True, slots=True)
class ScannerConstants:
    """
    Scanner engine architectural constants.
    """

    MAX_SCAN_ERRORS: int = 25
    MAX_SYMBOLS_PER_BATCH: int = 100
    DEFAULT_BATCH_SIZE: int = 50
    UPDATE_BATCH_SIZE: int = 50
    ENABLE_INCREMENTAL_UPDATE: bool = True
    SAVE_AFTER_EACH_SYMBOL: bool = False
    CONTINUE_ON_SYMBOL_ERROR: bool = True
    SORT_RESULTS_BY_SCORE: bool = True
    REPORT_TOP_RESULTS: int = 20
    DEFAULT_LOG_LEVEL: str = "INFO"
    DEFAULT_REPORT_NAME: str = "scan_report"
    DEFAULT_HISTORY_FILE: str = "scan_history.parquet"


# =============================================================================
# Network Constants
# =============================================================================

@dataclass(frozen=True, slots=True)
class NetworkConstants:
    """
    Network and API communication constants.

    These values define the default behavior of network
    communication with Binance.
    """

    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    RETRY_DELAY_SECONDS: float = 1.0
    REQUEST_DELAY_SECONDS: float = 0.15
    ENABLE_RATE_LIMIT: bool = True
    HTTP_OK: int = 200
    HTTP_TOO_MANY_REQUESTS: int = 429
    HTTP_SERVER_ERROR: int = 500


# =============================================================================
# Report Constants
# =============================================================================

@dataclass(frozen=True, slots=True)
class ReportConstants:
    """
    Report formatting constants.
    """

    DEFAULT_DECIMAL_PLACES: int = 2
    PERCENT_DECIMAL_PLACES: int = 2
    PRICE_DECIMAL_PLACES: int = 8
    SCORE_DECIMAL_PLACES: int = 1
    REPORT_SEPARATOR: str = "=" * 80
    SECTION_SEPARATOR: str = "-" * 80
    EMPTY_VALUE: str = "-"
    DEFAULT_EXPORT_ENCODING: str = "utf-8"
    DEFAULT_REPORT_EXTENSION: str = ".txt"


# =============================================================================
# End Of File
# =============================================================================