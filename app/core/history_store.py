"""
Historical tick data store for Polymarket markets.

Provides persistent storage for market tick data including prices, volumes,
and depth summaries. Uses SQLite for lightweight storage with efficient
batch inserts and indexed queries.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from sqlite_utils import Database

from app.core.logger import logger


# Default database path for history store (separate from alerts)
_HISTORY_DB_PATH = "data/market_history.db"


def _get_db(db_path: str = _HISTORY_DB_PATH) -> Database:
    """
    Get a database connection, ensuring parent directory exists.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        Database instance
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return Database(db_path)


def _ensure_table(db: Database) -> None:
    """
    Ensure the market_ticks table exists with proper schema and indexes.

    Args:
        db: Database instance
    """
    if "market_ticks" not in db.table_names():
        db["market_ticks"].create(
            {
                "market_id": str,
                "timestamp": str,
                "yes_price": float,
                "no_price": float,
                "volume": float,
                "depth_summary": str,  # JSON string for depth data
            },
            pk="id",
        )
        # Create index on (market_id, timestamp) for efficient queries
        db["market_ticks"].create_index(
            ["market_id", "timestamp"],
            index_name="idx_market_timestamp",
            if_not_exists=True,
        )
        logger.debug("Created market_ticks table with indexes")


def append_tick(
    market_id: str,
    timestamp: Union[datetime, str],
    yes_price: float,
    no_price: float,
    volume: float,
    depth_summary: Optional[Dict[str, Any]] = None,
    db_path: str = _HISTORY_DB_PATH,
) -> None:
    """
    Append a single tick to the history store.

    Args:
        market_id: Unique identifier for the market
        timestamp: Timestamp of the tick (datetime or ISO format string)
        yes_price: Price of the 'Yes' outcome (0-1)
        no_price: Price of the 'No' outcome (0-1)
        volume: Trading volume at this tick
        depth_summary: Optional dictionary with order book depth information
        db_path: Path to the SQLite database file

    Example:
        >>> append_tick(
        ...     market_id="market_123",
        ...     timestamp=datetime.now(),
        ...     yes_price=0.65,
        ...     no_price=0.35,
        ...     volume=1000.0,
        ...     depth_summary={"bid_depth": 500, "ask_depth": 600}
        ... )
    """
    try:
        db = _get_db(db_path)
        _ensure_table(db)

        # Convert timestamp to ISO format string if it's a datetime
        if isinstance(timestamp, datetime):
            timestamp_str = timestamp.isoformat()
        else:
            timestamp_str = timestamp

        # Serialize depth_summary to JSON string
        depth_json = json.dumps(depth_summary) if depth_summary else None

        tick_data = {
            "market_id": market_id,
            "timestamp": timestamp_str,
            "yes_price": yes_price,
            "no_price": no_price,
            "volume": volume,
            "depth_summary": depth_json,
        }

        db["market_ticks"].insert(tick_data)
        logger.debug(f"Appended tick for market {market_id} at {timestamp_str}")

    except Exception as e:
        logger.error(f"Error appending tick to history store: {e}", exc_info=True)
        # Don't re-raise to allow continued processing (safe if offline)


def append_ticks(
    ticks: List[Dict[str, Any]],
    db_path: str = _HISTORY_DB_PATH,
) -> int:
    """
    Append multiple ticks to the history store in a batch operation.

    This is more efficient than calling append_tick multiple times.

    Args:
        ticks: List of tick dictionaries with keys:
            - market_id (str): Market identifier
            - timestamp (datetime or str): Tick timestamp
            - yes_price (float): Yes price
            - no_price (float): No price
            - volume (float): Trading volume
            - depth_summary (dict, optional): Order book depth info
        db_path: Path to the SQLite database file

    Returns:
        Number of ticks successfully inserted

    Example:
        >>> ticks = [
        ...     {"market_id": "m1", "timestamp": "2024-01-01T12:00:00",
        ...      "yes_price": 0.6, "no_price": 0.4, "volume": 100},
        ...     {"market_id": "m1", "timestamp": "2024-01-01T12:01:00",
        ...      "yes_price": 0.61, "no_price": 0.39, "volume": 150},
        ... ]
        >>> count = append_ticks(ticks)
    """
    if not ticks:
        return 0

    try:
        db = _get_db(db_path)
        _ensure_table(db)

        # Prepare tick data for batch insert
        records = []
        for tick in ticks:
            timestamp = tick.get("timestamp")
            if isinstance(timestamp, datetime):
                timestamp_str = timestamp.isoformat()
            else:
                timestamp_str = timestamp

            depth_summary = tick.get("depth_summary")
            depth_json = json.dumps(depth_summary) if depth_summary else None

            records.append(
                {
                    "market_id": tick["market_id"],
                    "timestamp": timestamp_str,
                    "yes_price": tick["yes_price"],
                    "no_price": tick["no_price"],
                    "volume": tick["volume"],
                    "depth_summary": depth_json,
                }
            )

        # Batch insert for efficiency
        db["market_ticks"].insert_all(records)
        logger.debug(f"Batch inserted {len(records)} ticks")
        return len(records)

    except Exception as e:
        logger.error(f"Error batch inserting ticks: {e}", exc_info=True)
        # Don't re-raise to allow continued processing
        return 0


def get_ticks(
    market_id: str,
    start: Optional[Union[datetime, str]] = None,
    end: Optional[Union[datetime, str]] = None,
    limit: int = 1000,
    db_path: str = _HISTORY_DB_PATH,
) -> List[Dict[str, Any]]:
    """
    Retrieve ticks for a market within a time range.

    Args:
        market_id: Unique identifier for the market
        start: Start of time range (inclusive). If None, no lower bound.
        end: End of time range (inclusive). If None, no upper bound.
        limit: Maximum number of ticks to return (default: 1000)
        db_path: Path to the SQLite database file

    Returns:
        List of tick dictionaries ordered by timestamp ascending.
        Each dict contains: market_id, timestamp, yes_price, no_price,
        volume, depth_summary (deserialized from JSON).

    Example:
        >>> ticks = get_ticks(
        ...     market_id="market_123",
        ...     start=datetime(2024, 1, 1),
        ...     end=datetime(2024, 1, 2),
        ...     limit=500
        ... )
    """
    try:
        db = _get_db(db_path)

        # Check if table exists
        if "market_ticks" not in db.table_names():
            return []

        # Convert datetime to ISO format strings
        if isinstance(start, datetime):
            start_str = start.isoformat()
        else:
            start_str = start

        if isinstance(end, datetime):
            end_str = end.isoformat()
        else:
            end_str = end

        # Build query with parameterized values
        query = "SELECT * FROM market_ticks WHERE market_id = ?"
        params: List[Any] = [market_id]

        if start_str is not None:
            query += " AND timestamp >= ?"
            params.append(start_str)

        if end_str is not None:
            query += " AND timestamp <= ?"
            params.append(end_str)

        query += " ORDER BY timestamp ASC LIMIT ?"
        params.append(limit)

        rows = db.execute(query, params).fetchall()

        if not rows:
            return []

        # Get column names
        columns = [
            col[0]
            for col in db.execute("SELECT * FROM market_ticks LIMIT 0").description
        ]

        # Convert rows to dictionaries and deserialize depth_summary
        results = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            # Deserialize depth_summary JSON
            if row_dict.get("depth_summary"):
                try:
                    row_dict["depth_summary"] = json.loads(row_dict["depth_summary"])
                except (json.JSONDecodeError, TypeError):
                    pass  # Keep as string if deserialization fails
            results.append(row_dict)

        logger.debug(f"Retrieved {len(results)} ticks for market {market_id}")
        return results

    except Exception as e:
        logger.error(f"Error retrieving ticks: {e}", exc_info=True)
        return []


def prune_old(
    days: int,
    db_path: str = _HISTORY_DB_PATH,
) -> int:
    """
    Remove ticks older than the specified number of days.

    Args:
        days: Number of days to keep. Ticks older than this will be deleted.
        db_path: Path to the SQLite database file

    Returns:
        Number of ticks deleted

    Example:
        >>> deleted = prune_old(days=30)  # Remove ticks older than 30 days
        >>> print(f"Deleted {deleted} old ticks")
    """
    if days < 0:
        raise ValueError("days must be non-negative")

    try:
        db = _get_db(db_path)

        # Check if table exists
        if "market_ticks" not in db.table_names():
            return 0

        # Calculate cutoff timestamp
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.isoformat()

        # Count rows to be deleted
        count_result = db.execute(
            "SELECT COUNT(*) FROM market_ticks WHERE timestamp < ?", [cutoff_str]
        ).fetchone()
        count = count_result[0] if count_result else 0

        if count > 0:
            # Delete old ticks using table method
            db["market_ticks"].delete_where("timestamp < ?", [cutoff_str])
            # Explicit commit is required for sqlite-utils when using
            # separate Database objects across function calls (each call
            # to _get_db creates a new connection)
            db.conn.commit()
            logger.info(f"Pruned {count} ticks older than {days} days")

        return count

    except Exception as e:
        logger.error(f"Error pruning old ticks: {e}", exc_info=True)
        return 0


def get_tick_count(
    market_id: Optional[str] = None,
    db_path: str = _HISTORY_DB_PATH,
) -> int:
    """
    Get the total count of ticks, optionally filtered by market.

    Args:
        market_id: Optional market ID to filter by. If None, counts all ticks.
        db_path: Path to the SQLite database file

    Returns:
        Number of ticks in the store
    """
    try:
        db = _get_db(db_path)

        if "market_ticks" not in db.table_names():
            return 0

        if market_id:
            result = db.execute(
                "SELECT COUNT(*) FROM market_ticks WHERE market_id = ?", [market_id]
            ).fetchone()
        else:
            result = db.execute("SELECT COUNT(*) FROM market_ticks").fetchone()

        return result[0] if result else 0

    except Exception as e:
        logger.error(f"Error getting tick count: {e}", exc_info=True)
        return 0


def get_market_ids(
    db_path: str = _HISTORY_DB_PATH,
) -> List[str]:
    """
    Get all unique market IDs from the history store.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        List of unique market IDs in sorted order
    """
    try:
        db = _get_db(db_path)

        if "market_ticks" not in db.table_names():
            return []

        result = db.execute(
            "SELECT DISTINCT market_id FROM market_ticks ORDER BY market_id"
        ).fetchall()
        return [row[0] for row in result]

    except Exception as e:
        logger.error(f"Error getting market IDs: {e}", exc_info=True)
        return []


def _ensure_backtest_table(db: Database) -> None:
    """
    Ensure the backtest_results table exists with proper schema and indexes.

    Args:
        db: Database instance
    """
    if "backtest_results" not in db.table_names():
        db["backtest_results"].create(
            {
                "strategy": str,
                "market_id": str,
                "timestamp": str,
                "signal": str,  # JSON string for signal data
                "simulated_outcome": str,
                "notes": str,
            },
            pk="id",
        )
        # Create index on (strategy, market_id, timestamp) for efficient queries
        db["backtest_results"].create_index(
            ["strategy", "market_id", "timestamp"],
            index_name="idx_backtest_strategy_market_time",
            if_not_exists=True,
        )
        logger.debug("Created backtest_results table with indexes")


def append_backtest_result(
    strategy: str,
    market_id: str,
    timestamp: Union[datetime, str],
    signal: Dict[str, Any],
    simulated_outcome: str,
    notes: str = "",
    db_path: str = _HISTORY_DB_PATH,
) -> None:
    """
    Append a backtest result to the store.

    Args:
        strategy: Strategy name (e.g., "arb_detector", "price_alert", "depth_scanner")
        market_id: Unique identifier for the market
        timestamp: Timestamp when the signal was generated (datetime or ISO format string)
        signal: Dictionary containing signal details (will be serialized to JSON)
        simulated_outcome: Outcome of the simulation (e.g., "would_trigger", "early", "late", "wrong")
        notes: Additional notes about the result
        db_path: Path to the SQLite database file

    Example:
        >>> append_backtest_result(
        ...     strategy="arb_detector",
        ...     market_id="market_123",
        ...     timestamp=datetime.now(),
        ...     signal={"profit": 0.05, "type": "two-way"},
        ...     simulated_outcome="would_trigger",
        ...     notes="Arbitrage opportunity detected"
        ... )
    """
    try:
        db = _get_db(db_path)
        _ensure_backtest_table(db)

        # Convert timestamp to ISO format string if it's a datetime
        if isinstance(timestamp, datetime):
            timestamp_str = timestamp.isoformat()
        else:
            timestamp_str = timestamp

        # Serialize signal to JSON string
        signal_json = json.dumps(signal) if signal else None

        result_data = {
            "strategy": strategy,
            "market_id": market_id,
            "timestamp": timestamp_str,
            "signal": signal_json,
            "simulated_outcome": simulated_outcome,
            "notes": notes,
        }

        db["backtest_results"].insert(result_data)
        logger.debug(
            f"Appended backtest result for {strategy} on market {market_id} at {timestamp_str}"
        )

    except Exception as e:
        logger.error(f"Error appending backtest result: {e}", exc_info=True)
        # Don't re-raise to allow continued processing


def get_backtest_results(
    strategy: Optional[str] = None,
    market_id: Optional[str] = None,
    start: Optional[Union[datetime, str]] = None,
    end: Optional[Union[datetime, str]] = None,
    limit: int = 1000,
    db_path: str = _HISTORY_DB_PATH,
) -> List[Dict[str, Any]]:
    """
    Retrieve backtest results within specified filters.

    Args:
        strategy: Optional strategy name to filter by
        market_id: Optional market ID to filter by
        start: Start of time range (inclusive). If None, no lower bound.
        end: End of time range (inclusive). If None, no upper bound.
        limit: Maximum number of results to return (default: 1000)
        db_path: Path to the SQLite database file

    Returns:
        List of backtest result dictionaries ordered by timestamp ascending.
        Each dict contains: strategy, market_id, timestamp, signal (deserialized),
        simulated_outcome, notes.

    Example:
        >>> results = get_backtest_results(
        ...     strategy="arb_detector",
        ...     market_id="market_123",
        ...     limit=100
        ... )
    """
    try:
        db = _get_db(db_path)

        # Check if table exists
        if "backtest_results" not in db.table_names():
            return []

        # Convert datetime to ISO format strings
        if isinstance(start, datetime):
            start_str = start.isoformat()
        else:
            start_str = start

        if isinstance(end, datetime):
            end_str = end.isoformat()
        else:
            end_str = end

        # Build query with parameterized values
        query = "SELECT * FROM backtest_results WHERE 1=1"
        params: List[Any] = []

        if strategy is not None:
            query += " AND strategy = ?"
            params.append(strategy)

        if market_id is not None:
            query += " AND market_id = ?"
            params.append(market_id)

        if start_str is not None:
            query += " AND timestamp >= ?"
            params.append(start_str)

        if end_str is not None:
            query += " AND timestamp <= ?"
            params.append(end_str)

        query += " ORDER BY timestamp ASC LIMIT ?"
        params.append(limit)

        # Execute query
        cursor = db.execute(query, params)

        # Get column names
        column_names = [description[0] for description in cursor.description]

        # Convert to list of dicts and deserialize JSON
        results = []
        for row in cursor.fetchall():
            # Create dict from row using column names
            result_dict = dict(zip(column_names, row))
            # Deserialize signal JSON
            if result_dict.get("signal"):
                try:
                    result_dict["signal"] = json.loads(result_dict["signal"])
                except json.JSONDecodeError:
                    result_dict["signal"] = None
            results.append(result_dict)

        logger.debug(f"Retrieved {len(results)} backtest results")
        return results

    except Exception as e:
        logger.error(f"Error retrieving backtest results: {e}", exc_info=True)
        return []
