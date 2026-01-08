"""
Event logging service for arbitrage, alerts, and other system signals.
Handles all SQLite persistence for events.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from sqlite_utils import Database
from app.core.storage import get_db, get_table_columns

# Shared database path for event logs
_DB_PATH = "data/arb_logs.sqlite"

def init_db(db_path: str = _DB_PATH) -> None:
    """Initialize the SQLite database schema for event logging."""
    db = get_db(db_path)

    # 1. arbitrage_events
    if "arbitrage_events" not in db.table_names():
        db["arbitrage_events"].create(
            {
                "timestamp": str,
                "market_id": str,
                "market_name": str,
                "opportunity_type": str,
                "yes_price": float,
                "no_price": float,
                "sum": float,
                "expected_profit_pct": float,
                "mode": str,
                "decision": str,
                "mock_result": str,
                "failure_reason": str,
                "latency_ms": int,
                "expires_at": str,
                "category": str
            },
            pk="id",
        )
    else:
        # Schema evolution helpers
        cols = get_table_columns(db, "arbitrage_events")
        if "opportunity_type" not in cols:
            db.execute("ALTER TABLE arbitrage_events ADD COLUMN opportunity_type TEXT")
        if "expires_at" not in cols:
            db.execute("ALTER TABLE arbitrage_events ADD COLUMN expires_at TEXT")
        if "category" not in cols:
            db.execute("ALTER TABLE arbitrage_events ADD COLUMN category TEXT")
        if "mode" not in cols:
            db.execute("ALTER TABLE arbitrage_events ADD COLUMN mode TEXT")

    # 2. price_alert_events
    if "price_alert_events" not in db.table_names():
        db["price_alert_events"].create(
            {
                "timestamp": str,
                "alert_id": str,
                "market_id": str,
                "direction": str,
                "target_price": float,
                "trigger_price": float,
                "mode": str,
                "latency_ms": int,
            },
            pk="id",
        )

    # 3. depth_events
    if "depth_events" not in db.table_names():
        db["depth_events"].create(
            {
                "timestamp": str,
                "market_id": str,
                "metrics": str,  # JSON string
                "signal_type": str,
                "threshold_hit": str,
                "mode": str,
            },
            pk="id",
        )

    # 4. history_labels
    if "history_labels" not in db.table_names():
        db["history_labels"].create(
            {
                "timestamp": str,
                "market_id": str,
                "label_type": str,
                "notes": str,
            },
            pk="id",
        )

    # 5. user_annotations
    if "user_annotations" not in db.table_names():
        db["user_annotations"].create(
            {
                "market_id": str,
                "signal_id": int,
                "timestamp": str,
                "tag": str,
                "comment": str,
                "created_at": str,
                "mode": str
            },
            pk="id",
        )
    else:
        cols = get_table_columns(db, "user_annotations")
        if "mode" not in cols:
            db.execute("ALTER TABLE user_annotations ADD COLUMN mode TEXT")

    # 6. wallet_alerts
    if "wallet_alerts" not in db.table_names():
        db["wallet_alerts"].create(
            {
                "timestamp": str,
                "wallet": str,
                "market_id": str,
                "bet_size": float,
                "classification": str,
                "signal_type": str,
                "profile_url": str,
                "evidence": str,  # JSON string
            },
            pk="id",
        )

# --- Arbitrage Event Logging ---

def log_event(data: Dict[str, Any], db_path: str = _DB_PATH) -> None:
    """Log an arbitrage event."""
    try:
        db = get_db(db_path)
        event_data = data.copy()
        if hasattr(event_data.get("timestamp"), "isoformat"):
            event_data["timestamp"] = event_data["timestamp"].isoformat()
        db["arbitrage_events"].insert(event_data)
    except Exception as e:
        from app.core.logger import logger
        logger.error(f"Error logging event: {e}")

def fetch_recent(limit: int = 100, mode: Optional[str] = None, db_path: str = _DB_PATH) -> List[Dict[str, Any]]:
    """Fetch recent arbitrage events."""
    try:
        db = get_db(db_path)
        if "arbitrage_events" not in db.table_names():
            return []
        query = "SELECT * FROM arbitrage_events"
        params = []
        if mode:
            query += " WHERE mode = ?"
            params.append(mode)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = db.execute(query, params).fetchall()
        columns = get_table_columns(db, "arbitrage_events")
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        from app.core.logger import logger
        logger.error(f"Error fetching recent events: {e}")
        return []

# --- Price Alert Logging ---

def log_price_alert_event(data: Dict[str, Any], db_path: str = _DB_PATH) -> None:
    """Log a price alert event."""
    try:
        db = get_db(db_path)
        event_data = data.copy()
        if hasattr(event_data.get("timestamp"), "isoformat"):
            event_data["timestamp"] = event_data["timestamp"].isoformat()
        db["price_alert_events"].insert(event_data)
    except Exception as e:
        from app.core.logger import logger
        logger.error(f"Error logging price alert: {e}")

def fetch_recent_price_alerts(limit: int = 100, db_path: str = _DB_PATH) -> List[Dict[str, Any]]:
    """Fetch recent price alerts."""
    try:
        db = get_db(db_path)
        if "price_alert_events" not in db.table_names():
            return []
        rows = db.execute("SELECT * FROM price_alert_events ORDER BY timestamp DESC LIMIT ?", [limit]).fetchall()
        columns = get_table_columns(db, "price_alert_events")
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        from app.core.logger import logger
        logger.error(f"Error fetching recent price alerts: {e}")
        return []

def fetch_price_alert_events(market_id: Optional[str] = None, start: Optional[str] = None, 
                             end: Optional[str] = None, limit: int = 1000, 
                             db_path: str = _DB_PATH) -> List[Dict[str, Any]]:
    """Fetch filtered price alert events."""
    try:
        db = get_db(db_path)
        if "price_alert_events" not in db.table_names():
            return []
        query = "SELECT * FROM price_alert_events"
        params = []
        where = []
        if market_id:
            where.append("market_id = ?")
            params.append(market_id)
        if start:
            where.append("timestamp >= ?")
            params.append(start)
        if end:
            where.append("timestamp <= ?")
            params.append(end)
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = db.execute(query, params).fetchall()
        columns = get_table_columns(db, "price_alert_events")
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        from app.core.logger import logger
        logger.error(f"Error fetching price alert events: {e}")
        return []

# --- Depth Event Logging ---

def log_depth_event(data: Dict[str, Any], db_path: str = _DB_PATH) -> None:
    """Log a depth scanner event."""
    try:
        db = get_db(db_path)
        event_data = data.copy()
        if hasattr(event_data.get("timestamp"), "isoformat"):
            event_data["timestamp"] = event_data["timestamp"].isoformat()
        if isinstance(event_data.get("metrics"), dict):
            event_data["metrics"] = json.dumps(event_data["metrics"])
        db["depth_events"].insert(event_data)
    except Exception as e:
        from app.core.logger import logger
        logger.error(f"Error logging depth event: {e}")

def fetch_recent_depth_events(limit: int = 100, db_path: str = _DB_PATH) -> List[Dict[str, Any]]:
    """Fetch recent depth events."""
    try:
        db = get_db(db_path)
        if "depth_events" not in db.table_names():
            return []
        rows = db.execute("SELECT * FROM depth_events ORDER BY timestamp DESC LIMIT ?", [limit]).fetchall()
        columns = get_table_columns(db, "depth_events")
        results = []
        for row in rows:
            d = dict(zip(columns, row))
            if d.get("metrics"):
                try:
                    d["metrics"] = json.loads(d["metrics"])
                except:
                    pass
            results.append(d)
        return results
    except Exception as e:
        from app.core.logger import logger
        logger.error(f"Error fetching depth events: {e}")
        return []

def fetch_depth_events(market_id: Optional[str] = None, start: Optional[str] = None, 
                       end: Optional[str] = None, limit: int = 1000, 
                       db_path: str = _DB_PATH) -> List[Dict[str, Any]]:
    """Fetch filtered depth events."""
    try:
        db = get_db(db_path)
        if "depth_events" not in db.table_names():
            return []
        query = "SELECT * FROM depth_events"
        params = []
        where = []
        if market_id:
            where.append("market_id = ?")
            params.append(market_id)
        if start:
            where.append("timestamp >= ?")
            params.append(start)
        if end:
            where.append("timestamp <= ?")
            params.append(end)
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = db.execute(query, params).fetchall()
        columns = get_table_columns(db, "depth_events")
        results = []
        for row in rows:
            d = dict(zip(columns, row))
            if d.get("metrics"):
                try:
                    d["metrics"] = json.loads(d["metrics"])
                except:
                    pass
            results.append(d)
        return results
    except Exception as e:
        from app.core.logger import logger
        logger.error(f"Error fetching filtered depth events: {e}")
        return []

# --- History Labels & Annotations ---

def save_history_label(data: Dict[str, Any], db_path: str = _DB_PATH) -> None:
    """Save a manual history label."""
    try:
        db = get_db(db_path)
        label_data = data.copy()
        if hasattr(label_data.get("timestamp"), "isoformat"):
            label_data["timestamp"] = label_data["timestamp"].isoformat()
        db["history_labels"].insert(label_data)
    except Exception as e:
        from app.core.logger import logger
        logger.error(f"Error saving label: {e}")

def fetch_history_labels(market_id: Optional[str] = None, start: Optional[str] = None, 
                         end: Optional[str] = None, limit: int = 1000, 
                         db_path: str = _DB_PATH) -> List[Dict[str, Any]]:
    """Fetch history labels."""
    try:
        db = get_db(db_path)
        if "history_labels" not in db.table_names():
            return []
        query = "SELECT * FROM history_labels"
        params = []
        where = []
        if market_id:
            where.append("market_id = ?")
            params.append(market_id)
        if start:
            where.append("timestamp >= ?")
            params.append(start)
        if end:
            where.append("timestamp <= ?")
            params.append(end)
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = db.execute(query, params).fetchall()
        columns = get_table_columns(db, "history_labels")
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        from app.core.logger import logger
        logger.error(f"Error fetching labels: {e}")
        return []

def delete_history_label(label_id: int, db_path: str = _DB_PATH) -> bool:
    """Delete a history label."""
    try:
        db = get_db(db_path)
        db.execute("DELETE FROM history_labels WHERE id = ?", [label_id])
        db.conn.commit()
        return True
    except Exception as e:
        from app.core.logger import logger
        logger.error(f"Error deleting label: {e}")
        return False

def save_user_annotation(data: Dict[str, Any], db_path: str = _DB_PATH) -> int:
    """Save a user annotation (feedback)."""
    try:
        db = get_db(db_path)
        annotation_data = data.copy()
        if hasattr(annotation_data.get("timestamp"), "isoformat"):
            annotation_data["timestamp"] = annotation_data["timestamp"].isoformat()
        if "created_at" not in annotation_data:
            annotation_data["created_at"] = datetime.now().isoformat()
        row = db["user_annotations"].insert(annotation_data)
        return row.last_rowid
    except Exception as e:
        from app.core.logger import logger
        logger.error(f"Error saving annotation: {e}")
        return -1

def fetch_user_annotations(market_id: Optional[str] = None, start: Optional[str] = None, 
                           end: Optional[str] = None, limit: int = 1000, 
                           mode: Optional[str] = None, db_path: str = _DB_PATH) -> List[Dict[str, Any]]:
    """Fetch user annotations."""
    try:
        db = get_db(db_path)
        if "user_annotations" not in db.table_names():
            return []
        query = "SELECT * FROM user_annotations"
        params = []
        where = []
        if market_id:
            where.append("market_id = ?")
            params.append(market_id)
        if start:
            where.append("timestamp >= ?")
            params.append(start)
        if end:
            where.append("timestamp <= ?")
            params.append(end)
        if mode:
            where.append("mode = ?")
            params.append(mode)
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = db.execute(query, params).fetchall()
        columns = get_table_columns(db, "user_annotations")
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        from app.core.logger import logger
        logger.error(f"Error fetching annotations: {e}")
        return []

def delete_user_annotation(annotation_id: int, db_path: str = _DB_PATH) -> bool:
    """Delete a user annotation."""
    try:
        db = get_db(db_path)
        db["user_annotations"].delete(annotation_id)
        return True
    except Exception as e:
        from app.core.logger import logger
        logger.error(f"Error deleting annotation: {e}")
        return False

# --- Wallet Alert Logging ---

def log_wallet_alert(data: Dict[str, Any], db_path: str = _DB_PATH) -> None:
    """Log a wallet signal event."""
    try:
        db = get_db(db_path)
        event_data = data.copy()
        if hasattr(event_data.get("timestamp"), "isoformat"):
            event_data["timestamp"] = event_data["timestamp"].isoformat()
        if isinstance(event_data.get("evidence"), dict):
            event_data["evidence"] = json.dumps(event_data["evidence"])
        db["wallet_alerts"].insert(event_data)
    except Exception as e:
        from app.core.logger import logger
        logger.error(f"Error logging wallet alert: {e}")

def fetch_recent_wallet_alerts(limit: int = 100, db_path: str = _DB_PATH) -> List[Dict[str, Any]]:
    """Fetch recent wallet alerts."""
    try:
        db = get_db(db_path)
        if "wallet_alerts" not in db.table_names():
            return []
        rows = db.execute("SELECT * FROM wallet_alerts ORDER BY timestamp DESC LIMIT ?", [limit]).fetchall()
        columns = get_table_columns(db, "wallet_alerts")
        results = []
        for row in rows:
            d = dict(zip(columns, row))
            if d.get("evidence"):
                try:
                    d["evidence"] = json.loads(d["evidence"])
                except:
                    pass
            results.append(d)
        return results
    except Exception as e:
        from app.core.logger import logger
        logger.error(f"Error fetching wallet alerts: {e}")
        return []

# --- Metrics Aggregation ---

def get_annotated_metrics(db_path: str = _DB_PATH) -> Dict[str, Any]:
    """Calculate high-level metrics based on user feedback labels."""
    try:
        db = get_db(db_path)
        if "user_annotations" not in db.table_names() or "arbitrage_events" not in db.table_names():
            return {}
        total_signals = db.execute("SELECT COUNT(*) FROM arbitrage_events WHERE decision = 'alerted'").fetchone()[0]
        if total_signals == 0:
            return {}
        fp_count = db.execute("SELECT COUNT(*) FROM user_annotations WHERE tag = 'False Positive'").fetchone()[0]
        executed_count = db.execute("SELECT COUNT(*) FROM user_annotations WHERE tag = 'Executed'").fetchone()[0]
        untradeable_count = db.execute("SELECT COUNT(*) FROM user_annotations WHERE tag = 'Untradeable'").fetchone()[0]
        return {
            "false_positive_rate": (fp_count / total_signals) * 100,
            "executed_rate": (executed_count / total_signals) * 100,
            "untradeable_rate": (untradeable_count / total_signals) * 100,
            "counts": {
                "total": total_signals,
                "false_positive": fp_count,
                "executed": executed_count,
                "untradeable": untradeable_count
            }
        }
    except Exception as e:
        from app.core.logger import logger
        logger.error(f"Error calculating annotated metrics: {e}")
        return {}
