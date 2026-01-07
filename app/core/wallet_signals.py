"""
Wallet signal detection for notable on-chain activity.

Generates structured alerts when wallet behavior suggests unusual or
informative trading patterns.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlite_utils import Database

from app.core.logger import logger
from app.core.wallet_classifier import (
    classify_fresh_wallet,
    classify_high_confidence,
)
from app.core.wallet_feed import WalletTrade, _WALLET_TRADES_DB_PATH, _ensure_table, _get_db


@dataclass
class WalletSignal:
    """Structured wallet activity signal."""

    signal_type: str
    wallet: str
    market_id: str
    evidence: Dict[str, Any]
    risk_level: str
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation with required keys."""
        return {
            "type": self.signal_type,
            "wallet": self.wallet,
            "market_id": self.market_id,
            "evidence": self.evidence,
            "risk_level": self.risk_level,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class WalletSignalConfig:
    """Configuration for wallet signal detection thresholds."""

    big_bet_threshold: float = 10000.0
    high_confidence_entry_window_minutes: int = 15
    repeated_buys_window_minutes: int = 20
    repeated_buys_min_count: int = 3
    repeated_buys_min_total_size: float = 1500.0
    tight_market_price_band: Tuple[float, float] = (0.45, 0.55)
    pile_in_window_minutes: int = 5
    pile_in_min_wallets: int = 4
    pile_in_min_total_size: float = 5000.0
    frontrun_window_minutes: int = 5
    frontrun_price_move_threshold: float = 0.05


POLITICAL_KEYWORDS = (
    "election",
    "president",
    "senate",
    "house",
    "governor",
    "congress",
    "politic",
    "primary",
    "nominee",
    "ballot",
    "campaign",
    "poll",
)


def detect_wallet_signals(
    trades: Iterable[WalletTrade],
    db_path: str = _WALLET_TRADES_DB_PATH,
    config: Optional[WalletSignalConfig] = None,
    market_metadata_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[WalletSignal]:
    """
    Detect wallet activity signals for a batch of trades.

    Args:
        trades: Iterable of WalletTrade events to evaluate.
        db_path: Path to SQLite database with wallet trades.
        config: Optional configuration overrides.
        market_metadata_by_id: Optional mapping of market_id to metadata.

    Returns:
        List of WalletSignal instances.
    """
    trade_list = sorted(list(trades), key=lambda trade: trade.timestamp)
    if not trade_list:
        return []

    config = config or WalletSignalConfig()
    market_metadata_by_id = market_metadata_by_id or {}

    db = _get_db(db_path)
    _ensure_table(db)

    signals: List[WalletSignal] = []
    seen_keys = set()

    for trade in trade_list:
        if trade.size >= config.big_bet_threshold:
            tag = classify_fresh_wallet(
                trade.wallet,
                reference_date=_start_of_day(trade.timestamp),
                db_path=db_path,
            )
            if tag:
                key = ("fresh_wallet_big_bet", trade.wallet, trade.market_id, trade.tx_hash)
                if key not in seen_keys:
                    signals.append(
                        WalletSignal(
                            signal_type="fresh_wallet_big_bet",
                            wallet=trade.wallet,
                            market_id=trade.market_id,
                            evidence={
                                "size": trade.size,
                                "price": trade.price,
                                "side": trade.side,
                                "fresh_reference": tag.metadata.get("reference_date"),
                                "total_trades": tag.metadata.get("total_trades"),
                            },
                            risk_level="high",
                            timestamp=trade.timestamp,
                        )
                    )
                    seen_keys.add(key)

        high_conf_tag = classify_high_confidence(trade.wallet, db_path=db_path)
        if high_conf_tag:
            window_start = trade.timestamp - timedelta(
                minutes=config.high_confidence_entry_window_minutes
            )
            recent_trades = _collect_recent_trades(
                db,
                trade_list,
                window_start,
                market_id=trade.market_id,
                wallet=trade.wallet,
            )
            if len(recent_trades) == 1:
                key = ("high_confidence_entry", trade.wallet, trade.market_id)
                if key not in seen_keys:
                    signals.append(
                        WalletSignal(
                            signal_type="high_confidence_entry",
                            wallet=trade.wallet,
                            market_id=trade.market_id,
                            evidence={
                                "side": trade.side,
                                "size": trade.size,
                                "price": trade.price,
                                "confidence": high_conf_tag.confidence,
                                "metadata": high_conf_tag.metadata,
                                "window_minutes": config.high_confidence_entry_window_minutes,
                            },
                            risk_level="high",
                            timestamp=trade.timestamp,
                        )
                    )
                    seen_keys.add(key)

        if _is_tight_market(trade.price, config.tight_market_price_band) and _is_political_market(
            trade.market_id,
            market_metadata_by_id.get(trade.market_id),
        ):
            window_start = trade.timestamp - timedelta(
                minutes=config.repeated_buys_window_minutes
            )
            recent_trades = _collect_recent_trades(
                db,
                trade_list,
                window_start,
                market_id=trade.market_id,
                wallet=trade.wallet,
                side=trade.side,
            )
            total_size = sum(tr.size for tr in recent_trades)
            if (
                len(recent_trades) >= config.repeated_buys_min_count
                and total_size >= config.repeated_buys_min_total_size
            ):
                key = ("repeated_buys_tight_market", trade.wallet, trade.market_id, trade.side)
                if key not in seen_keys:
                    signals.append(
                        WalletSignal(
                            signal_type="repeated_buys_tight_market",
                            wallet=trade.wallet,
                            market_id=trade.market_id,
                            evidence={
                                "side": trade.side,
                                "trade_count": len(recent_trades),
                                "total_size": total_size,
                                "price_band": config.tight_market_price_band,
                                "window_minutes": config.repeated_buys_window_minutes,
                            },
                            risk_level="medium",
                            timestamp=trade.timestamp,
                        )
                    )
                    seen_keys.add(key)

        window_start = trade.timestamp - timedelta(minutes=config.pile_in_window_minutes)
        pile_in_trades = _collect_recent_trades(
            db,
            trade_list,
            window_start,
            market_id=trade.market_id,
            side=trade.side,
        )
        pile_in_wallets = {tr.wallet for tr in pile_in_trades}
        pile_in_total = sum(tr.size for tr in pile_in_trades)
        if (
            len(pile_in_wallets) >= config.pile_in_min_wallets
            and pile_in_total >= config.pile_in_min_total_size
        ):
            key = ("rapid_side_pile_in", trade.market_id, trade.side, window_start)
            if key not in seen_keys:
                signals.append(
                    WalletSignal(
                        signal_type="rapid_side_pile_in",
                        wallet=trade.wallet,
                        market_id=trade.market_id,
                        evidence={
                            "side": trade.side,
                            "wallets": sorted(pile_in_wallets),
                            "wallet_count": len(pile_in_wallets),
                            "total_size": pile_in_total,
                            "window_minutes": config.pile_in_window_minutes,
                        },
                        risk_level="medium",
                        timestamp=trade.timestamp,
                    )
                )
                seen_keys.add(key)

        frontrun_signal = _detect_frontrun(
            trade,
            trade_list,
            config.frontrun_window_minutes,
            config.frontrun_price_move_threshold,
        )
        if frontrun_signal:
            key = (
                "frontrun_sharp_move",
                trade.wallet,
                trade.market_id,
                trade.tx_hash,
            )
            if key not in seen_keys:
                signals.append(frontrun_signal)
                seen_keys.add(key)

    return signals


def _collect_recent_trades(
    db: Database,
    trades: List[WalletTrade],
    window_start: datetime,
    market_id: Optional[str] = None,
    wallet: Optional[str] = None,
    side: Optional[str] = None,
) -> List[WalletTrade]:
    """Collect recent trades from DB and local list within a window."""
    db_trades = _fetch_trades_since(db, window_start, market_id=market_id, side=side)

    local_trades = [
        trade
        for trade in trades
        if trade.timestamp >= window_start
        and (market_id is None or trade.market_id == market_id)
        and (wallet is None or trade.wallet == wallet)
        and (side is None or trade.side == side)
    ]

    merged = {trade.tx_hash: trade for trade in db_trades}
    for trade in local_trades:
        merged.setdefault(trade.tx_hash, trade)

    if wallet is None:
        return list(merged.values())

    return [trade for trade in merged.values() if trade.wallet == wallet]


def _fetch_trades_since(
    db: Database,
    window_start: datetime,
    market_id: Optional[str] = None,
    side: Optional[str] = None,
) -> List[WalletTrade]:
    """Fetch trades from the database since a given timestamp."""
    query = """
        SELECT wallet, market_id, side, price, size, timestamp, tx_hash
        FROM wallet_trades
        WHERE timestamp >= ?
    """
    params: List[Any] = [window_start.isoformat()]

    if market_id is not None:
        query += " AND market_id = ?"
        params.append(market_id)
    if side is not None:
        query += " AND side = ?"
        params.append(side)

    rows = db.execute(query, params).fetchall()
    trades: List[WalletTrade] = []
    for row in rows:
        try:
            trades.append(
                WalletTrade(
                    wallet=row[0],
                    market_id=row[1],
                    side=row[2],
                    price=float(row[3]),
                    size=float(row[4]),
                    timestamp=datetime.fromisoformat(row[5]),
                    tx_hash=row[6],
                )
            )
        except Exception as exc:
            logger.warning("Skipping malformed trade row: %s", exc)
    return trades


def _detect_frontrun(
    trade: WalletTrade,
    trades: List[WalletTrade],
    window_minutes: int,
    price_move_threshold: float,
) -> Optional[WalletSignal]:
    """Detect a trade that precedes a sharp price move in the same market."""
    window_end = trade.timestamp + timedelta(minutes=window_minutes)
    future_trades = [
        future_trade
        for future_trade in trades
        if future_trade.market_id == trade.market_id
        and future_trade.side == trade.side
        and trade.timestamp < future_trade.timestamp <= window_end
    ]

    if not future_trades:
        return None

    max_future_price = max(ft.price for ft in future_trades)
    min_future_price = min(ft.price for ft in future_trades)

    price_move = 0.0
    if trade.side.lower() == "yes":
        price_move = max_future_price - trade.price
    elif trade.side.lower() == "no":
        price_move = max_future_price - trade.price
    else:
        price_move = max(
            abs(max_future_price - trade.price),
            abs(trade.price - min_future_price),
        )

    if price_move >= price_move_threshold:
        return WalletSignal(
            signal_type="frontrun_sharp_move",
            wallet=trade.wallet,
            market_id=trade.market_id,
            evidence={
                "side": trade.side,
                "entry_price": trade.price,
                "max_future_price": max_future_price,
                "min_future_price": min_future_price,
                "price_move": price_move,
                "window_minutes": window_minutes,
            },
            risk_level="high",
            timestamp=trade.timestamp,
        )

    return None


def _is_tight_market(price: float, band: Tuple[float, float]) -> bool:
    """Return True if price falls within a tight market band."""
    return band[0] <= price <= band[1]


def _is_political_market(market_id: str, metadata: Optional[Dict[str, Any]]) -> bool:
    """Heuristic check for political market classification."""
    fields = [market_id]
    if metadata:
        for key in ("category", "tags", "name", "title", "question"):
            value = metadata.get(key)
            if value is None:
                continue
            if isinstance(value, (list, tuple, set)):
                fields.extend(str(item) for item in value)
            else:
                fields.append(str(value))

    joined = " ".join(fields).lower()
    return any(keyword in joined for keyword in POLITICAL_KEYWORDS)


def _start_of_day(timestamp: datetime) -> datetime:
    """Return the timestamp at start of day for the provided datetime."""
    return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
