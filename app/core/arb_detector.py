"""
Arbitrage detection engine for Polymarket markets.

Detects arbitrage opportunities by analyzing market prices and calculates
expected profit with fee considerations. Supports two-way arbitrage detection
and includes risk assessment for detected opportunities.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
import json
import sqlite3
from pathlib import Path

from app.core.logger import logger
from app.core.signals.context_builder import build_signal_metadata


@dataclass
class ArbAlert:
    """
    Structured alert for arbitrage detection.

    Attributes:
        profitable: Whether an arbitrage opportunity exists
        reason: Human-readable explanation of the alert
        metrics: Dictionary containing detailed metrics about the opportunity
    """

    profitable: bool
    reason: str
    metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "profitable": self.profitable,
            "reason": self.reason,
            "metrics": self.metrics,
        }


@dataclass
class ArbitrageOpportunity:
    """Represents a detected arbitrage opportunity."""

    market_id: str
    market_name: str
    opportunity_type: str  # e.g., "two-way", "triangular"
    expected_profit: float
    expected_return_pct: float
    positions: List[Dict[str, Any]]  # List of positions to take
    detected_at: datetime
    risk_score: float = 0.0
    metadata: Optional[Dict[str, Any]] = None
    outcome: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None
    category: Optional[str] = None
    mode: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert opportunity to dictionary for logging and serialization."""
        return {
            "market_id": self.market_id,
            "market_name": self.market_name,
            "opportunity_type": self.opportunity_type,
            "expected_profit": self.expected_profit,
            "expected_return_pct": self.expected_return_pct,
            "positions": self.positions,
            "detected_at": self.detected_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "risk_score": self.risk_score,
            "metadata": self.metadata,
            "outcome": self.outcome,
            "category": self.category,
            "mode": self.mode
        }


class ArbitrageDetector:
    """Main arbitrage detection engine."""

    # Constants for arbitrage detection
    ARBITRAGE_THRESHOLD = 0.98  # Sum of prices must be below this for arbitrage

    def __init__(self, db_path: str = "data/polymarket_arb.db"):
        """
        Initialize the arbitrage detector.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._conn = None  # For in-memory database persistence
        self._init_database()
        logger.info("ArbitrageDetector initialized")

    def _init_database(self):
        """Initialize SQLite database for storing opportunities."""
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # For in-memory database, keep connection alive
        if self.db_path == ":memory:":
            self._conn = sqlite3.connect(self.db_path)
            conn = self._conn
        else:
            conn = sqlite3.connect(self.db_path)

        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT NOT NULL,
                market_name TEXT,
                opportunity_type TEXT,
                expected_profit REAL,
                expected_return_pct REAL,
                detected_at TIMESTAMP,
                risk_score REAL,
                metadata TEXT,
                outcome TEXT,
                expires_at TIMESTAMP,
                category TEXT,
                mode TEXT
            )
        """
        )

        # In-app alerts table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS in_app_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT NOT NULL,
                market_name TEXT,
                roi REAL,
                reason TEXT,
                timestamp TIMESTAMP,
                seen BOOLEAN DEFAULT 0,
                unique_key TEXT UNIQUE,
                expires_at TIMESTAMP,
                category TEXT,
                mode TEXT
            )
        """
        )

        # Outbound queue table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS outbound_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER,
                created_at TIMESTAMP,
                type TEXT,
                payload_summary TEXT,
                status TEXT DEFAULT 'pending_external',
                FOREIGN KEY(alert_id) REFERENCES in_app_alerts(id)
            )
        """
        )

        # Check if new columns exist for existing databases
        cursor.execute("PRAGMA table_info(opportunities)")
        columns = [info[1] for info in cursor.fetchall()]
        if "metadata" not in columns:
            cursor.execute("ALTER TABLE opportunities ADD COLUMN metadata TEXT")
        if "outcome" not in columns:
            cursor.execute("ALTER TABLE opportunities ADD COLUMN outcome TEXT")
        if "expires_at" not in columns:
            cursor.execute("ALTER TABLE opportunities ADD COLUMN expires_at TIMESTAMP")
        if "category" not in columns:
            cursor.execute("ALTER TABLE opportunities ADD COLUMN category TEXT")
        if "mode" not in columns:
            cursor.execute("ALTER TABLE opportunities ADD COLUMN mode TEXT")

        cursor.execute("PRAGMA table_info(in_app_alerts)")
        alert_columns = [info[1] for info in cursor.fetchall()]
        if "expires_at" not in alert_columns:
            cursor.execute("ALTER TABLE in_app_alerts ADD COLUMN expires_at TIMESTAMP")
        if "category" not in alert_columns:
            cursor.execute("ALTER TABLE in_app_alerts ADD COLUMN category TEXT")
        if "mode" not in alert_columns:
            cursor.execute("ALTER TABLE in_app_alerts ADD COLUMN mode TEXT")

        conn.commit()
        if self.db_path != ":memory:":
            conn.close()

    def detect_opportunities(
        self, market_data: List[Any]
    ) -> List[ArbitrageOpportunity]:
        """
        Detect arbitrage opportunities from market data.

        An arbitrage opportunity exists when the sum of prices for all
        outcomes is less than 1.0 (two-way arbitrage for binary markets).

        Args:
            market_data: List of market data dictionaries or NormalizedMarket objects

        Returns:
            List of detected arbitrage opportunities
        """
        opportunities = []

        try:
            logger.info(
                f"Analyzing {len(market_data)} markets for arbitrage opportunities"
            )

            for market in market_data:
                try:
                    if market is None:
                        logger.warning("Skipping None market data")
                        continue

                    # Handle NormalizedMarket objects
                    if hasattr(market, "to_dict"):
                        market_dict = market.to_dict()
                    else:
                        market_dict = market

                    opp = self._check_two_way_arbitrage(market_dict)
                    if opp:
                        opportunities.append(opp)
                except Exception as e:
                    market_id = market.id if hasattr(market, "id") else market.get("id", "unknown")
                    logger.error(
                        f"Error checking arbitrage for market {market_id}: {e}"
                    )
                    # Continue processing other markets

            if opportunities:
                logger.info(f"Found {len(opportunities)} arbitrage opportunities")

        except Exception as e:
            logger.error(f"Error in detect_opportunities: {e}", exc_info=True)

        return opportunities

    def _check_two_way_arbitrage(
        self, market: Dict[str, Any]
    ) -> Optional[ArbitrageOpportunity]:
        """
        Check for two-way arbitrage in a binary market.

        Two-way arbitrage exists when sum of all outcome prices < 1.0,
        allowing profit by buying all outcomes.

        Args:
            market: Market data dictionary

        Returns:
            ArbitrageOpportunity if found, None otherwise
        """
        outcomes = market.get("outcomes", [])
        if len(outcomes) < 2:
            return None

        # Calculate sum of prices
        price_sum = sum(outcome.get("price", 0) for outcome in outcomes)

        # Arbitrage exists if sum < threshold (to account for fees)
        if price_sum < self.ARBITRAGE_THRESHOLD:
            profit_margin = 1.0 - price_sum
            expected_profit = profit_margin * 100  # Per $100 invested
            expected_return_pct = (
                (profit_margin / price_sum) * 100 if price_sum > 0 else 0
            )

            positions = [
                {
                    "outcome": outcome["name"],
                    "action": "BUY",
                    "price": outcome["price"],
                    "volume": outcome.get("volume", 0),
                }
                for outcome in outcomes
            ]

            return ArbitrageOpportunity(
                market_id=market.get("id", "unknown"),
                market_name=market.get("title", market.get("name", "Unknown Market")),
                opportunity_type="two-way",
                expected_profit=expected_profit,
                expected_return_pct=expected_return_pct,
                positions=positions,
                detected_at=datetime.now(),
                expires_at=(
                    datetime.fromisoformat(market["expires_at"].replace("Z", "+00:00"))
                    if market.get("expires_at")
                    else None
                ),
                risk_score=self._calculate_risk_score(market, profit_margin),
                metadata=build_signal_metadata(market, "two-way"),
                category=market.get("category", "General")
            )

        return None

    def check_arbitrage(
        self, market: Dict[str, Any], fee_buffer: float = 0.02
    ) -> ArbAlert:
        """
        Check a single market for arbitrage opportunity.

        Computes sum_price = yes_price + no_price and triggers an alert
        if sum_price < (1 - fee_buffer).

        Args:
            market: Market data dictionary containing 'outcomes' with 'price' values
            fee_buffer: Buffer for fees (default: 0.02 = 2%)

        Returns:
            ArbAlert with profitable flag, reason, and metrics including:
            - expected_profit_pct: Expected profit percentage
            - market_name: Name of the market
            - prices: Dictionary of outcome prices (yes_price, no_price)
            - timestamp: When the check was performed
            - sum_price: Sum of all outcome prices
        """
        timestamp = datetime.now()
        outcomes = market.get("outcomes", [])
        market_name = market.get("name", "Unknown Market")

        # Handle missing or insufficient outcomes
        if len(outcomes) < 2:
            return ArbAlert(
                profitable=False,
                reason="Insufficient outcomes for arbitrage analysis",
                metrics={
                    "expected_profit_pct": 0.0,
                    "market_name": market_name,
                    "prices": {},
                    "timestamp": timestamp.isoformat(),
                    "sum_price": 0.0,
                },
            )

        # Extract prices from outcomes
        # Support both named outcomes (Yes/No) and positional outcomes
        yes_price = None
        no_price = None

        for outcome in outcomes:
            outcome_name = outcome.get("name", "").lower()
            price = outcome.get("price", 0.0)
            if outcome_name == "yes":
                yes_price = price
            elif outcome_name == "no":
                no_price = price

        # Fallback to positional if named outcomes not found
        if yes_price is None and len(outcomes) >= 1:
            yes_price = outcomes[0].get("price", 0.0)
        if no_price is None and len(outcomes) >= 2:
            no_price = outcomes[1].get("price", 0.0)

        # Ensure we have valid prices
        if yes_price is None:
            yes_price = 0.0
        if no_price is None:
            no_price = 0.0

        # Calculate sum of prices
        sum_price = yes_price + no_price

        # Calculate threshold for arbitrage
        threshold = 1.0 - fee_buffer

        # Build prices dictionary
        prices = {
            "yes_price": yes_price,
            "no_price": no_price,
        }

        # Check for arbitrage opportunity
        if sum_price < threshold:
            # Arbitrage opportunity exists
            profit_margin = 1.0 - sum_price
            expected_profit_pct = (
                (profit_margin / sum_price) * 100 if sum_price > 0 else 0.0
            )

            return ArbAlert(
                profitable=True,
                reason=f"Arbitrage opportunity: sum_price ({sum_price:.4f}) < threshold ({threshold:.4f})",
                metrics={
                    "expected_profit_pct": expected_profit_pct,
                    "market_name": market_name,
                    "prices": prices,
                    "timestamp": timestamp.isoformat(),
                    "sum_price": sum_price,
                    "threshold": threshold,
                    "profit_margin": profit_margin,
                },
            )
        else:
            # No arbitrage opportunity
            return ArbAlert(
                profitable=False,
                reason=f"No arbitrage: sum_price ({sum_price:.4f}) >= threshold ({threshold:.4f})",
                metrics={
                    "expected_profit_pct": 0.0,
                    "market_name": market_name,
                    "prices": prices,
                    "timestamp": timestamp.isoformat(),
                    "sum_price": sum_price,
                    "threshold": threshold,
                },
            )

    def get_opportunities_for_market(
        self, market_id: str, start: datetime, end: datetime, mode: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get opportunities for a specific market within a time range.
        """
        try:
            if self._conn:
                conn = self._conn
            else:
                conn = sqlite3.connect(self.db_path)

            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = """
                SELECT * FROM opportunities
                WHERE market_id = ? AND detected_at BETWEEN ? AND ?
            """
            params = [market_id, start.isoformat(), end.isoformat()]
            
            if mode:
                query += " AND mode = ?"
                params.append(mode)
                
            query += " ORDER BY detected_at ASC"

            cursor.execute(query, tuple(params))

            rows = cursor.fetchall()
            if not self._conn:
                conn.close()

            results = []
            for row in rows:
                d = dict(row)
                if d.get("metadata"):
                    try:
                        d["metadata"] = json.loads(d["metadata"])
                    except:
                        pass
                if d.get("outcome"):
                    try:
                        d["outcome"] = json.loads(d["outcome"])
                    except:
                        pass
                results.append(d)
            return results
        except Exception as e:
            logger.error(f"Error fetching opportunities for market: {e}", exc_info=True)
            return []

    def _calculate_risk_score(
        self, market: Dict[str, Any], profit_margin: float
    ) -> float:
        """
        Calculate a risk score for an arbitrage opportunity.

        Lower scores indicate lower risk (better opportunities).

        Args:
            market: Market data dictionary
            profit_margin: The profit margin of the opportunity

        Returns:
            Risk score between 0.0 and 1.0
        """
        risk = 0.5  # Base risk

        # Lower risk for higher profit margins
        if profit_margin > 0.1:
            risk -= 0.2
        elif profit_margin > 0.05:
            risk -= 0.1

        # Lower risk for higher liquidity
        liquidity = market.get("liquidity", 0)
        if liquidity > 100000:
            risk -= 0.2
        elif liquidity > 50000:
            risk -= 0.1

        return max(0.0, min(1.0, risk))

    def save_opportunity(self, opportunity: ArbitrageOpportunity):
        """
        Save detected opportunity to database.

        Args:
            opportunity: The opportunity to save

        TODO: Add duplicate detection
        TODO: Add opportunity status tracking
        """
        try:
            # Use persistent connection for in-memory database
            if self._conn:
                conn = self._conn
            else:
                conn = sqlite3.connect(self.db_path)

            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO opportunities
                (market_id, market_name, opportunity_type, expected_profit,
                 expected_return_pct, detected_at, risk_score, metadata, outcome,
                 expires_at, category, mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    opportunity.market_id,
                    opportunity.market_name,
                    opportunity.opportunity_type,
                    opportunity.expected_profit,
                    opportunity.expected_return_pct,
                    opportunity.detected_at.isoformat(),
                    opportunity.risk_score,
                    json.dumps(opportunity.metadata) if opportunity.metadata else None,
                    json.dumps(opportunity.outcome) if opportunity.outcome else None,
                    opportunity.expires_at.isoformat() if opportunity.expires_at else None,
                    opportunity.category,
                    opportunity.mode,
                ),
            )

            conn.commit()
            if not self._conn:
                conn.close()
            logger.info(f"Saved opportunity for market {opportunity.market_id}")

        except Exception as e:
            logger.error(
                f"Error saving opportunity for market {opportunity.market_id}: {e}",
                exc_info=True,
            )
            # Don't re-raise to allow continued processing

    def get_recent_opportunities(self, limit: int = 100, mode: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recent opportunities from database.

        Args:
            limit: Maximum number of opportunities to return
            mode: Optional mode filter ("live" or "mock")

        Returns:
            List of opportunity dictionaries
        """
        try:
            # Use persistent connection for in-memory database
            if self._conn:
                conn = self._conn
            else:
                conn = sqlite3.connect(self.db_path)

            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM opportunities"
            params = []
            
            if mode:
                query += " WHERE mode = ?"
                params.append(mode)
                
            query += " ORDER BY detected_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)

            rows = cursor.fetchall()
            if not self._conn:
                conn.close()

            results = []
            for row in rows:
                d = dict(row)
                if d.get("metadata"):
                    try:
                        d["metadata"] = json.loads(d["metadata"])
                    except:
                        pass
                if d.get("outcome"):
                    try:
                        d["outcome"] = json.loads(d["outcome"])
                    except:
                        pass
                results.append(d)
            return results

        except Exception as e:
            logger.error(f"Error fetching recent opportunities: {e}", exc_info=True)
            return []
