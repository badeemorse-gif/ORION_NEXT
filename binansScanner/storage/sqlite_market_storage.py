"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : storage.sqlite_market_storage
Version      : 1.1.0
Status       : ORION Production V1.0 INITIAL
===============================================================================

SQLite backend implementation for MarketStorage, responsible solely for
persisting and retrieving market datasets using native sqlite3 with
transactions, context managers, and prepared statements.

Connection lifecycle is explicitly managed so SQLite file handles are always
released after each operation, including on Windows.
===============================================================================
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

from models.market import MarketDataset, TimeframeData
from storage.market_storage import MarketStorage

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class StorageError(Exception):
    """Base exception class for all storage related errors."""


class SQLiteStorageError(StorageError):
    """Raised when SQLite operations fail."""


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting storage operation context attributes."""

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
        formatted_msg = (
            f"[{context_str}] {msg}"
            if context_str
            else msg
        )
        return formatted_msg, kwargs


# =============================================================================
# SQLite Market Storage Backend
# =============================================================================

class SQLiteMarketStorage(MarketStorage):
    """
    SQLite backend storage implementation for persisting MarketDataset
    entities using native sqlite3 with strict transactions and prepared
    statements.

    Every connection created by this class is explicitly closed when its
    operation finishes. This is required for deterministic lifecycle
    management and Windows-compatible temporary database cleanup.
    """

    def __init__(
        self,
        database_path: str,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._database_path = database_path
        self._logger_instance = (
            logger
            if logger is not None
            else base_logger
        )

        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "component": "SQLiteMarketStorage",
                "operation": "init",
            },
        )

        self._logger.info(
            f"Initializing SQLiteMarketStorage with path: {database_path}"
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
        """
        Create a SQLite connection and guarantee that it is closed.

        sqlite3.Connection implements transaction context management, but
        exiting ``with connection`` does not close the connection itself.
        This dedicated context manager closes it deterministically.
        """
        conn = sqlite3.connect(self._database_path)
        conn.row_factory = sqlite3.Row

        try:
            yield conn
        finally:
            conn.close()

    def _init_database(self) -> None:
        """Create the required market_data table if it does not exist."""

        create_table_query = """
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
                conn.execute(create_table_query)
                conn.commit()

            self._logger.info(
                "Database schema initialized successfully."
            )

        except Exception as exc:
            self._logger.error(
                f"Failed to initialize database schema: {exc}"
            )
            raise SQLiteStorageError(
                f"Failed to initialize database: {exc}"
            ) from exc

    # -------------------------------------------------------------------------
    # Public Storage Interface
    # -------------------------------------------------------------------------

    def save_dataset(
        self,
        dataset: MarketDataset,
    ) -> None:
        """
        Save all timeframes contained within a MarketDataset into SQLite
        using a single atomic transaction and prepared statements.
        """

        symbol = dataset.symbol

        logger = self._get_logger(
            symbol=symbol,
            operation="save_dataset",
        )

        logger.info(
            f"Saving MarketDataset for symbol '{symbol}' "
            f"across {len(dataset.timeframes)} timeframes."
        )

        insert_query = """
        INSERT OR REPLACE INTO market_data (
            symbol,
            timeframe,
            timestamp,
            open,
            high,
            low,
            close,
            volume
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """

        try:
            with self._connection() as conn:
                cursor = conn.cursor()

                cursor.execute("BEGIN TRANSACTION;")

                for tf_str, tf_data in dataset.timeframes.items():

                    if tf_data.df is None or tf_data.df.empty:
                        continue

                    df = tf_data.df
                    records = []

                    for ts, row in df.iterrows():

                        ts_val = (
                            int(ts.timestamp() * 1000)
                            if hasattr(ts, "timestamp")
                            else int(ts)
                        )

                        records.append(
                            (
                                symbol,
                                tf_str,
                                ts_val,
                                float(row["open"]),
                                float(row["high"]),
                                float(row["low"]),
                                float(row["close"]),
                                float(row["volume"]),
                            )
                        )

                    if records:
                        cursor.executemany(
                            insert_query,
                            records,
                        )

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
        """
        Load a MarketDataset for a symbol and specified timeframes.

        Returns None if no data is found.
        """

        logger = self._get_logger(
            symbol=symbol,
            operation="load_dataset",
        )

        logger.info(
            f"Loading MarketDataset for symbol '{symbol}' "
            f"across timeframes: {timeframes}"
        )

        if not timeframes:
            logger.warning(
                "load_dataset called with empty timeframes list."
            )
            return None

        select_query = """
        SELECT
            timestamp,
            open,
            high,
            low,
            close,
            volume
        FROM market_data
        WHERE symbol = ?
          AND timeframe = ?
        ORDER BY timestamp ASC;
        """

        try:
            timeframe_dict: dict[str, TimeframeData] = {}
            has_data = False

            with self._connection() as conn:

                cursor = conn.cursor()

                for tf in timeframes:

                    cursor.execute(
                        select_query,
                        (symbol, tf),
                    )

                    rows = cursor.fetchall()

                    if not rows:
                        continue

                    has_data = True

                    import pandas as pd

                    data_rows = []
                    timestamps = []

                    for row in rows:

                        ts_dt = datetime.fromtimestamp(
                            row["timestamp"] / 1000.0,
                            tz=timezone.utc,
                        )

                        timestamps.append(ts_dt)

                        data_rows.append(
                            {
                                "open": row["open"],
                                "high": row["high"],
                                "low": row["low"],
                                "close": row["close"],
                                "volume": row["volume"],
                            }
                        )

                    df = pd.DataFrame(
                        data_rows,
                        index=pd.DatetimeIndex(
                            timestamps,
                            name="timestamp",
                        ),
                    )

                    timeframe_dict[tf] = TimeframeData(
                        timeframe=tf,
                        df=df,
                    )

            if not has_data:
                logger.info(
                    f"No stored data found for symbol '{symbol}'."
                )
                return None

            dataset = MarketDataset(
                symbol=symbol,
                timeframes=timeframe_dict,
            )

            logger.info(
                f"Successfully loaded MarketDataset for symbol '{symbol}'."
            )

            return dataset

        except Exception as exc:
            logger.error(
                f"Failed to load MarketDataset for symbol '{symbol}': {exc}"
            )

            raise SQLiteStorageError(
                f"Failed to load dataset for symbol {symbol}: {exc}"
            ) from exc

    def dataset_exists(
        self,
        symbol: str,
    ) -> bool:
        """
        Check whether any stored market data exists for the given symbol.
        """

        logger = self._get_logger(
            symbol=symbol,
            operation="dataset_exists",
        )

        query = """
        SELECT 1
        FROM market_data
        WHERE symbol = ?
        LIMIT 1;
        """

        try:
            with self._connection() as conn:

                cursor = conn.cursor()

                cursor.execute(
                    query,
                    (symbol,),
                )

                row = cursor.fetchone()

                exists = row is not None

            logger.info(
                f"Dataset existence check for symbol '{symbol}': {exists}"
            )

            return exists

        except Exception as exc:
            logger.error(
                f"Failed to check dataset existence for symbol '{symbol}': {exc}"
            )

            raise SQLiteStorageError(
                f"Failed to check existence for symbol {symbol}: {exc}"
            ) from exc

    def delete_symbol(
        self,
        symbol: str,
    ) -> None:
        """Delete all stored market data for a symbol."""

        logger = self._get_logger(
            symbol=symbol,
            operation="delete_symbol",
        )

        logger.info(
            f"Deleting all stored data for symbol '{symbol}'."
        )

        delete_query = """
        DELETE FROM market_data
        WHERE symbol = ?;
        """

        try:
            with self._connection() as conn:

                cursor = conn.cursor()

                cursor.execute(
                    "BEGIN TRANSACTION;"
                )

                cursor.execute(
                    delete_query,
                    (symbol,),
                )

                conn.commit()

            logger.info(
                f"Successfully deleted data for symbol '{symbol}'."
            )

        except Exception as exc:
            logger.error(
                f"Failed to delete data for symbol '{symbol}': {exc}"
            )

            raise SQLiteStorageError(
                f"Failed to delete symbol {symbol}: {exc}"
            ) from exc

    def purge(self) -> None:
        """Purge all stored market data."""

        logger = self._get_logger(
            operation="purge",
        )

        logger.info(
            "Purging all stored market data from database."
        )

        purge_query = """
        DELETE FROM market_data;
        """

        try:
            with self._connection() as conn:

                cursor = conn.cursor()

                cursor.execute(
                    "BEGIN TRANSACTION;"
                )

                cursor.execute(
                    purge_query,
                )

                conn.commit()

            logger.info(
                "Successfully purged all market data."
            )

        except Exception as exc:
            logger.error(
                f"Failed to purge database: {exc}"
            )

            raise SQLiteStorageError(
                f"Failed to purge database: {exc}"
            ) from exc


# =============================================================================
# End Of File
# =============================================================================