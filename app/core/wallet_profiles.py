"""
Wallet profile analytics for Polymarket traders.

This module provides functionality to track and analyze wallet trading performance,
including win rates, ROI, and market participation. It helps identify "smart wallets"
based on their trading history and outcomes.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from app.core.logger import logger
from app.core.wallet_feed import _WALLET_TRADES_DB_PATH, _ensure_table, _get_db


@dataclass
class WalletProfile:
    """Profile containing trading statistics for a wallet."""

    wallet: str
    total_trades: int = 0
    avg_entry_price: float = 0.0
    realized_outcomes: int = 0  # Number of resolved markets traded
    win_rate: float = 0.0  # Percentage of winning trades in resolved markets
    avg_roi: float = 0.0  # Average return on investment
    markets_traded: List[str] = field(default_factory=list)  # List of market IDs
    categories: Set[str] = field(default_factory=set)  # Market categories
    total_volume: float = 0.0  # Total trading volume (sum of trade sizes)
    total_profit: float = 0.0  # Total profit/loss from resolved markets

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "wallet": self.wallet,
            "total_trades": self.total_trades,
            "avg_entry_price": self.avg_entry_price,
            "realized_outcomes": self.realized_outcomes,
            "win_rate": self.win_rate,
            "avg_roi": self.avg_roi,
            "markets_traded": self.markets_traded,
            "categories": list(self.categories),
            "total_volume": self.total_volume,
            "total_profit": self.total_profit,
        }


def _calculate_wallet_stats(
    trades: List[Dict[str, Any]],
    market_outcomes: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Calculate wallet statistics from trade history.

    Args:
        trades: List of trade dictionaries from wallet_trades table
        market_outcomes: Optional dict mapping market_id to outcome info
                        Format: {market_id: {"outcome": "yes"|"no", "resolved": bool}}

    Returns:
        Dictionary containing calculated statistics
    """
    if not trades:
        return {
            "total_trades": 0,
            "avg_entry_price": 0.0,
            "realized_outcomes": 0,
            "win_rate": 0.0,
            "avg_roi": 0.0,
            "markets_traded": [],
            "categories": set(),
            "total_volume": 0.0,
            "total_profit": 0.0,
        }

    # Basic statistics
    total_trades = len(trades)
    total_price = sum(float(t.get("price", 0)) for t in trades)
    avg_entry_price = total_price / total_trades if total_trades > 0 else 0.0
    total_volume = sum(float(t.get("size", 0)) for t in trades)

    # Track markets and positions
    markets_traded = list(set(t.get("market_id") for t in trades))

    # Group trades by market to calculate positions and outcomes
    market_positions: Dict[str, List[Dict[str, Any]]] = {}
    for trade in trades:
        market_id = trade.get("market_id")
        if market_id:
            if market_id not in market_positions:
                market_positions[market_id] = []
            market_positions[market_id].append(trade)

    # Calculate realized outcomes and profitability
    realized_outcomes = 0
    total_profit = 0.0
    winning_trades = 0
    total_resolved_trades = 0

    if market_outcomes:
        for market_id, market_trades in market_positions.items():
            outcome_info = market_outcomes.get(market_id)
            if outcome_info and outcome_info.get("resolved"):
                realized_outcomes += 1
                winning_outcome = outcome_info.get("outcome")  # "yes" or "no"

                # Calculate profit for this market
                for trade in market_trades:
                    total_resolved_trades += 1
                    trade_side = trade.get("side")
                    trade_price = float(trade.get("price", 0))
                    trade_size = float(trade.get("size", 0))

                    # Calculate profit based on whether trade side matches winning outcome
                    if trade_side == winning_outcome:
                        # Winning trade: profit = size * (1 - price)
                        profit = trade_size * (1 - trade_price)
                        total_profit += profit
                        winning_trades += 1
                    else:
                        # Losing trade: loss = size * price
                        loss = trade_size * trade_price
                        total_profit -= loss

    # Calculate win rate and ROI
    win_rate = (
        (winning_trades / total_resolved_trades * 100)
        if total_resolved_trades > 0
        else 0.0
    )

    # Calculate ROI: total profit / total invested volume
    avg_roi = (total_profit / total_volume * 100) if total_volume > 0 else 0.0

    return {
        "total_trades": total_trades,
        "avg_entry_price": avg_entry_price,
        "realized_outcomes": realized_outcomes,
        "win_rate": win_rate,
        "avg_roi": avg_roi,
        "markets_traded": markets_traded,
        "categories": set(),  # Categories would need market metadata
        "total_volume": total_volume,
        "total_profit": total_profit,
    }


def get_wallet_profile(
    wallet: str,
    market_outcomes: Optional[Dict[str, Dict[str, Any]]] = None,
    db_path: str = _WALLET_TRADES_DB_PATH,
) -> Optional[WalletProfile]:
    """
    Get trading profile for a specific wallet.

    Args:
        wallet: Wallet address
        market_outcomes: Optional dict mapping market_id to outcome info
                        Format: {market_id: {"outcome": "yes"|"no", "resolved": bool}}
        db_path: Path to wallet trades database

    Returns:
        WalletProfile object with trading statistics, or None if wallet not found
    """
    try:
        db = _get_db(db_path)
        _ensure_table(db)

        # Query all trades for this wallet
        query = """
            SELECT id, wallet, market_id, side, price, size, timestamp, tx_hash
            FROM wallet_trades
            WHERE wallet = ?
            ORDER BY timestamp ASC
        """
        rows = db.execute(query, [wallet]).fetchall()

        if not rows:
            logger.debug(f"No trades found for wallet: {wallet}")
            return None

        # Convert rows to dictionaries
        columns = [
            "id",
            "wallet",
            "market_id",
            "side",
            "price",
            "size",
            "timestamp",
            "tx_hash",
        ]
        trades = [dict(zip(columns, row)) for row in rows]

        # Calculate statistics
        stats = _calculate_wallet_stats(trades, market_outcomes)

        # Create profile
        profile = WalletProfile(
            wallet=wallet,
            total_trades=stats["total_trades"],
            avg_entry_price=stats["avg_entry_price"],
            realized_outcomes=stats["realized_outcomes"],
            win_rate=stats["win_rate"],
            avg_roi=stats["avg_roi"],
            markets_traded=stats["markets_traded"],
            categories=stats["categories"],
            total_volume=stats["total_volume"],
            total_profit=stats["total_profit"],
        )

        logger.debug(
            f"Generated profile for wallet {wallet}: {stats['total_trades']} trades"
        )
        return profile

    except Exception as e:
        logger.error(f"Error getting wallet profile: {e}", exc_info=True)
        return None


def rank_wallets(
    by: str = "win_rate",
    market_outcomes: Optional[Dict[str, Dict[str, Any]]] = None,
    min_trades: int = 5,
    limit: int = 100,
    db_path: str = _WALLET_TRADES_DB_PATH,
) -> List[WalletProfile]:
    """
    Rank wallets by performance metrics.

    Args:
        by: Ranking metric - "win_rate", "profit", "roi", or "volume"
        market_outcomes: Optional dict mapping market_id to outcome info
        min_trades: Minimum number of trades required for ranking
        limit: Maximum number of wallets to return
        db_path: Path to wallet trades database

    Returns:
        List of WalletProfile objects sorted by the specified metric
    """
    valid_metrics = {"win_rate", "profit", "roi", "volume"}
    if by not in valid_metrics:
        logger.error(f"Invalid ranking metric: {by}. Must be one of {valid_metrics}")
        return []

    try:
        db = _get_db(db_path)
        _ensure_table(db)

        # Get all unique wallets with at least min_trades
        query = """
            SELECT wallet, COUNT(*) as trade_count
            FROM wallet_trades
            GROUP BY wallet
            HAVING trade_count >= ?
            ORDER BY trade_count DESC
        """
        rows = db.execute(query, [min_trades]).fetchall()

        if not rows:
            logger.debug(f"No wallets found with at least {min_trades} trades")
            return []

        # Generate profiles for each wallet
        profiles = []
        for row in rows:
            wallet = row[0]
            profile = get_wallet_profile(wallet, market_outcomes, db_path)
            if profile:
                profiles.append(profile)

        # Sort by specified metric
        if by == "win_rate":
            profiles.sort(key=lambda p: p.win_rate, reverse=True)
        elif by == "profit":
            profiles.sort(key=lambda p: p.total_profit, reverse=True)
        elif by == "roi":
            profiles.sort(key=lambda p: p.avg_roi, reverse=True)
        elif by == "volume":
            profiles.sort(key=lambda p: p.total_volume, reverse=True)

        # Apply limit
        result = profiles[:limit]
        logger.info(f"Ranked {len(result)} wallets by {by}")
        return result

    except Exception as e:
        logger.error(f"Error ranking wallets: {e}", exc_info=True)
        return []


def get_all_wallet_profiles(
    market_outcomes: Optional[Dict[str, Dict[str, Any]]] = None,
    min_trades: int = 1,
    db_path: str = _WALLET_TRADES_DB_PATH,
) -> List[WalletProfile]:
    """
    Get profiles for all wallets in the database.

    Args:
        market_outcomes: Optional dict mapping market_id to outcome info
        min_trades: Minimum number of trades required
        db_path: Path to wallet trades database

    Returns:
        List of WalletProfile objects for all wallets
    """
    try:
        db = _get_db(db_path)
        _ensure_table(db)

        # Get all unique wallets
        query = """
            SELECT wallet, COUNT(*) as trade_count
            FROM wallet_trades
            GROUP BY wallet
            HAVING trade_count >= ?
        """
        rows = db.execute(query, [min_trades]).fetchall()

        # Generate profiles
        profiles = []
        for row in rows:
            wallet = row[0]
            profile = get_wallet_profile(wallet, market_outcomes, db_path)
            if profile:
                profiles.append(profile)

        logger.info(f"Retrieved {len(profiles)} wallet profiles")
        return profiles

    except Exception as e:
        logger.error(f"Error getting all wallet profiles: {e}", exc_info=True)
        return []
