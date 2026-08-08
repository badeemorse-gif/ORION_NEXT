"""
===============================================================================
Badee Binance Scanner
Architecture : ORION - Approved Architecture
Module       : storage.market_storage
Version      : 1.0.0
Status       : ORION Production V1.0
===============================================================================

Market Dataset Storage Engine using Apache Parquet and JSON metadata.
===============================================================================
"""

from __future__ import annotations

import hashlib
import json
import logging
import platform
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, TypedDict

import numpy as np
import pandas as pd

from enums import DataHealth, Timeframe
from models.market import MarketDataset, MarketMetadata, TimeframeData

base_logger = logging.getLogger(__name__)


# =============================================================================
# Storage Configuration & Version Constants
# =============================================================================

@dataclass(frozen=True, slots=True)
class StorageConfig:
    schema_version: str = "1.0.0"
    storage_version: str = "1.0.0"
    parquet_engine: str = "pyarrow"
    compression_algorithm: str = "zstd"


STORAGE_CONFIG = StorageConfig()


# =============================================================================
# Metadata TypedDict Definitions
# =============================================================================

class TimeframeMetadataDict(TypedDict):
    data_health: str
    candles_count: int
    first_timestamp: Optional[str]
    last_timestamp: Optional[str]
    indicators_ready: bool
    profile_ready: bool
    dataframe_hash: str


class MetadataDict(TypedDict):
    schema_version: str
    storage_version: str
    symbol: str
    exchange: str
    source: str
    cache_version: str
    downloaded_at: Optional[str]
    last_updated_at: str
    created_at: str
    updated_at: str
    is_valid: bool
    validation_message: Optional[str]
    parquet_engine: str
    compression: str
    checksum: str
    python_version: str
    pandas_version: str
    numpy_version: str
    timeframes: dict[str, TimeframeMetadataDict]


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """
    Custom LoggerAdapter to inject contextual information into every log record.
    """

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        if context_str:
            formatted_msg = f"[{context_str}] {msg}"
        else:
            formatted_msg = msg
        return formatted_msg, kwargs


def get_logger(
    symbol: Optional[str] = None,
    timeframe: Optional[Timeframe | str] = None,
    operation: Optional[str] = None,
    dataset: Optional[str] = None,
    method: Optional[str] = None,
) -> LoggerAdapter:
    """
    Factory function to create a LoggerAdapter with enhanced preset context.
    """
    tf_str = (
        timeframe.value
        if hasattr(timeframe, "value")
        else str(timeframe)
        if timeframe
        else None
    )
    return LoggerAdapter(
        base_logger,
        {
            "symbol": symbol,
            "timeframe": tf_str,
            "operation": operation,
            "dataset": dataset,
            "method": method,
        },
    )


# =============================================================================
# Custom Exceptions
# =============================================================================

class StorageError(Exception):
    """Base exception for all storage-related errors."""
    pass


class DatasetNotFound(StorageError):
    """Raised when a dataset or symbol path does not exist."""
    pass


class InvalidDataset(StorageError):
    """Raised when dataset validation fails."""
    pass


class MetadataError(StorageError):
    """Raised when reading or writing metadata fails."""
    pass


# =============================================================================
# Market Storage Engine
# =============================================================================

@dataclass(slots=True)
class MarketStorage:
    """
    Handles local persistence of MarketDataset objects using Apache Parquet
    for timeframe DataFrames and JSON for metadata with atomic operations.
    """

    root_directory: Path
    cache_dir: Path = field(init=False)
    parquet_dir: Path = field(init=False)
    temp_dir: Path = field(init=False)
    logs_dir: Path = field(init=False)
    backups_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "root_directory", Path(self.root_directory))
        object.__setattr__(self, "cache_dir", self.root_directory / "cache")
        object.__setattr__(self, "parquet_dir", self.cache_dir / "parquet")
        object.__setattr__(self, "temp_dir", self.cache_dir / "temp")
        object.__setattr__(self, "logs_dir", self.cache_dir / "logs")
        object.__setattr__(self, "backups_dir", self.cache_dir / "backups")
        self._initialize_directories()

    def _initialize_directories(self) -> None:
        """
        Automatically create required cache subdirectories if they are missing.
        """
        for directory in [
            self.cache_dir,
            self.parquet_dir,
            self.temp_dir,
            self.logs_dir,
            self.backups_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    def _now(self) -> str:
        """
        Helper to return current UTC timestamp in ISO format.
        """
        return datetime.now(timezone.utc).isoformat()

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def save_dataset(self, dataset: MarketDataset) -> None:
        """
        Validate and save a MarketDataset to local storage atomically.
        """
        logger = get_logger(
            symbol=dataset.symbol,
            operation="save_dataset",
            dataset=dataset.symbol,
            method="save_dataset",
        )
        logger.info("Saving dataset.")
        self._validate_dataset(dataset)

        symbol_path = self._build_symbol_path(dataset.symbol)
        symbol_path.mkdir(parents=True, exist_ok=True)

        temp_symbol_dir = self.temp_dir / dataset.symbol
        if temp_symbol_dir.exists():
            shutil.rmtree(temp_symbol_dir, ignore_errors=True)
        temp_symbol_dir.mkdir(parents=True, exist_ok=True)

        try:
            serialized_data: dict[str, tuple[bytes, str]] = {}
            for tf, tf_data in dataset.timeframes.items():
                tf_str = tf.value if hasattr(tf, "value") else str(tf)
                tf_path = temp_symbol_dir / f"{tf_str}.parquet"
                df_bytes = self._write_parquet(tf_data.dataframe, tf_path, timeframe=tf)
                df_hash = hashlib.sha256(df_bytes).hexdigest()
                serialized_data[tf_str] = (df_bytes, df_hash)

            metadata_path = symbol_path / "metadata.json"
            existing_created_at: Optional[str] = None
            if metadata_path.exists():
                try:
                    old_meta = self._read_metadata(metadata_path)
                    existing_created_at = old_meta.get("created_at")
                except Exception:
                    pass

            temp_metadata_path = temp_symbol_dir / "metadata.json"
            self._write_metadata(
                dataset,
                temp_metadata_path,
                serialized_data=serialized_data,
                existing_created_at=existing_created_at,
            )

            if symbol_path.exists():
                shutil.rmtree(symbol_path, ignore_errors=True)
            shutil.move(str(temp_symbol_dir), str(symbol_path))

            logger.info("Dataset successfully saved.")
        except Exception as e:
            logger.error(f"Failed to save dataset atomically: {e}")
            if temp_symbol_dir.exists():
                shutil.rmtree(temp_symbol_dir, ignore_errors=True)
            raise StorageError(f"Atomic save failed: {e}") from e

    def load_dataset(self, symbol: str) -> MarketDataset:
        """
        Load a MarketDataset from local storage by symbol with checksum verification.
        """
        logger = get_logger(
            symbol=symbol,
            operation="load_dataset",
            dataset=symbol,
            method="load_dataset",
        )
        logger.info("Loading dataset.")
        if not self.dataset_exists(symbol):
            raise DatasetNotFound(f"Dataset for symbol {symbol} not found.")

        symbol_path = self._build_symbol_path(symbol)
        metadata_path = symbol_path / "metadata.json"
        metadata_dict = self._read_metadata(metadata_path)

        market_metadata = MarketMetadata(
            symbol=metadata_dict.get("symbol", symbol),
            exchange=metadata_dict.get("exchange", "BINANCE"),
            source=metadata_dict.get("source", "API"),
            cache_version=metadata_dict.get("cache_version", "1.0.0"),
            downloaded_at=datetime.fromisoformat(metadata_dict["downloaded_at"]) if metadata_dict.get("downloaded_at") else datetime.now(timezone.utc),
            last_updated_at=datetime.fromisoformat(metadata_dict["last_updated_at"]) if metadata_dict.get("last_updated_at") else datetime.now(timezone.utc),
            is_valid=metadata_dict.get("is_valid", True),
            validation_message=metadata_dict.get("validation_message"),
        )

        dataset = MarketDataset(metadata=market_metadata)

        timeframes_info = metadata_dict.get("timeframes", {})
        total_checksum_payload = ""

        for tf_str, tf_info in timeframes_info.items():
            try:
                tf_enum = Timeframe(tf_str)
            except ValueError:
                logger.warning(f"Unknown timeframe string '{tf_str}' found in metadata. Skipping.")
                continue

            tf_path = self._build_timeframe_path(symbol, tf_enum)
            if tf_path.exists():
                df = self._read_parquet(tf_path, timeframe=tf_enum)

                df_bytes = df.to_parquet(
                    engine=STORAGE_CONFIG.parquet_engine,
                    compression=STORAGE_CONFIG.compression_algorithm,
                )
                computed_df_hash = hashlib.sha256(df_bytes).hexdigest()
                stored_df_hash = tf_info.get("dataframe_hash")

                if stored_df_hash and computed_df_hash != stored_df_hash:
                    raise InvalidDataset(f"Checksum mismatch for timeframe {tf_enum} in symbol {symbol}. Dataset may be corrupted.")

                total_checksum_payload += computed_df_hash

                first_ts = datetime.fromisoformat(tf_info["first_timestamp"]) if tf_info.get("first_timestamp") else None
                last_ts = datetime.fromisoformat(tf_info["last_timestamp"]) if tf_info.get("last_timestamp") else None

                tf_data = TimeframeData(
                    timeframe=tf_enum,
                    dataframe=df,
                    data_health=DataHealth(tf_info.get("data_health", "VALID")),
                    candles_count=tf_info.get("candles_count", len(df)),
                    first_timestamp=first_ts,
                    last_timestamp=last_ts,
                    indicators_ready=tf_info.get("indicators_ready", False),
                    profile_ready=tf_info.get("profile_ready", False),
                )
                dataset.add_timeframe(tf_data)

        expected_global_checksum = hashlib.sha256(total_checksum_payload.encode("utf-8")).hexdigest()
        stored_global_checksum = metadata_dict.get("checksum")
        if stored_global_checksum and expected_global_checksum != stored_global_checksum:
            raise InvalidDataset(f"Global checksum mismatch for symbol {symbol}. Dataset integrity check failed.")

        logger.info("Dataset successfully loaded and verified.")
        return dataset

    def dataset_exists(self, symbol: str) -> bool:
        """
        Check if a dataset exists for the given symbol.
        """
        symbol_path = self._build_symbol_path(symbol)
        metadata_path = symbol_path / "metadata.json"
        return symbol_path.exists() and metadata_path.exists()

    def delete_dataset(self, symbol: str) -> None:
        """
        Delete entire dataset and folder for a symbol safely using shutil.rmtree.
        """
        logger = get_logger(
            symbol=symbol,
            operation="delete_dataset",
            dataset=symbol,
            method="delete_dataset",
        )
        logger.info("Deleting dataset.")
        symbol_path = self._build_symbol_path(symbol)
        if not symbol_path.exists() or not symbol_path.is_dir():
            raise DatasetNotFound(f"Dataset for symbol {symbol} does not exist.")

        shutil.rmtree(symbol_path, ignore_errors=True)
        logger.info("Dataset deleted successfully.")

    def delete_symbol(self, symbol: str) -> None:
        """
        Alias for delete_dataset.
        """
        self.delete_dataset(symbol)

    def delete_timeframe(self, symbol: str, timeframe: Timeframe) -> None:
        """
        Delete a specific timeframe parquet file and update metadata.
        If no timeframes remain, delete the entire symbol directory.
        """
        logger = get_logger(
            symbol=symbol,
            timeframe=timeframe,
            operation="delete_timeframe",
            dataset=symbol,
            method="delete_timeframe",
        )
        logger.info("Deleting timeframe.")
        if not self.dataset_exists(symbol):
            raise DatasetNotFound(f"Dataset for symbol {symbol} does not exist.")

        tf_path = self._build_timeframe_path(symbol, timeframe)
        if tf_path.exists():
            tf_path.unlink()

        symbol_path = self._build_symbol_path(symbol)
        metadata_path = symbol_path / "metadata.json"
        metadata_dict = self._read_metadata(metadata_path)

        if "timeframes" in metadata_dict and str(timeframe) in metadata_dict["timeframes"]:
            del metadata_dict["timeframes"][str(timeframe)]

        remaining_timeframes = metadata_dict.get("timeframes", {})
        if not remaining_timeframes:
            logger.warning("No timeframes remaining after deletion. Removing entire dataset directory.")
            self.delete_dataset(symbol)
        else:
            metadata_dict["updated_at"] = self._now()
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata_dict, f, indent=4, default=str)
            logger.info("Timeframe deleted successfully and metadata updated.")

    def list_symbols(self) -> list[str]:
        """
        List all available symbols in the cache storage, sorted alphabetically.
        """
        if not self.parquet_dir.exists():
            return []
        symbols = [item.name for item in self.parquet_dir.iterdir() if item.is_dir()]
        return sorted(symbols)

    def list_timeframes(self, symbol: str) -> list[Timeframe]:
        """
        List all available timeframes for a given symbol safely supporting unknown future timeframes.
        """
        if not self.dataset_exists(symbol):
            raise DatasetNotFound(f"Dataset for symbol {symbol} does not exist.")

        symbol_path = self._build_symbol_path(symbol)
        timeframes = []
        for file_path in symbol_path.glob("*.parquet"):
            tf_name = file_path.stem
            try:
                timeframes.append(Timeframe(tf_name))
            except ValueError:
                logger_local = get_logger(symbol=symbol, operation="list_timeframes", method="list_timeframes")
                logger_local.warning(f"Encountered unknown future timeframe identifier '{tf_name}' in storage. Skipping.")
        return timeframes

    def clear_cache(self) -> None:
        """
        Clear all cached parquet files and metadata by removing symbol directories recursively
        and recreating the parquet directory automatically without touching the cache root.
        """
        logger = get_logger(operation="clear_cache", method="clear_cache")
        logger.info("Clearing cache storage.")
        removed_count = 0
        if self.parquet_dir.exists():
            for symbol_dir in self.parquet_dir.iterdir():
                if symbol_dir.is_dir():
                    shutil.rmtree(symbol_dir, ignore_errors=True)
                    removed_count += 1
            self.parquet_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Cache cleared successfully. Removed {removed_count} dataset directories.")

    def backup_dataset(self, symbol: str) -> Path:
        """
        Create an unlimited versioned backup of the symbol's dataset files under YYYYMMDD_HHMMSS subfolder.
        """
        logger = get_logger(
            symbol=symbol,
            operation="backup_dataset",
            dataset=symbol,
            method="backup_dataset",
        )
        logger.info("Backing up dataset.")
        if not self.dataset_exists(symbol):
            raise DatasetNotFound(f"Dataset for symbol {symbol} does not exist.")

        symbol_path = self._build_symbol_path(symbol)
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_symbol_dir = self.backups_dir / symbol / timestamp_str
        backup_symbol_dir.mkdir(parents=True, exist_ok=True)

        shutil.copytree(symbol_path, backup_symbol_dir, dirs_exist_ok=True)
        logger.info(f"Backup created at {backup_symbol_dir}")
        return backup_symbol_dir

    def restore_backup(self, symbol: str, timestamp: Optional[str] = None) -> None:
        """
        Restore a symbol's dataset from its backup. If timestamp is not specified, restores the latest backup automatically.
        """
        logger = get_logger(
            symbol=symbol,
            operation="restore_backup",
            dataset=symbol,
            method="restore_backup",
        )
        logger.info("Restoring dataset backup.")
        symbol_backup_root = self.backups_dir / symbol
        if not symbol_backup_root.exists() or not symbol_backup_root.is_dir():
            raise DatasetNotFound(f"Backups for symbol {symbol} do not exist.")

        if timestamp:
            backup_target_dir = symbol_backup_root / timestamp
        else:
            subfolders = [d for d in symbol_backup_root.iterdir() if d.is_dir()]
            if not subfolders:
                raise DatasetNotFound(f"No backup subfolders found for symbol {symbol}.")
            backup_target_dir = max(subfolders, key=lambda d: d.name)

        if not backup_target_dir.exists() or not backup_target_dir.is_dir():
            raise DatasetNotFound(f"Specified backup target directory {backup_target_dir} does not exist.")

        symbol_path = self._build_symbol_path(symbol)
        if symbol_path.exists():
            shutil.rmtree(symbol_path, ignore_errors=True)

        shutil.copytree(backup_target_dir, symbol_path)
        logger.info(f"Dataset restored successfully from backup {backup_target_dir.name}.")

    def dataset_info(self, symbol: str) -> dict[str, Any]:
        """
        Return comprehensive information dictionary about a dataset, including extended storage and backup fields.
        """
        if not self.dataset_exists(symbol):
            raise DatasetNotFound(f"Dataset for symbol {symbol} does not exist.")

        symbol_path = self._build_symbol_path(symbol)
        metadata_path = symbol_path / "metadata.json"
        metadata_dict = self._read_metadata(metadata_path)
        timeframes = self.list_timeframes(symbol)

        total_size = sum(f.stat().st_size for f in symbol_path.glob("**/*") if f.is_file())
        file_count = sum(1 for f in symbol_path.glob("**/*") if f.is_file())

        symbol_backup_root = self.backups_dir / symbol
        backup_count = 0
        last_backup = None
        if symbol_backup_root.exists() and symbol_backup_root.is_dir():
            backups = sorted([d.name for d in symbol_backup_root.iterdir() if d.is_dir()])
            backup_count = len(backups)
            last_backup = backups[-1] if backups else None

        return {
            "symbol": symbol,
            "metadata": metadata_dict,
            "available_timeframes": [str(tf) for tf in timeframes],
            "storage_path": str(symbol_path),
            "dataset_size_mb": round(total_size / (1024 * 1024), 4),
            "number_of_files": file_count,
            "metadata_version": metadata_dict.get("schema_version", STORAGE_CONFIG.schema_version),
            "storage_version": metadata_dict.get("storage_version", STORAGE_CONFIG.storage_version),
            "backup_count": backup_count,
            "last_backup": last_backup,
        }

    # -------------------------------------------------------------------------
    # Internal Private Methods
    # -------------------------------------------------------------------------

    def _build_symbol_path(self, symbol: str) -> Path:
        """
        Build directory path for a specific symbol.
        """
        return self.parquet_dir / symbol

    def _build_timeframe_path(self, symbol: str, timeframe: Timeframe | str) -> Path:
        """
        Build file path for a specific timeframe parquet file.
        """
        tf_str = timeframe.value if hasattr(timeframe, "value") else str(timeframe)
        return self._build_symbol_path(symbol) / f"{tf_str}.parquet"

    def _validate_dataset(self, dataset: MarketDataset) -> None:
        """
        Perform strict validation rules on the dataset before saving using optimized vectorized checks.
        """
        if not dataset.timeframes:
            raise InvalidDataset("Dataset contains no timeframes to save.")

        for tf, tf_data in dataset.timeframes.items():
            df = tf_data.dataframe

            if df is None or df.empty:
                raise InvalidDataset(f"DataFrame for timeframe {tf} is empty.")

            if not isinstance(df.index, pd.DatetimeIndex):
                raise InvalidDataset(f"DataFrame index for timeframe {tf} must be a DatetimeIndex.")

            if df.index.tz is None:
                raise InvalidDataset(f"DataFrame index for timeframe {tf} must be timezone-aware.")

            if df.index.duplicated().any():
                raise InvalidDataset(f"DataFrame for timeframe {tf} contains duplicate index timestamps.")

            if not df.index.is_monotonic_increasing:
                raise InvalidDataset(f"DataFrame index for timeframe {tf} must be sorted chronologically.")

            if df.columns.duplicated().any():
                raise InvalidDataset(f"DataFrame contains duplicate column names for timeframe {tf}.")

            required_columns = {"open", "high", "low", "close", "volume"}
            missing_cols = required_columns - set(df.columns)
            if missing_cols:
                raise InvalidDataset(f"DataFrame for timeframe {tf} is missing required columns: {missing_cols}")

            expected_dtypes = {
                "open": [np.floating],
                "high": [np.floating],
                "low": [np.floating],
                "close": [np.floating],
                "volume": [np.floating],
            }
            for col, allowed_kinds in expected_dtypes.items():
                if col in df.columns:
                    is_valid_type = any(np.issubdtype(df[col].dtype, kind) for kind in allowed_kinds)
                    if not is_valid_type:
                        raise InvalidDataset(f"Column '{col}' in timeframe {tf} has invalid dtype: {df[col].dtype}")

            sub_df = df[list(required_columns)]
            isna_mask = sub_df.isna()
            if isinstance(isna_mask, pd.DataFrame):
                if isna_mask.to_numpy().any():
                    raise InvalidDataset(f"DataFrame for timeframe {tf} contains NaN values.")
            else:
                if isna_mask.any():
                    raise InvalidDataset(f"DataFrame for timeframe {tf} contains NaN values.")

            isinf_mask = np.isinf(sub_df.to_numpy())
            if isinf_mask.any():
                raise InvalidDataset(f"DataFrame for timeframe {tf} contains INF values.")

            if (df["volume"] < 0).any():
                raise InvalidDataset(f"DataFrame for timeframe {tf} contains negative volume values.")

            invalid_ohlc = (
                (df["high"] < df["low"]) |
                (df["high"] < df["open"]) |
                (df["high"] < df["close"]) |
                (df["low"] > df["open"]) |
                (df["low"] > df["close"])
            )
            if invalid_ohlc.any():
                raise InvalidDataset(f"DataFrame for timeframe {tf} contains invalid OHLC relationships.")

    def _write_parquet(self, df: pd.DataFrame, path: Path, timeframe: Optional[Timeframe | str] = None) -> bytes:
        """
        Write a DataFrame to Parquet using PyArrow backend with zstd compression, index enabled,
        and returning the generated bytes directly to avoid duplicate serialization.
        """
        logger = get_logger(
            timeframe=timeframe,
            operation="_write_parquet",
            method="_write_parquet",
        )
        try:
            df_bytes = df.to_parquet(
                engine=STORAGE_CONFIG.parquet_engine,
                compression=STORAGE_CONFIG.compression_algorithm,
                index=True,
            )
            path.write_bytes(df_bytes)
            return df_bytes
        except Exception as e:
            logger.error(f"Failed to write parquet to {path}: {e}")
            raise StorageError(f"Failed to write parquet file: {e}") from e

    def _read_parquet(self, path: Path, timeframe: Optional[Timeframe | str] = None) -> pd.DataFrame:
        """
        Read a DataFrame from Parquet using PyArrow backend and validate immediately.
        """
        logger = get_logger(
            timeframe=timeframe,
            operation="_read_parquet",
            method="_read_parquet",
        )
        try:
            df = pd.read_parquet(path, engine=STORAGE_CONFIG.parquet_engine)
            if df is None or df.empty or not isinstance(df.index, pd.DatetimeIndex):
                raise InvalidDataset(f"Corrupted or invalid parquet file read from {path}")
            return df
        except Exception as e:
            logger.error(f"Failed to read or validate parquet from {path}: {e}")
            raise InvalidDataset(f"Failed to read or validate parquet file: {e}") from e

    def _write_metadata(
        self,
        dataset: MarketDataset,
        path: Path,
        serialized_data: Optional[dict[str, tuple[bytes, str]]] = None,
        existing_created_at: Optional[str] = None,
    ) -> None:
        """
        Write dataset metadata and extensive properties to a JSON file ensuring created_at stability
        and automatic runtime environment version logging.
        """
        logger = get_logger(
            symbol=dataset.symbol,
            operation="_write_metadata",
            dataset=dataset.symbol,
            method="_write_metadata",
        )
        try:
            timeframes_meta: dict[str, TimeframeMetadataDict] = {}
            total_checksum_payload = ""

            for tf, tf_data in dataset.timeframes.items():
                tf_str = tf.value if hasattr(tf, "value") else str(tf)
                if serialized_data and tf_str in serialized_data:
                    _, df_hash = serialized_data[tf_str]
                else:
                    df_bytes = tf_data.dataframe.to_parquet(
                        engine=STORAGE_CONFIG.parquet_engine,
                        compression=STORAGE_CONFIG.compression_algorithm,
                    )
                    df_hash = hashlib.sha256(df_bytes).hexdigest()

                total_checksum_payload += df_hash

                timeframes_meta[tf_str] = {
                    "data_health": tf_data.data_health.value if hasattr(tf_data.data_health, "value") else str(tf_data.data_health),
                    "candles_count": tf_data.candles_count,
                    "first_timestamp": tf_data.first_timestamp.isoformat() if tf_data.first_timestamp else None,
                    "last_timestamp": tf_data.last_timestamp.isoformat() if tf_data.last_timestamp else None,
                    "indicators_ready": tf_data.indicators_ready,
                    "profile_ready": tf_data.profile_ready,
                    "dataframe_hash": df_hash,
                }

            global_checksum = hashlib.sha256(total_checksum_payload.encode("utf-8")).hexdigest()
            now_iso = self._now()
            created_at = existing_created_at if existing_created_at else now_iso

            meta_dict: MetadataDict = {
                "schema_version": STORAGE_CONFIG.schema_version,
                "storage_version": STORAGE_CONFIG.storage_version,
                "symbol": dataset.metadata.symbol,
                "exchange": dataset.metadata.exchange,
                "source": dataset.metadata.source,
                "cache_version": dataset.metadata.cache_version,
                "downloaded_at": dataset.metadata.downloaded_at.isoformat() if dataset.metadata.downloaded_at else now_iso,
                "last_updated_at": now_iso,
                "created_at": created_at,
                "updated_at": now_iso,
                "is_valid": dataset.metadata.is_valid,
                "validation_message": dataset.metadata.validation_message,
                "parquet_engine": STORAGE_CONFIG.parquet_engine,
                "compression": STORAGE_CONFIG.compression_algorithm,
                "checksum": global_checksum,
                "python_version": platform.python_version(),
                "pandas_version": pd.__version__,
                "numpy_version": np.__version__,
                "timeframes": timeframes_meta,
            }

            temp_meta_path = path.with_suffix(".tmp")
            with open(temp_meta_path, "w", encoding="utf-8") as f:
                json.dump(meta_dict, f, indent=4, default=str)
            temp_meta_path.replace(path)

        except Exception as e:
            logger.error(f"Failed to write metadata to {path}: {e}")
            raise MetadataError(f"Failed to write metadata JSON: {e}") from e

    def _read_metadata(self, path: Path) -> dict[str, Any]:
        """
        Read dataset metadata from a JSON file and validate required fields.
        """
        logger = get_logger(operation="_read_metadata", method="_read_metadata")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            required_fields = {"symbol", "schema_version", "checksum", "timeframes"}
            missing_fields = required_fields - set(data.keys())
            if missing_fields:
                raise MetadataError(f"Metadata file at {path} is missing required fields: {missing_fields}")

            return data
        except Exception as e:
            logger.error(f"Failed to read metadata from {path}: {e}")
            raise MetadataError(f"Failed to read metadata JSON: {e}") from e


# =============================================================================
# End Of File
# =============================================================================