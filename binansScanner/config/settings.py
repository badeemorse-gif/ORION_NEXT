"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : config.settings
Version      : 1.0.0
Status       : ORION Production Candidate V1
===============================================================================

Centralized Configuration and Settings Management Module for the ORION project.
Responsible for providing strongly-typed, immutable frozen dataclasses for all system
subsystems (Binance, Cache, Logging, Trading, Risk, Scanner, and OrionSettings)
alongside a robust SettingsLoader utility handling environment variables, default profiles,
JSON file serialization, and comprehensive structural and logical validation.
Strictly enforcing clean architecture and zero business logic or exchange coupling.
===============================================================================
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class SettingsError(Exception):
    """Base exception class for all settings and configuration related failures."""
    pass


class SettingsValidationError(SettingsError):
    """Raised when configuration parameters fail validation rules or integrity checks."""
    pass


# =============================================================================
# Configuration Subsystem Dataclasses (Frozen & Fully Typed)
# =============================================================================

@dataclass(frozen=True, slots=True)
class BinanceSettings:
    """Immutable settings governing Binance exchange connection parameters."""
    api_key: str = ""
    api_secret: str = ""
    testnet: bool = True
    base_url: str = "https://testnet.binance.vision"
    request_timeout: float = 10.0
    recv_window: int = 5000


@dataclass(frozen=True, slots=True)
class CacheSettings:
    """Immutable settings governing market and pipeline data caching behavior."""
    enabled: bool = True
    directory: Path = field(default_factory=lambda: Path("./orion_workspace/cache"))
    max_size_mb: int = 512
    expiration_minutes: int = 60


@dataclass(frozen=True, slots=True)
class LoggingSettings:
    """Immutable settings governing system logging, output sinks, and rotation files."""
    level: str = "INFO"
    directory: Path = field(default_factory=lambda: Path("./orion_workspace/logs"))
    filename: str = "orion_production.log"
    rotation_mb: int = 10
    backup_files: int = 5
    console_output: bool = True


@dataclass(frozen=True, slots=True)
class TradingSettings:
    """Immutable settings governing general order execution and trading modes."""
    paper_trading: bool = True
    default_quantity: float = 1.0
    max_open_positions: int = 5
    allow_short: bool = True
    allow_long: bool = True


@dataclass(frozen=True, slots=True)
class RiskSettings:
    """Immutable settings governing risk management thresholds and position constraints."""
    max_daily_loss: float = 0.05
    max_position_size: float = 0.20
    risk_per_trade: float = 0.01
    stop_loss_percent: float = 0.02
    take_profit_percent: float = 0.04


@dataclass(frozen=True, slots=True)
class ScannerSettings:
    """Immutable settings governing market symbol scanning frequencies and scopes."""
    default_timeframes: tuple[str, ...] = ("1h", "4h", "1d")
    max_parallel_symbols: int = 10
    default_symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT")
    refresh_interval_seconds: int = 300


@dataclass(frozen=True, slots=True)
class OrionSettings:
    """Master immutable aggregate configuration structure enclosing all system subsystems."""
    workspace: Path = field(default_factory=lambda: Path("./orion_workspace"))
    binance: BinanceSettings = field(default_factory=BinanceSettings)
    cache: CacheSettings = field(default_factory=CacheSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    trading: TradingSettings = field(default_factory=TradingSettings)
    risk: RiskSettings = field(default_factory=RiskSettings)
    scanner: ScannerSettings = field(default_factory=ScannerSettings)


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting settings component context attributes into log entries."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# Settings Loader & Factory
# =============================================================================

class SettingsLoader:
    """
    Centralized factory and manager responsible for loading, merging, persisting,
    and rigorously validating OrionSettings from default profiles, environment variables,
    or external JSON configuration files.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger_instance = logger if logger is not None else base_logger
        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "component": "SettingsLoader",
                "operation": "init",
            },
        )
        self._logger.info("SettingsLoader initialized successfully.")

    def load_defaults(self) -> OrionSettings:
        """Create and return a default production-ready OrionSettings instance."""
        self._logger.info("Loading default OrionSettings configuration profile.")
        return OrionSettings()

    def load_from_environment(self, base_settings: Optional[OrionSettings] = None) -> OrionSettings:
        """
        Load configuration overrides from environment variables and merge them
        into the provided base settings or a fresh default settings profile.
        """
        self._logger.info("Loading configuration overrides from environment variables.")
        current = base_settings if base_settings is not None else self.load_defaults()

        try:
            # Workspace & General Env
            workspace = Path(os.getenv("ORION_WORKSPACE", current.workspace))

            # Binance Env
            binance_settings = BinanceSettings(
                api_key=os.getenv("ORION_BINANCE_API_KEY", current.binance.api_key),
                api_secret=os.getenv("ORION_BINANCE_API_SECRET", current.binance.api_secret),
                testnet=os.getenv("ORION_BINANCE_TESTNET", str(current.binance.testnet)).lower() in ("true", "1", "yes"),
                base_url=os.getenv("ORION_BINANCE_BASE_URL", current.binance.base_url),
                request_timeout=float(os.getenv("ORION_BINANCE_REQUEST_TIMEOUT", current.binance.request_timeout)),
                recv_window=int(os.getenv("ORION_BINANCE_RECV_WINDOW", current.binance.recv_window)),
            )

            # Cache Env
            cache_settings = CacheSettings(
                enabled=os.getenv("ORION_CACHE_ENABLED", str(current.cache.enabled)).lower() in ("true", "1", "yes"),
                directory=Path(os.getenv("ORION_CACHE_DIRECTORY", current.cache.directory)),
                max_size_mb=int(os.getenv("ORION_CACHE_MAX_SIZE_MB", current.cache.max_size_mb)),
                expiration_minutes=int(os.getenv("ORION_CACHE_EXPIRATION_MINUTES", current.cache.expiration_minutes)),
            )

            # Logging Env
            logging_settings = LoggingSettings(
                level=os.getenv("ORION_LOGGING_LEVEL", current.logging.level),
                directory=Path(os.getenv("ORION_LOGGING_DIRECTORY", current.logging.directory)),
                filename=os.getenv("ORION_LOGGING_FILENAME", current.logging.filename),
                rotation_mb=int(os.getenv("ORION_LOGGING_ROTATION_MB", current.logging.rotation_mb)),
                backup_files=int(os.getenv("ORION_LOGGING_BACKUP_FILES", current.logging.backup_files)),
                console_output=os.getenv("ORION_LOGGING_CONSOLE_OUTPUT", str(current.logging.console_output)).lower() in ("true", "1", "yes"),
            )

            # Trading Env
            trading_settings = TradingSettings(
                paper_trading=os.getenv("ORION_TRADING_PAPER_TRADING", str(current.trading.paper_trading)).lower() in ("true", "1", "yes"),
                default_quantity=float(os.getenv("ORION_TRADING_DEFAULT_QUANTITY", current.trading.default_quantity)),
                max_open_positions=int(os.getenv("ORION_TRADING_MAX_OPEN_POSITIONS", current.trading.max_open_positions)),
                allow_short=os.getenv("ORION_TRADING_ALLOW_SHORT", str(current.trading.allow_short)).lower() in ("true", "1", "yes"),
                allow_long=os.getenv("ORION_TRADING_ALLOW_LONG", str(current.trading.allow_long)).lower() in ("true", "1", "yes"),
            )

            # Risk Env
            risk_settings = RiskSettings(
                max_daily_loss=float(os.getenv("ORION_RISK_MAX_DAILY_LOSS", current.risk.max_daily_loss)),
                max_position_size=float(os.getenv("ORION_RISK_MAX_POSITION_SIZE", current.risk.max_position_size)),
                risk_per_trade=float(os.getenv("ORION_RISK_RISK_PER_TRADE", current.risk.risk_per_trade)),
                stop_loss_percent=float(os.getenv("ORION_RISK_STOP_LOSS_PERCENT", current.risk.stop_loss_percent)),
                take_profit_percent=float(os.getenv("ORION_RISK_TAKE_PROFIT_PERCENT", current.risk.take_profit_percent)),
            )

            # Scanner Env
            env_timeframes = os.getenv("ORION_SCANNER_DEFAULT_TIMEFRAMES")
            timeframes = tuple(env_timeframes.split(",")) if env_timeframes else current.scanner.default_timeframes

            env_symbols = os.getenv("ORION_SCANNER_DEFAULT_SYMBOLS")
            symbols = tuple(env_symbols.split(",")) if env_symbols else current.scanner.default_symbols

            scanner_settings = ScannerSettings(
                default_timeframes=timeframes,
                max_parallel_symbols=int(os.getenv("ORION_SCANNER_MAX_PARALLEL_SYMBOLS", current.scanner.max_parallel_symbols)),
                default_symbols=symbols,
                refresh_interval_seconds=int(os.getenv("ORION_SCANNER_REFRESH_INTERVAL_SECONDS", current.scanner.refresh_interval_seconds)),
            )

            loaded_settings = OrionSettings(
                workspace=workspace,
                binance=binance_settings,
                cache=cache_settings,
                logging=logging_settings,
                trading=trading_settings,
                risk=risk_settings,
                scanner=scanner_settings,
            )

            self._logger.info("Environment configuration loaded and merged successfully.")
            return loaded_settings

        except Exception as e:
            raise SettingsError(f"Failed to load settings from environment variables: {e}") from e

    def load_from_file(self, file_path: Path | str) -> OrionSettings:
        """Load and parse OrionSettings from a JSON configuration file on disk."""
        path = Path(file_path)
        self._logger.info(f"Loading OrionSettings configuration from file: {path}")

        if not path.exists():
            raise SettingsError(f"Configuration file does not exist at path: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            workspace = Path(data.get("workspace", "./orion_workspace"))

            b_data = data.get("binance", {})
            binance_settings = BinanceSettings(
                api_key=b_data.get("api_key", ""),
                api_secret=b_data.get("api_secret", ""),
                testnet=b_data.get("testnet", True),
                base_url=b_data.get("base_url", "https://testnet.binance.vision"),
                request_timeout=float(b_data.get("request_timeout", 10.0)),
                recv_window=int(b_data.get("recv_window", 5000)),
            )

            c_data = data.get("cache", {})
            cache_settings = CacheSettings(
                enabled=c_data.get("enabled", True),
                directory=Path(c_data.get("directory", "./orion_workspace/cache")),
                max_size_mb=int(c_data.get("max_size_mb", 512)),
                expiration_minutes=int(c_data.get("expiration_minutes", 60)),
            )

            l_data = data.get("logging", {})
            logging_settings = LoggingSettings(
                level=l_data.get("level", "INFO"),
                directory=Path(l_data.get("directory", "./orion_workspace/logs")),
                filename=l_data.get("filename", "orion_production.log"),
                rotation_mb=int(l_data.get("rotation_mb", 10)),
                backup_files=int(l_data.get("backup_files", 5)),
                console_output=l_data.get("console_output", True),
            )

            t_data = data.get("trading", {})
            trading_settings = TradingSettings(
                paper_trading=t_data.get("paper_trading", True),
                default_quantity=float(t_data.get("default_quantity", 1.0)),
                max_open_positions=int(t_data.get("max_open_positions", 5)),
                allow_short=t_data.get("allow_short", True),
                allow_long=t_data.get("allow_long", True),
            )

            r_data = data.get("risk", {})
            risk_settings = RiskSettings(
                max_daily_loss=float(r_data.get("max_daily_loss", 0.05)),
                max_position_size=float(r_data.get("max_position_size", 0.20)),
                risk_per_trade=float(r_data.get("risk_per_trade", 0.01)),
                stop_loss_percent=float(r_data.get("stop_loss_percent", 0.02)),
                take_profit_percent=float(r_data.get("take_profit_percent", 0.04)),
            )

            s_data = data.get("scanner", {})
            scanner_settings = ScannerSettings(
                default_timeframes=tuple(s_data.get("default_timeframes", ("1h", "4h", "1d"))),
                max_parallel_symbols=int(s_data.get("max_parallel_symbols", 10)),
                default_symbols=tuple(s_data.get("default_symbols", ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"))),
                refresh_interval_seconds=int(s_data.get("refresh_interval_seconds", 300)),
            )

            settings = OrionSettings(
                workspace=workspace,
                binance=binance_settings,
                cache=cache_settings,
                logging=logging_settings,
                trading=trading_settings,
                risk=risk_settings,
                scanner=scanner_settings,
            )

            self._logger.info(f"Configuration file loaded successfully from {path}")
            return settings

        except Exception as e:
            raise SettingsError(f"Failed to load configuration from file {path}: {e}") from e

    def save(self, settings: OrionSettings, file_path: Path | str) -> None:
        """Serialize and save OrionSettings to a JSON configuration file on disk."""
        path = Path(file_path)
        self._logger.info(f"Saving OrionSettings configuration to file: {path}")

        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "workspace": str(settings.workspace),
                "binance": {
                    "api_key": settings.binance.api_key,
                    "api_secret": settings.binance.api_secret,
                    "testnet": settings.binance.testnet,
                    "base_url": settings.binance.base_url,
                    "request_timeout": settings.binance.request_timeout,
                    "recv_window": settings.binance.recv_window,
                },
                "cache": {
                    "enabled": settings.cache.enabled,
                    "directory": str(settings.cache.directory),
                    "max_size_mb": settings.cache.max_size_mb,
                    "expiration_minutes": settings.cache.expiration_minutes,
                },
                "logging": {
                    "level": settings.logging.level,
                    "directory": str(settings.logging.directory),
                    "filename": settings.logging.filename,
                    "rotation_mb": settings.logging.rotation_mb,
                    "backup_files": settings.logging.backup_files,
                    "console_output": settings.logging.console_output,
                },
                "trading": {
                    "paper_trading": settings.trading.paper_trading,
                    "default_quantity": settings.trading.default_quantity,
                    "max_open_positions": settings.trading.max_open_positions,
                    "allow_short": settings.trading.allow_short,
                    "allow_long": settings.trading.allow_long,
                },
                "risk": {
                    "max_daily_loss": settings.risk.max_daily_loss,
                    "max_position_size": settings.risk.max_position_size,
                    "risk_per_trade": settings.risk.risk_per_trade,
                    "stop_loss_percent": settings.risk.stop_loss_percent,
                    "take_profit_percent": settings.risk.take_profit_percent,
                },
                "scanner": {
                    "default_timeframes": list(settings.scanner.default_timeframes),
                    "max_parallel_symbols": settings.scanner.max_parallel_symbols,
                    "default_symbols": list(settings.scanner.default_symbols),
                    "refresh_interval_seconds": settings.scanner.refresh_interval_seconds,
                },
            }

            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

            self._logger.info(f"Configuration successfully saved to {path}")

        except Exception as e:
            raise SettingsError(f"Failed to save configuration to file {path}: {e}") from e

    def validate(self, settings: OrionSettings) -> bool:
        """
        Rigorously validate all configuration parameters, ranges, percentages,
        quantities, API options, and logging paths. Raises SettingsValidationError
        if any constraint is violated.
        """
        self._logger.info("Executing rigorous validation of OrionSettings configuration.")

        try:
            # 1. Validate Workspace and Paths
            if not settings.workspace:
                raise SettingsValidationError("Workspace path cannot be empty.")

            # Validate Logging level
            valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
            if settings.logging.level.upper() not in valid_log_levels:
                raise SettingsValidationError(f"Invalid logging level: [{settings.logging.level}]. Must be one of {valid_log_levels}.")

            if settings.logging.rotation_mb <= 0:
                raise SettingsValidationError("Logging rotation_mb must be greater than zero.")
            if settings.logging.backup_files < 0:
                raise SettingsValidationError("Logging backup_files cannot be negative.")

            # 2. Validate Binance Settings (if live trading is intended or general format check)
            if settings.binance.request_timeout <= 0:
                raise SettingsValidationError("Binance request_timeout must be greater than zero.")
            if settings.binance.recv_window <= 0:
                raise SettingsValidationError("Binance recv_window must be greater than zero.")
            if not settings.binance.base_url.startswith("http"):
                raise SettingsValidationError(f"Invalid Binance base_url format: [{settings.binance.base_url}]")

            if not settings.trading.paper_trading:
                # If paper trading is disabled (Live mode), API keys are mandatory
                if not settings.binance.api_key.strip() or not settings.binance.api_secret.strip():
                    raise SettingsValidationError("Binance API key and secret are required when paper_trading is disabled (Live trading mode).")

            # 3. Validate Trading Quantities & Positions
            if settings.trading.default_quantity <= 0.0:
                raise SettingsValidationError("Trading default_quantity must be greater than zero.")
            if settings.trading.max_open_positions <= 0:
                raise SettingsValidationError("Trading max_open_positions must be greater than zero.")
            if not settings.trading.allow_short and not settings.trading.allow_long:
                raise SettingsValidationError("Both allow_long and allow_short cannot be False simultaneously.")

            # 4. Validate Risk Percentages & Thresholds
            if not (0.0 < settings.risk.max_daily_loss <= 1.0):
                raise SettingsValidationError(f"Invalid max_daily_loss percentage: [{settings.risk.max_daily_loss}]. Must be between 0.0 and 1.0.")
            if not (0.0 < settings.risk.max_position_size <= 1.0):
                raise SettingsValidationError(f"Invalid max_position_size percentage: [{settings.risk.max_position_size}]. Must be between 0.0 and 1.0.")
            if not (0.0 < settings.risk.risk_per_trade <= 1.0):
                raise SettingsValidationError(f"Invalid risk_per_trade percentage: [{settings.risk.risk_per_trade}]. Must be between 0.0 and 1.0.")
            if not (0.0 < settings.risk.stop_loss_percent <= 1.0):
                raise SettingsValidationError(f"Invalid stop_loss_percent percentage: [{settings.risk.stop_loss_percent}]. Must be between 0.0 and 1.0.")
            if not (0.0 < settings.risk.take_profit_percent <= 1.0):
                raise SettingsValidationError(f"Invalid take_profit_percent percentage: [{settings.risk.take_profit_percent}]. Must be between 0.0 and 1.0.")

            # 5. Validate Scanner Settings
            if not settings.scanner.default_timeframes:
                raise SettingsValidationError("Scanner default_timeframes cannot be empty.")
            if not settings.scanner.default_symbols:
                raise SettingsValidationError("Scanner default_symbols cannot be empty.")
            if settings.scanner.max_parallel_symbols <= 0:
                raise SettingsValidationError("Scanner max_parallel_symbols must be greater than zero.")
            if settings.scanner.refresh_interval_seconds <= 0:
                raise SettingsValidationError("Scanner refresh_interval_seconds must be greater than zero.")

            # 6. Validate Cache Settings
            if settings.cache.max_size_mb <= 0:
                raise SettingsValidationError("Cache max_size_mb must be greater than zero.")
            if settings.cache.expiration_minutes <= 0:
                raise SettingsValidationError("Cache expiration_minutes must be greater than zero.")

            self._logger.info("OrionSettings validation completed successfully. All parameters are valid.")
            return True

        except SettingsValidationError as sve:
            self._logger.error(f"Settings validation failed: {sve}")
            raise
        except Exception as e:
            self._logger.error(f"Unexpected error during settings validation: {e}")
            raise SettingsValidationError(f"Settings validation unexpected error: {e}") from e


# =============================================================================
# End Of File
# =============================================================================
'''
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : config.settings
Version      : 1.0.0
Status       : ORION Production Candidate V1
===============================================================================

Centralized Configuration and Settings Management Module for the ORION project.
Responsible for providing strongly-typed, immutable frozen dataclasses for all system
subsystems (Binance, Cache, Logging, Trading, Risk, Scanner, and OrionSettings)
alongside a robust SettingsLoader utility handling environment variables, default profiles,
JSON file serialization, and comprehensive structural and logical validation.
Strictly enforcing clean architecture and zero business logic or exchange coupling.
===============================================================================
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class SettingsError(Exception):
    """Base exception class for all settings and configuration related failures."""
    pass


class SettingsValidationError(SettingsError):
    """Raised when configuration parameters fail validation rules or integrity checks."""
    pass


# =============================================================================
# Configuration Subsystem Dataclasses (Frozen & Fully Typed)
# =============================================================================

@dataclass(frozen=True, slots=True)
class BinanceSettings:
    """Immutable settings governing Binance exchange connection parameters."""
    api_key: str = ""
    api_secret: str = ""
    testnet: bool = True
    base_url: str = "https://testnet.binance.vision"
    request_timeout: float = 10.0
    recv_window: int = 5000


@dataclass(frozen=True, slots=True)
class CacheSettings:
    """Immutable settings governing market and pipeline data caching behavior."""
    enabled: bool = True
    directory: Path = field(default_factory=lambda: Path("./orion_workspace/cache"))
    max_size_mb: int = 512
    expiration_minutes: int = 60


@dataclass(frozen=True, slots=True)
class LoggingSettings:
    """Immutable settings governing system logging, output sinks, and rotation files."""
    level: str = "INFO"
    directory: Path = field(default_factory=lambda: Path("./orion_workspace/logs"))
    filename: str = "orion_production.log"
    rotation_mb: int = 10
    backup_files: int = 5
    console_output: bool = True


@dataclass(frozen=True, slots=True)
class TradingSettings:
    """Immutable settings governing general order execution and trading modes."""
    paper_trading: bool = True
    default_quantity: float = 1.0
    max_open_positions: int = 5
    allow_short: bool = True
    allow_long: bool = True


@dataclass(frozen=True, slots=True)
class RiskSettings:
    """Immutable settings governing risk management thresholds and position constraints."""
    max_daily_loss: float = 0.05
    max_position_size: float = 0.20
    risk_per_trade: float = 0.01
    stop_loss_percent: float = 0.02
    take_profit_percent: float = 0.04


@dataclass(frozen=True, slots=True)
class ScannerSettings:
    """Immutable settings governing market symbol scanning frequencies and scopes."""
    default_timeframes: tuple[str, ...] = ("1h", "4h", "1d")
    max_parallel_symbols: int = 10
    default_symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT")
    refresh_interval_seconds: int = 300


@dataclass(frozen=True, slots=True)
class OrionSettings:
    """Master immutable aggregate configuration structure enclosing all system subsystems."""
    workspace: Path = field(default_factory=lambda: Path("./orion_workspace"))
    binance: BinanceSettings = field(default_factory=BinanceSettings)
    cache: CacheSettings = field(default_factory=CacheSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    trading: TradingSettings = field(default_factory=TradingSettings)
    risk: RiskSettings = field(default_factory=RiskSettings)
    scanner: ScannerSettings = field(default_factory=ScannerSettings)


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting settings component context attributes into log entries."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# Settings Loader & Factory
# =============================================================================

class SettingsLoader:
    """
    Centralized factory and manager responsible for loading, merging, persisting,
    and rigorously validating OrionSettings from default profiles, environment variables,
    or external JSON configuration files.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger_instance = logger if logger is not None else base_logger
        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "component": "SettingsLoader",
                "operation": "init",
            },
        )
        self._logger.info("SettingsLoader initialized successfully.")

    def load_defaults(self) -> OrionSettings:
        """Create and return a default production-ready OrionSettings instance."""
        self._logger.info("Loading default OrionSettings configuration profile.")
        return OrionSettings()

    def load_from_environment(self, base_settings: Optional[OrionSettings] = None) -> OrionSettings:
        """
        Load configuration overrides from environment variables and merge them
        into the provided base settings or a fresh default settings profile.
        """
        self._logger.info("Loading configuration overrides from environment variables.")
        current = base_settings if base_settings is not None else self.load_defaults()

        try:
            # Workspace & General Env
            workspace = Path(os.getenv("ORION_WORKSPACE", current.workspace))

            # Binance Env
            binance_settings = BinanceSettings(
                api_key=os.getenv("ORION_BINANCE_API_KEY", current.binance.api_key),
                api_secret=os.getenv("ORION_BINANCE_API_SECRET", current.binance.api_secret),
                testnet=os.getenv("ORION_BINANCE_TESTNET", str(current.binance.testnet)).lower() in ("true", "1", "yes"),
                base_url=os.getenv("ORION_BINANCE_BASE_URL", current.binance.base_url),
                request_timeout=float(os.getenv("ORION_BINANCE_REQUEST_TIMEOUT", current.binance.request_timeout)),
                recv_window=int(os.getenv("ORION_BINANCE_RECV_WINDOW", current.binance.recv_window)),
            )

            # Cache Env
            cache_settings = CacheSettings(
                enabled=os.getenv("ORION_CACHE_ENABLED", str(current.cache.enabled)).lower() in ("true", "1", "yes"),
                directory=Path(os.getenv("ORION_CACHE_DIRECTORY", current.cache.directory)),
                max_size_mb=int(os.getenv("ORION_CACHE_MAX_SIZE_MB", current.cache.max_size_mb)),
                expiration_minutes=int(os.getenv("ORION_CACHE_EXPIRATION_MINUTES", current.cache.expiration_minutes)),
            )

            # Logging Env
            logging_settings = LoggingSettings(
                level=os.getenv("ORION_LOGGING_LEVEL", current.logging.level),
                directory=Path(os.getenv("ORION_LOGGING_DIRECTORY", current.logging.directory)),
                filename=os.getenv("ORION_LOGGING_FILENAME", current.logging.filename),
                rotation_mb=int(os.getenv("ORION_LOGGING_ROTATION_MB", current.logging.rotation_mb)),
                backup_files=int(os.getenv("ORION_LOGGING_BACKUP_FILES", current.logging.backup_files)),
                console_output=os.getenv("ORION_LOGGING_CONSOLE_OUTPUT", str(current.logging.console_output)).lower() in ("true", "1", "yes"),
            )

            # Trading Env
            trading_settings = TradingSettings(
                paper_trading=os.getenv("ORION_TRADING_PAPER_TRADING", str(current.trading.paper_trading)).lower() in ("true", "1", "yes"),
                default_quantity=float(os.getenv("ORION_TRADING_DEFAULT_QUANTITY", current.trading.default_quantity)),
                max_open_positions=int(os.getenv("ORION_TRADING_MAX_OPEN_POSITIONS", current.trading.max_open_positions)),
                allow_short=os.getenv("ORION_TRADING_ALLOW_SHORT", str(current.trading.allow_short)).lower() in ("true", "1", "yes"),
                allow_long=os.getenv("ORION_TRADING_ALLOW_LONG", str(current.trading.allow_long)).lower() in ("true", "1", "yes"),
            )

            # Risk Env
            risk_settings = RiskSettings(
                max_daily_loss=float(os.getenv("ORION_RISK_MAX_DAILY_LOSS", current.risk.max_daily_loss)),
                max_position_size=float(os.getenv("ORION_RISK_MAX_POSITION_SIZE", current.risk.max_position_size)),
                risk_per_trade=float(os.getenv("ORION_RISK_RISK_PER_TRADE", current.risk.risk_per_trade)),
                stop_loss_percent=float(os.getenv("ORION_RISK_STOP_LOSS_PERCENT", current.risk.stop_loss_percent)),
                take_profit_percent=float(os.getenv("ORION_RISK_TAKE_PROFIT_PERCENT", current.risk.take_profit_percent)),
            )

            # Scanner Env
            env_timeframes = os.getenv("ORION_SCANNER_DEFAULT_TIMEFRAMES")
            timeframes = tuple(env_timeframes.split(",")) if env_timeframes else current.scanner.default_timeframes

            env_symbols = os.getenv("ORION_SCANNER_DEFAULT_SYMBOLS")
            symbols = tuple(env_symbols.split(",")) if env_symbols else current.scanner.default_symbols

            scanner_settings = ScannerSettings(
                default_timeframes=timeframes,
                max_parallel_symbols=int(os.getenv("ORION_SCANNER_MAX_PARALLEL_SYMBOLS", current.scanner.max_parallel_symbols)),
                default_symbols=symbols,
                refresh_interval_seconds=int(os.getenv("ORION_SCANNER_REFRESH_INTERVAL_SECONDS", current.scanner.refresh_interval_seconds)),
            )

            loaded_settings = OrionSettings(
                workspace=workspace,
                binance=binance_settings,
                cache=cache_settings,
                logging=logging_settings,
                trading=trading_settings,
                risk=risk_settings,
                scanner=scanner_settings,
            )

            self._logger.info("Environment configuration loaded and merged successfully.")
            return loaded_settings

        except Exception as e:
            raise SettingsError(f"Failed to load settings from environment variables: {e}") from e

    def load_from_file(self, file_path: Path | str) -> OrionSettings:
        """Load and parse OrionSettings from a JSON configuration file on disk."""
        path = Path(file_path)
        self._logger.info(f"Loading OrionSettings configuration from file: {path}")

        if not path.exists():
            raise SettingsError(f"Configuration file does not exist at path: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            workspace = Path(data.get("workspace", "./orion_workspace"))

            b_data = data.get("binance", {})
            binance_settings = BinanceSettings(
                api_key=b_data.get("api_key", ""),
                api_secret=b_data.get("api_secret", ""),
                testnet=b_data.get("testnet", True),
                base_url=b_data.get("base_url", "https://testnet.binance.vision"),
                request_timeout=float(b_data.get("request_timeout", 10.0)),
                recv_window=int(b_data.get("recv_window", 5000)),
            )

            c_data = data.get("cache", {})
            cache_settings = CacheSettings(
                enabled=c_data.get("enabled", True),
                directory=Path(c_data.get("directory", "./orion_workspace/cache")),
                max_size_mb=int(c_data.get("max_size_mb", 512)),
                expiration_minutes=int(c_data.get("expiration_minutes", 60)),
            )

            l_data = data.get("logging", {})
            logging_settings = LoggingSettings(
                level=l_data.get("level", "INFO"),
                directory=Path(l_data.get("directory", "./orion_workspace/logs")),
                filename=l_data.get("filename", "orion_production.log"),
                rotation_mb=int(l_data.get("rotation_mb", 10)),
                backup_files=int(l_data.get("backup_files", 5)),
                console_output=l_data.get("console_output", True),
            )

            t_data = data.get("trading", {})
            trading_settings = TradingSettings(
                paper_trading=t_data.get("paper_trading", True),
                default_quantity=float(t_data.get("default_quantity", 1.0)),
                max_open_positions=int(t_data.get("max_open_positions", 5)),
                allow_short=t_data.get("allow_short", True),
                allow_long=t_data.get("allow_long", True),
            )

            r_data = data.get("risk", {})
            risk_settings = RiskSettings(
                max_daily_loss=float(r_data.get("max_daily_loss", 0.05)),
                max_position_size=float(r_data.get("max_position_size", 0.20)),
                risk_per_trade=float(r_data.get("risk_per_trade", 0.01)),
                stop_loss_percent=float(r_data.get("stop_loss_percent", 0.02)),
                take_profit_percent=float(r_data.get("take_profit_percent", 0.04)),
            )

            s_data = data.get("scanner", {})
            scanner_settings = ScannerSettings(
                default_timeframes=tuple(s_data.get("default_timeframes", ("1h", "4h", "1d"))),
                max_parallel_symbols=int(s_data.get("max_parallel_symbols", 10)),
                default_symbols=tuple(s_data.get("default_symbols", ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"))),
                refresh_interval_seconds=int(s_data.get("refresh_interval_seconds", 300)),
            )

            settings = OrionSettings(
                workspace=workspace,
                binance=binance_settings,
                cache=cache_settings,
                logging=logging_settings,
                trading=trading_settings,
                risk=risk_settings,
                scanner=scanner_settings,
            )

            self._logger.info(f"Configuration file loaded successfully from {path}")
            return settings

        except Exception as e:
            raise SettingsError(f"Failed to load configuration from file {path}: {e}") from e

    def save(self, settings: OrionSettings, file_path: Path | str) -> None:
        """Serialize and save OrionSettings to a JSON configuration file on disk."""
        path = Path(file_path)
        self._logger.info(f"Saving OrionSettings configuration to file: {path}")

        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "workspace": str(settings.workspace),
                "binance": {
                    "api_key": settings.binance.api_key,
                    "api_secret": settings.binance.api_secret,
                    "testnet": settings.binance.testnet,
                    "base_url": settings.binance.base_url,
                    "request_timeout": settings.binance.request_timeout,
                    "recv_window": settings.binance.recv_window,
                },
                "cache": {
                    "enabled": settings.cache.enabled,
                    "directory": str(settings.cache.directory),
                    "max_size_mb": settings.cache.max_size_mb,
                    "expiration_minutes": settings.cache.expiration_minutes,
                },
                "logging": {
                    "level": settings.logging.level,
                    "directory": str(settings.logging.directory),
                    "filename": settings.logging.filename,
                    "rotation_mb": settings.logging.rotation_mb,
                    "backup_files": settings.logging.backup_files,
                    "console_output": settings.logging.console_output,
                },
                "trading": {
                    "paper_trading": settings.trading.paper_trading,
                    "default_quantity": settings.trading.default_quantity,
                    "max_open_positions": settings.trading.max_open_positions,
                    "allow_short": settings.trading.allow_short,
                    "allow_long": settings.trading.allow_long,
                },
                "risk": {
                    "max_daily_loss": settings.risk.max_daily_loss,
                    "max_position_size": settings.risk.max_position_size,
                    "risk_per_trade": settings.risk.risk_per_trade,
                    "stop_loss_percent": settings.risk.stop_loss_percent,
                    "take_profit_percent": settings.risk.take_profit_percent,
                },
                "scanner": {
                    "default_timeframes": list(settings.scanner.default_timeframes),
                    "max_parallel_symbols": settings.scanner.max_parallel_symbols,
                    "default_symbols": list(settings.scanner.default_symbols),
                    "refresh_interval_seconds": settings.scanner.refresh_interval_seconds,
                },
            }

            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

            self._logger.info(f"Configuration successfully saved to {path}")

        except Exception as e:
            raise SettingsError(f"Failed to save configuration to file {path}: {e}") from e

    def validate(self, settings: OrionSettings) -> bool:
        """
        Rigorously validate all configuration parameters, ranges, percentages,
        quantities, API options, and logging paths. Raises SettingsValidationError
        if any constraint is violated.
        """
        self._logger.info("Executing rigorous validation of OrionSettings configuration.")

        try:
            # 1. Validate Workspace and Paths
            if not settings.workspace:
                raise SettingsValidationError("Workspace path cannot be empty.")

            # Validate Logging level
            valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
            if settings.logging.level.upper() not in valid_log_levels:
                raise SettingsValidationError(f"Invalid logging level: [{settings.logging.level}]. Must be one of {valid_log_levels}.")

            if settings.logging.rotation_mb <= 0:
                raise SettingsValidationError("Logging rotation_mb must be greater than zero.")
            if settings.logging.backup_files < 0:
                raise SettingsValidationError("Logging backup_files cannot be negative.")

            # 2. Validate Binance Settings (if live trading is intended or general format check)
            if settings.binance.request_timeout <= 0:
                raise SettingsValidationError("Binance request_timeout must be greater than zero.")
            if settings.binance.recv_window <= 0:
                raise SettingsValidationError("Binance recv_window must be greater than zero.")
            if not settings.binance.base_url.startswith("http"):
                raise SettingsValidationError(f"Invalid Binance base_url format: [{settings.binance.base_url}]")

            if not settings.trading.paper_trading:
                # If paper trading is disabled (Live mode), API keys are mandatory
                if not settings.binance.api_key.strip() or not settings.binance.api_secret.strip():
                    raise SettingsValidationError("Binance API key and secret are required when paper_trading is disabled (Live trading mode).")

            # 3. Validate Trading Quantities & Positions
            if settings.trading.default_quantity <= 0.0:
                raise SettingsValidationError("Trading default_quantity must be greater than zero.")
            if settings.trading.max_open_positions <= 0:
                raise SettingsValidationError("Trading max_open_positions must be greater than zero.")
            if not settings.trading.allow_short and not settings.trading.allow_long:
                raise SettingsValidationError("Both allow_long and allow_short cannot be False simultaneously.")

            # 4. Validate Risk Percentages & Thresholds
            if not (0.0 < settings.risk.max_daily_loss <= 1.0):
                raise SettingsValidationError(f"Invalid max_daily_loss percentage: [{settings.risk.max_daily_loss}]. Must be between 0.0 and 1.0.")
            if not (0.0 < settings.risk.max_position_size <= 1.0):
                raise SettingsValidationError(f"Invalid max_position_size percentage: [{settings.risk.max_position_size}]. Must be between 0.0 and 1.0.")
            if not (0.0 < settings.risk.risk_per_trade <= 1.0):
                raise SettingsValidationError(f"Invalid risk_per_trade percentage: [{settings.risk.risk_per_trade}]. Must be between 0.0 and 1.0.")
            if not (0.0 < settings.risk.stop_loss_percent <= 1.0):
                raise SettingsValidationError(f"Invalid stop_loss_percent percentage: [{settings.risk.stop_loss_percent}]. Must be between 0.0 and 1.0.")
            if not (0.0 < settings.risk.take_profit_percent <= 1.0):
                raise SettingsValidationError(f"Invalid take_profit_percent percentage: [{settings.risk.take_profit_percent}]. Must be between 0.0 and 1.0.")

            # 5. Validate Scanner Settings
            if not settings.scanner.default_timeframes:
                raise SettingsValidationError("Scanner default_timeframes cannot be empty.")
            if not settings.scanner.default_symbols:
                raise SettingsValidationError("Scanner default_symbols cannot be empty.")
            if settings.scanner.max_parallel_symbols <= 0:
                raise SettingsValidationError("Scanner max_parallel_symbols must be greater than zero.")
            if settings.scanner.refresh_interval_seconds <= 0:
                raise SettingsValidationError("Scanner refresh_interval_seconds must be greater than zero.")

            # 6. Validate Cache Settings
            if settings.cache.max_size_mb <= 0:
                raise SettingsValidationError("Cache max_size_mb must be greater than zero.")
            if settings.cache.expiration_minutes <= 0:
                raise SettingsValidationError("Cache expiration_minutes must be greater than zero.")

            self._logger.info("OrionSettings validation completed successfully. All parameters are valid.")
            return True

        except SettingsValidationError as sve:
            self._logger.error(f"Settings validation failed: {sve}")
            raise
        except Exception as e:
            self._logger.error(f"Unexpected error during settings validation: {e}")
            raise SettingsValidationError(f"Settings validation unexpected error: {e}") from e


# =============================================================================
# End Of File
# =============================================================================
'''
