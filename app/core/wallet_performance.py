"""
Resolved-market evaluation for wallet performance and signal accuracy.

Tracks market outcomes, updates wallet ROI/win-rate profiles, and records
whether wallet signals were correct once a market resolves.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from sqlite_utils import Database

from app.core.logger import _DB_PATH as _ALERTS_DB_PATH
from app.core.logger import init_db, logger
from app.core.wallet_feed import _WALLET_TRADES_DB_PATH, _ensure_table, _get_db
from app.core.wallet_profiles import WalletProfile, get_wallet_profile


def evaluate_resolved_market(
    market_id: str,
    outcome: str,
    resolved_at: Optional[datetime] = None,
    wallet_db_path: str = _WALLET_TRADES_DB_PATH,
    alerts_db_path: str = _ALERTS_DB_PATH,
) -> Dict[str, Any]:
    """
    Evaluate a resolved market and update wallet performance and signal outcomes.

    Args:
        market_id: Polymarket market identifier.
        outcome: Winning outcome ("yes" or "no").
        resolved_at: Resolution timestamp (defaults to now).
        wallet_db_path: Path to wallet trades database.
        alerts_db_path: Path to alerts database containing wallet signals.

    Returns:
        Summary dictionary of updates performed.
    """
    resolved_at = resolved_at or datetime.utcnow()
    normalized_outcome = outcome.strip().lower()
    if normalized_outcome not in {"yes", "no"}:
        raise ValueError(f"Outcome must be 'yes' or 'no', got '{outcome}'.")

    wallet_db = _get_db(wallet_db_path)
    _ensure_table(wallet_db)
    _ensure_outcomes_table(wallet_db)
    _ensure_wallet_profile_table(wallet_db)

    _record_market_outcome(wallet_db, market_id, normalized_outcome, resolved_at)

    wallets = _fetch_market_wallets(wallet_db, market_id)
    market_outcomes = load_market_outcomes(wallet_db_path)

    updated_profiles = 0
    for wallet in wallets:
        profile = get_wallet_profile(wallet, market_outcomes=market_outcomes, db_path=wallet_db_path)
        if not profile:
            continue
        _upsert_wallet_profile(wallet_db, profile, resolved_at)
        updated_profiles += 1

    scored_signals = _score_wallet_signals(
        alerts_db_path=alerts_db_path,
        market_id=market_id,
        outcome=normalized_outcome,
        evaluated_at=resolved_at,
    )

    summary = {
        "market_id": market_id,
        "outcome": normalized_outcome,
        "resolved_at": resolved_at.isoformat(),
        "wallets_participated": len(wallets),
        "wallet_profiles_updated": updated_profiles,
        "signals_scored": scored_signals,
    }
    logger.info(
        "Resolved market evaluation completed",
        extra=summary,
    )
    return summary


def load_market_outcomes(db_path: str = _WALLET_TRADES_DB_PATH) -> Dict[str, Dict[str, Any]]:
    """
    Load resolved market outcomes from the wallet trades database.

    Returns:
        Mapping of market_id to {"outcome": str, "resolved": bool, "resolved_at": str}.
    """
    db = _get_db(db_path)
    _ensure_outcomes_table(db)

    rows = db.execute("SELECT market_id, outcome, resolved_at FROM market_outcomes").fetchall()
    outcomes: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        outcomes[row[0]] = {
            "outcome": row[1],
            "resolved": True,
            "resolved_at": row[2],
        }
    return outcomes


def _ensure_outcomes_table(db: Database) -> None:
    """Ensure the market_outcomes table exists."""
    if "market_outcomes" not in db.table_names():
        db["market_outcomes"].create(
            {
                "market_id": str,
                "outcome": str,
                "resolved_at": str,
            },
            pk="market_id",
        )


def _ensure_wallet_profile_table(db: Database) -> None:
    """Ensure the wallet_profile_metrics table exists."""
    if "wallet_profile_metrics" not in db.table_names():
        db["wallet_profile_metrics"].create(
            {
                "wallet": str,
                "updated_at": str,
                "total_trades": int,
                "avg_entry_price": float,
                "realized_outcomes": int,
                "win_rate": float,
                "avg_roi": float,
                "total_volume": float,
                "total_profit": float,
            },
            pk="wallet",
        )
        db["wallet_profile_metrics"].create_index(
            ["updated_at"],
            index_name="idx_wallet_profile_updated_at",
            if_not_exists=True,
        )


def _record_market_outcome(
    db: Database, market_id: str, outcome: str, resolved_at: datetime
) -> None:
    """Insert or update a market outcome entry."""
    db["market_outcomes"].insert(
        {
            "market_id": market_id,
            "outcome": outcome,
            "resolved_at": resolved_at.isoformat(),
        },
        pk="market_id",
        replace=True,
    )


def _fetch_market_wallets(db: Database, market_id: str) -> List[str]:
    """Fetch wallets that traded in the resolved market."""
    rows = db.execute(
        "SELECT DISTINCT wallet FROM wallet_trades WHERE market_id = ?",
        [market_id],
    ).fetchall()
    return [row[0] for row in rows]


def _upsert_wallet_profile(
    db: Database, profile: WalletProfile, resolved_at: datetime
) -> None:
    """Upsert wallet profile metrics into the database."""
    db["wallet_profile_metrics"].insert(
        {
            "wallet": profile.wallet,
            "updated_at": resolved_at.isoformat(),
            "total_trades": profile.total_trades,
            "avg_entry_price": profile.avg_entry_price,
            "realized_outcomes": profile.realized_outcomes,
            "win_rate": profile.win_rate,
            "avg_roi": profile.avg_roi,
            "total_volume": profile.total_volume,
            "total_profit": profile.total_profit,
        },
        pk="wallet",
        replace=True,
    )


def _score_wallet_signals(
    alerts_db_path: str,
    market_id: str,
    outcome: str,
    evaluated_at: datetime,
) -> int:
    """Score wallet alerts against the resolved outcome."""
    init_db(alerts_db_path)
    db = Database(alerts_db_path)
    _ensure_signal_outcomes_table(db)

    rows = db.execute(
        "SELECT id, wallet, market_id, signal_type, evidence FROM wallet_alerts "
        "WHERE market_id = ?",
        [market_id],
    ).fetchall()

    scored = 0
    for row in rows:
        alert_id, wallet, market_id_row, signal_type, evidence = row
        if db["wallet_signal_outcomes"].exists(alert_id):
            continue

        signal_side = _extract_signal_side(evidence)
        is_correct = bool(signal_side and signal_side.lower() == outcome)

        db["wallet_signal_outcomes"].insert(
            {
                "wallet_alert_id": alert_id,
                "market_id": market_id_row,
                "wallet": wallet,
                "signal_type": signal_type,
                "signal_side": signal_side,
                "market_outcome": outcome,
                "is_correct": int(is_correct),
                "evaluated_at": evaluated_at.isoformat(),
            },
            pk="wallet_alert_id",
            replace=False,
        )
        scored += 1
    return scored


def _ensure_signal_outcomes_table(db: Database) -> None:
    """Ensure wallet_signal_outcomes table exists."""
    if "wallet_signal_outcomes" not in db.table_names():
        db["wallet_signal_outcomes"].create(
            {
                "wallet_alert_id": int,
                "market_id": str,
                "wallet": str,
                "signal_type": str,
                "signal_side": str,
                "market_outcome": str,
                "is_correct": int,
                "evaluated_at": str,
            },
            pk="wallet_alert_id",
        )
        db["wallet_signal_outcomes"].create_index(
            ["market_id"],
            index_name="idx_wallet_signal_outcomes_market",
            if_not_exists=True,
        )


def _extract_signal_side(evidence: Any) -> Optional[str]:
    """Extract the side (yes/no) from wallet signal evidence."""
    if evidence is None:
        return None
    parsed = evidence
    if isinstance(evidence, str):
        try:
            parsed = json.loads(evidence)
        except json.JSONDecodeError:
            return None

    if isinstance(parsed, dict):
        side = parsed.get("side")
        if side is not None:
            return str(side).strip().lower()
    return None


def backfill_resolved_markets(
    market_outcomes: Dict[str, str],
    resolved_at: Optional[datetime] = None,
    wallet_db_path: str = _WALLET_TRADES_DB_PATH,
    alerts_db_path: str = _ALERTS_DB_PATH,
) -> List[Dict[str, Any]]:
    """
    Backfill multiple resolved markets in batch.

    Args:
        market_outcomes: Mapping of market_id to outcome ("yes" or "no").
        resolved_at: Optional timestamp to use for all updates.
        wallet_db_path: Path to wallet trades database.
        alerts_db_path: Path to alerts database.

    Returns:
        List of summary dictionaries (one per market).
    """
    resolved_at = resolved_at or datetime.utcnow()
    summaries = []
    for market_id, outcome in market_outcomes.items():
        summaries.append(
            evaluate_resolved_market(
                market_id=market_id,
                outcome=outcome,
                resolved_at=resolved_at,
                wallet_db_path=wallet_db_path,
                alerts_db_path=alerts_db_path,
            )
        )
    return summaries
