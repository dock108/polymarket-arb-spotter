"""
Wallet event ingestion for Polymarket transactions.

This module provides functionality to subscribe to Polymarket transaction feeds
(REST/WebSocket), normalize trade events, and store them in a SQLite database
with retry and duplication protection.
"""

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

import requests
from sqlite_utils import Database

from app.core.logger import logger


# Default database path for wallet trades
_WALLET_TRADES_DB_PATH = "data/wallet_trades.db"


@dataclass
class WalletTrade:
    """Normalized wallet trade event."""

    wallet: str
    market_id: str
    side: str  # "yes" or "no"
    price: float
    size: float
    timestamp: datetime
    tx_hash: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "wallet": self.wallet,
            "market_id": self.market_id,
            "side": self.side,
            "price": self.price,
            "size": self.size,
            "timestamp": self.timestamp.isoformat(),
            "tx_hash": self.tx_hash,
        }


def _get_db(db_path: str = _WALLET_TRADES_DB_PATH) -> Database:
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
    Ensure the wallet_trades table exists with proper schema and indexes.

    Args:
        db: Database instance
    """
    if "wallet_trades" not in db.table_names():
        db["wallet_trades"].create(
            {
                "wallet": str,
                "market_id": str,
                "side": str,
                "price": float,
                "size": float,
                "timestamp": str,
                "tx_hash": str,
            },
            pk="id",
        )
        # Create unique index on tx_hash for duplication protection
        db["wallet_trades"].create_index(
            ["tx_hash"],
            index_name="idx_tx_hash",
            unique=True,
            if_not_exists=True,
        )
        # Create index on (wallet, timestamp) for efficient queries
        db["wallet_trades"].create_index(
            ["wallet", "timestamp"],
            index_name="idx_wallet_timestamp",
            if_not_exists=True,
        )
        # Create index on (market_id, timestamp) for efficient queries
        db["wallet_trades"].create_index(
            ["market_id", "timestamp"],
            index_name="idx_market_timestamp",
            if_not_exists=True,
        )
        logger.debug("Created wallet_trades table with indexes")


class WalletFeed:
    """
    Client for ingesting Polymarket wallet transaction events.

    Supports both REST API polling and WebSocket streaming for real-time
    transaction data. Includes retry logic and duplication protection.
    """

    # Polymarket CLOB API endpoints
    DEFAULT_CLOB_URL = "https://clob.polymarket.com"
    
    # Retry configuration
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1.0  # seconds
    DEFAULT_TIMEOUT = 30  # seconds

    def __init__(
        self,
        clob_url: str = DEFAULT_CLOB_URL,
        db_path: str = _WALLET_TRADES_DB_PATH,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """
        Initialize wallet feed client.

        Args:
            clob_url: Base URL for Polymarket CLOB API
            db_path: Path to SQLite database for storing trades
            max_retries: Maximum number of retry attempts for failed requests
            retry_delay: Base delay between retries (exponential backoff applied)
            timeout: Request timeout in seconds
        """
        self.clob_url = clob_url.rstrip("/")
        self.db_path = db_path
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.session = requests.Session()
        
        # Initialize database
        db = _get_db(db_path)
        _ensure_table(db)

        # Cache for deduplication (in-memory supplement to DB unique index)
        self._seen_tx_hashes: Set[str] = set()

        logger.info(f"WalletFeed initialized with clob_url: {clob_url}")

    def _request_with_retry(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional[requests.Response]:
        """
        Make an HTTP request with retry logic and exponential backoff.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            params: Query parameters
            **kwargs: Additional arguments passed to requests

        Returns:
            Response object if successful, None otherwise
        """
        kwargs.setdefault("timeout", self.timeout)

        for attempt in range(self.max_retries):
            try:
                response = self.session.request(method, url, params=params, **kwargs)
                response.raise_for_status()
                return response

            except requests.exceptions.RequestException as e:
                delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                
                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Request failed after {self.max_retries} attempts: {e}"
                    )
                    return None

        return None

    def _normalize_trade(self, raw_trade: Dict[str, Any]) -> Optional[WalletTrade]:
        """
        Normalize a raw trade event into standardized format.

        Args:
            raw_trade: Raw trade data from API

        Returns:
            WalletTrade object or None if normalization fails
        """
        try:
            # Extract required fields
            # Note: Polymarket API trade format may vary, adjust field names as needed
            wallet = raw_trade.get("maker_address") or raw_trade.get("taker_address")
            market_id = raw_trade.get("asset_id") or raw_trade.get("market")
            
            # Determine side (yes/no) based on outcome field
            # In Polymarket, outcome is typically 0 for No, 1 for Yes
            outcome = raw_trade.get("outcome")
            if outcome == "0" or outcome == 0:
                side = "no"
            elif outcome == "1" or outcome == 1:
                side = "yes"
            else:
                # Try alternate field names
                side_raw = raw_trade.get("side", "").lower()
                side = "yes" if side_raw in ["yes", "buy"] else "no"

            price = float(raw_trade.get("price", 0))
            size = float(raw_trade.get("size", 0))
            
            # Parse timestamp
            timestamp_raw = raw_trade.get("timestamp") or raw_trade.get("created_at")
            if isinstance(timestamp_raw, str):
                timestamp = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
            elif isinstance(timestamp_raw, (int, float)):
                timestamp = datetime.fromtimestamp(timestamp_raw)
            else:
                timestamp = datetime.now()

            tx_hash = raw_trade.get("transaction_hash") or raw_trade.get("id")

            if not all([wallet, market_id, tx_hash]):
                logger.warning(f"Missing required fields in trade: {raw_trade}")
                return None

            return WalletTrade(
                wallet=wallet,
                market_id=market_id,
                side=side,
                price=price,
                size=size,
                timestamp=timestamp,
                tx_hash=tx_hash,
            )

        except Exception as e:
            logger.error(f"Error normalizing trade: {e}", exc_info=True)
            return None

    def _is_duplicate(self, tx_hash: str, db: Database) -> bool:
        """
        Check if a transaction hash already exists in the database.

        Args:
            tx_hash: Transaction hash to check
            db: Database instance

        Returns:
            True if duplicate, False otherwise
        """
        # Check in-memory cache first
        if tx_hash in self._seen_tx_hashes:
            return True

        # Check database
        try:
            existing = list(db["wallet_trades"].rows_where("tx_hash = ?", [tx_hash]))
            if existing:
                self._seen_tx_hashes.add(tx_hash)
                return True
        except Exception as e:
            logger.error(f"Error checking for duplicate: {e}")

        return False

    def store_trade(
        self,
        trade: WalletTrade,
        db_path: Optional[str] = None,
    ) -> bool:
        """
        Store a single trade in the database with duplication protection.

        Args:
            trade: WalletTrade object to store
            db_path: Optional database path (uses instance default if not provided)

        Returns:
            True if trade was stored, False if duplicate or error
        """
        db_path = db_path or self.db_path
        
        try:
            db = _get_db(db_path)
            _ensure_table(db)

            # Check for duplicates
            if self._is_duplicate(trade.tx_hash, db):
                logger.debug(f"Skipping duplicate trade: {trade.tx_hash}")
                return False

            # Store trade
            trade_data = trade.to_dict()
            db["wallet_trades"].insert(trade_data, ignore=True)
            
            # Add to cache
            self._seen_tx_hashes.add(trade.tx_hash)
            
            logger.debug(
                f"Stored trade for wallet {trade.wallet} in market {trade.market_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error storing trade: {e}", exc_info=True)
            return False

    def store_trades(
        self,
        trades: List[WalletTrade],
        db_path: Optional[str] = None,
    ) -> int:
        """
        Store multiple trades in the database with duplication protection.

        Args:
            trades: List of WalletTrade objects to store
            db_path: Optional database path (uses instance default if not provided)

        Returns:
            Number of trades successfully stored (excluding duplicates)
        """
        if not trades:
            return 0

        db_path = db_path or self.db_path
        stored_count = 0

        try:
            db = _get_db(db_path)
            _ensure_table(db)

            # Filter out duplicates
            new_trades = []
            for trade in trades:
                if not self._is_duplicate(trade.tx_hash, db):
                    new_trades.append(trade.to_dict())
                    self._seen_tx_hashes.add(trade.tx_hash)

            # Batch insert
            if new_trades:
                db["wallet_trades"].insert_all(new_trades, ignore=True)
                stored_count = len(new_trades)
                logger.debug(f"Batch stored {stored_count} trades")

        except Exception as e:
            logger.error(f"Error batch storing trades: {e}", exc_info=True)

        return stored_count

    def fetch_trades(
        self,
        market_id: Optional[str] = None,
        wallet: Optional[str] = None,
        limit: int = 100,
    ) -> List[WalletTrade]:
        """
        Fetch trades from Polymarket CLOB API.

        Args:
            market_id: Optional market ID to filter trades
            wallet: Optional wallet address to filter trades
            limit: Maximum number of trades to fetch

        Returns:
            List of normalized WalletTrade objects
        """
        logger.info(f"Fetching trades (market={market_id}, wallet={wallet}, limit={limit})")

        # Build request parameters
        params: Dict[str, Any] = {"limit": min(limit, 1000)}
        
        if market_id:
            params["asset_id"] = market_id
        if wallet:
            params["maker"] = wallet

        url = f"{self.clob_url}/trades"
        response = self._request_with_retry("GET", url, params=params)

        if response is None:
            return []

        try:
            data = response.json()
            
            # Handle different response formats
            trades_raw = []
            if isinstance(data, list):
                trades_raw = data
            elif isinstance(data, dict):
                trades_raw = data.get("data", data.get("trades", []))

            # Normalize trades
            trades = []
            for raw_trade in trades_raw:
                trade = self._normalize_trade(raw_trade)
                if trade:
                    trades.append(trade)

            logger.info(f"Fetched and normalized {len(trades)} trades")
            return trades

        except Exception as e:
            logger.error(f"Error fetching trades: {e}", exc_info=True)
            return []

    def ingest_trades(
        self,
        market_id: Optional[str] = None,
        wallet: Optional[str] = None,
        limit: int = 100,
    ) -> int:
        """
        Fetch and store trades in one operation.

        Args:
            market_id: Optional market ID to filter trades
            wallet: Optional wallet address to filter trades
            limit: Maximum number of trades to fetch

        Returns:
            Number of new trades stored
        """
        trades = self.fetch_trades(market_id=market_id, wallet=wallet, limit=limit)
        return self.store_trades(trades)

    def subscribe_to_trades(
        self,
        on_trade: Callable[[WalletTrade], None],
        market_id: Optional[str] = None,
        wallet: Optional[str] = None,
        poll_interval: float = 5.0,
        auto_store: bool = True,
    ) -> None:
        """
        Subscribe to trade events via polling (REST API).

        This is a simple polling-based subscription. For production use,
        consider implementing WebSocket streaming for lower latency.

        Args:
            on_trade: Callback function called for each new trade
            market_id: Optional market ID to filter trades
            wallet: Optional wallet address to filter trades
            poll_interval: Seconds between polling requests
            auto_store: Whether to automatically store trades in database

        Note:
            This method runs indefinitely. Use in a separate thread or with
            appropriate termination logic.
        """
        logger.info(
            f"Starting trade subscription (market={market_id}, wallet={wallet}, "
            f"poll_interval={poll_interval}s)"
        )

        last_seen_tx_hashes: Set[str] = set()

        while True:
            try:
                trades = self.fetch_trades(
                    market_id=market_id,
                    wallet=wallet,
                    limit=100,
                )

                # Process new trades
                for trade in trades:
                    if trade.tx_hash not in last_seen_tx_hashes:
                        # Store if enabled
                        if auto_store:
                            self.store_trade(trade)
                        
                        # Call user callback
                        try:
                            on_trade(trade)
                        except Exception as e:
                            logger.error(f"Error in trade callback: {e}")

                        last_seen_tx_hashes.add(trade.tx_hash)

                # Cleanup old hashes (keep last 1000)
                if len(last_seen_tx_hashes) > 1000:
                    last_seen_tx_hashes = set(list(last_seen_tx_hashes)[-1000:])

                time.sleep(poll_interval)

            except Exception as e:
                logger.error(f"Error in trade subscription: {e}", exc_info=True)
                time.sleep(poll_interval)


def get_wallet_trades(
    wallet: Optional[str] = None,
    market_id: Optional[str] = None,
    limit: int = 100,
    db_path: str = _WALLET_TRADES_DB_PATH,
) -> List[Dict[str, Any]]:
    """
    Retrieve wallet trades from the database.

    Args:
        wallet: Optional wallet address to filter by
        market_id: Optional market ID to filter by
        limit: Maximum number of trades to return
        db_path: Path to the SQLite database file

    Returns:
        List of trade dictionaries
    """
    try:
        db = _get_db(db_path)
        _ensure_table(db)

        # Build query
        where_clauses = []
        params = []
        
        if wallet:
            where_clauses.append("wallet = ?")
            params.append(wallet)
        
        if market_id:
            where_clauses.append("market_id = ?")
            params.append(market_id)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Build full query with ORDER BY and LIMIT
        query = f"""
            SELECT * FROM wallet_trades 
            WHERE {where_sql}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        params.append(limit)

        # Execute query
        rows = db.execute(query, params).fetchall()

        if not rows:
            return []

        # Get column names
        columns = [
            col[0]
            for col in db.execute("SELECT * FROM wallet_trades LIMIT 0").description
        ]

        # Convert rows to dictionaries
        results = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            results.append(row_dict)

        return results

    except Exception as e:
        logger.error(f"Error retrieving wallet trades: {e}", exc_info=True)
        return []
