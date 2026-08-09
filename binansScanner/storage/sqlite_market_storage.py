"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : storage.sqlite_market_storage
Version      : 1.2.0
Status       : ORION Canonical Market Contract
===============================================================================

SQLite backend implementation for MarketStorage.

The backend persists the canonical MarketDataset contract defined by
models.market.  In particular, TimeframeData exposes ``dataframe`` (not
``df``), and MarketDataset carries canonical MarketMetadata.
===============================================================================
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

import pandas as pd

from enums import DataHealth, Timeframe
from models.market import MarketDataset, MarketMetadata, TimeframeData
from storage.market_storage import MarketStorage

base_logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Base exception class for SQLite storage failures."""


class SQLiteStorageError(StorageError):
    """Raised when a SQLite storage operation fails."""


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter injecting SQLite storage context."""

    def process(
        self,
        msg: str,
        kwargs: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(
            f"{key}={value}"
            for key, value in context.items()
            if value is not None
        )
        return (
            f"[{context_str}] {msg}" if context_str else msg,
            kwargs,
        )


class SQLiteMarketStorage(MarketStorage):
    """Canonical SQLite persistence backend for MarketDataset."""

    def __init__(
        self,
        database_path: str,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._database_path = database_path
        self._logger_instance = logger if logger is not None else base_logger
        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "component": "SQLiteMarketStorage",
                "operation": "init",
            },
        )
        self._init_database()

    def _get_logger(
        self,
        symbol: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> LoggerAdapter:
        return LoggerAdapter(
            self._logger_instance,
            {
                "component": "SQLiteMarketStorage",
                "symbol": symbol,
                "operation": operation,
            },
        )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Create and deterministically close one SQLite connection."""
        conn = sqlite3.connect(self._database_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_database(self) -> None:
        """Create the canonical OHLCV persistence table."""
        query = """
        CREATE TABLE IF NOT EXISTS market_data (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            PRIMARY KEY (symbol, timeframe, timestamp)
        );
        """
        try:
            with self._connection() as conn:
                conn.execute(query)
                conn.commit()
        except Exception as exc:
            self._logger.error(f"Failed to initialize database schema: {exc}")
            raise SQLiteStorageError(
                f"Failed to initialize database: {exc}"
            ) from exc

    # -------------------------------------------------------------------------
    # Canonical Storage Interface
    # -------------------------------------------------------------------------

    def execute(self, dataset: MarketDataset) -> None:
        """Unified storage execution contract used by Orchestrator."""
        if not isinstance(dataset, MarketDataset):
            raise SQLiteStorageError(
                "Storage execute() requires a MarketDataset instance."
            )
        self.save_dataset(dataset)

    def save_dataset(self, dataset: MarketDataset) -> None:
        """Persist every canonical timeframe DataFrame atomically."""
        if not isinstance(dataset, MarketDataset):
            raise SQLiteStorageError("save_dataset requires a MarketDataset instance.")

        symbol = dataset.symbol
        logger = self._get_logger(symbol=symbol, operation="save_dataset")

        insert_query = """
        INSERT OR REPLACE INTO market_data (
            symbol, timeframe, timestamp, open, high, low, close, volume
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """

        try:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("BEGIN TRANSACTION;")

                for timeframe, timeframe_data in dataset.timeframes.items():
                    dataframe = timeframe_data.dataframe
                    if dataframe is None or dataframe.empty:
                        continue

                    timeframe_value = (
                        timeframe.value
                        if isinstance(timeframe, Timeframe)
                        else str(timeframe)
                    )

                    records: list[tuple[Any, ...]] = []
                    for timestamp, row in dataframe.iterrows():
                        if hasattr(timestamp, "timestamp"):
                            timestamp_ms = int(timestamp.timestamp() * 1000)
                        else:
                            timestamp_ms = int(timestamp)

                        records.append(
                            (
                                symbol,
                                timeframe_value,
                                timestamp_ms,
                                float(row["open"]),
                                float(row["high"]),
                                float(row["low"]),
                                float(row["close"]),
                                float(row["volume"]),
                            )
                        )

                    if records:
                        cursor.executemany(insert_query, records)

                conn.commit()

            logger.info(
                f"Successfully saved MarketDataset for symbol '{symbol}'."
            )
        except Exception as exc:
            logger.error(
                f"Failed to save MarketDataset for symbol '{symbol}': {exc}"
            )
            raise SQLiteStorageError(
                f"Failed to save dataset for symbol {symbol}: {exc}"
            ) from exc

    def load_dataset(
        self,
        symbol: str,
        timeframes: list[str],
    ) -> Optional[MarketDataset]:
        """Load canonical MarketDataset data from SQLite."""
        logger = self._get_logger(symbol=symbol, operation="load_dataset")
        if not timeframes:
            return None

        query = """
        SELECT timestamp, open, high, low, close, volume
        FROM market_data
        WHERE symbol = ? AND timeframe = ?
        ORDER BY timestamp ASC;
        """

        try:
            timeframe_models: dict[Timeframe, TimeframeData] = {}

            with self._connection() as conn:
                cursor = conn.cursor()

                for raw_timeframe in timeframes:
                    try:
                        timeframe = (
                            raw_timeframe
                            if isinstance(raw_timeframe, Timeframe)
                            else Timeframe(str(raw_timeframe))
                        )
                    except ValueError:
                        logger.warning(
                            f"Unknown timeframe '{raw_timeframe}' skipped."
                        )
                        continue

                    cursor.execute(query, (symbol, timeframe.value))
                    rows = cursor.fetchall()
                    if not rows:
                        continue

                    timestamps = [
                        datetime.fromtimestamp(
                            row["timestamp"] / 1000.0,
                            tz=timezone.utc,
                        )
                        for row in rows
                    ]

                    dataframe = pd.DataFrame(
                        [
                            {
                                "open": row["open"],
                                "high": row["high"],
                                "low": row["low"],
                                "close": row["close"],
                                "volume": row["volume"],
                            }
                            for row in rows
                        ],
                        index=pd.DatetimeIndex(
                            timestamps,
                            name="timestamp",
                        ),
                    )

                    candles_count = len(dataframe)
                    if candles_count >= 1000:
                        data_health = DataHealth.EXCELLENT
                    elif candles_count >= 500:
                        data_health = DataHealth.GOOD
                    elif candles_count >= 100:
                        data_health = DataHealth.ACCEPTABLE
                    elif candles_count > 0:
                        data_health = DataHealth.POOR
                    else:
                        data_health = DataHealth.INVALID

                    timeframe_models[timeframe] = TimeframeData(
                        timeframe=timeframe,
                        dataframe=dataframe,
                        data_health=data_health,
                        candles_count=candles_count,
                        first_timestamp=timestamps[0] if timestamps else None,
                        last_timestamp=timestamps[-1] if timestamps else None,
                    )

            if not timeframe_models:
                logger.info(f"No stored data found for symbol '{symbol}'.")
                return None

            now = datetime.now(timezone.utc)
            metadata = MarketMetadata(
                symbol=symbol,
                exchange="BINANCE",
                source="BINANCE_API",
                cache_version="1.0.0",
                downloaded_at=now,
                last_updated_at=now,
                is_valid=True,
                validation_message=None,
            )

            return MarketDataset(
                metadata=metadata,
                timeframes=timeframe_models,
            )

        except Exception as exc:
            logger.error(
                f"Failed to load MarketDataset for symbol '{symbol}': {exc}"
            )
            raise SQLiteStorageError(
                f"Failed to load dataset for symbol {symbol}: {exc}"
            ) from exc

    def dataset_exists(self, symbol: str) -> bool:
        """Return whether at least one candle exists for a symbol."""
        query = """
        SELECT 1 FROM market_data WHERE symbol = ? LIMIT 1;
        """
        try:
            with self._connection() as conn:
                return conn.execute(query, (symbol,)).fetchone() is not None
        except Exception as exc:
            raise SQLiteStorageError(
                f"Failed to check existence for symbol {symbol}: {exc}"
            ) from exc

    def delete_symbol(self, symbol: str) -> None:
        """Delete all persisted market data for a symbol."""
        try:
            with self._connection() as conn:
                conn.execute(
                    "DELETE FROM market_data WHERE symbol = ?;",
                    (symbol,),
                )
                conn.commit()
        except Exception as exc:
            raise SQLiteStorageError(
                f"Failed to delete symbol {symbol}: {exc}"
            ) from exc

    def delete_dataset(self, symbol: str) -> None:
        """Canonical alias for delete_symbol."""
        self.delete_symbol(symbol)

    def purge(self) -> None:
        """Delete all persisted market data."""
        try:
            with self._connection() as conn:
                conn.execute("DELETE FROM market_data;")
                conn.commit()
        except Exception as exc:
            raise SQLiteStorageError(
                f"Failed to purge database: {exc}"
            ) from exc
