"""
Internal alert processing and unread management.
Decoupled from outbound delivery (Telegram/Email).
"""

import sqlite3
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.core.config import get_config

logger = logging.getLogger(__name__)

class AlertService:
    """Manages internal in-app alerts and rule-based filtering."""
    
    def __init__(self, config=None):
        self.config = config or get_config()

    def process_in_app_alert(self, alert_data: Dict[str, Any]) -> bool:
        """Process a new signal for in-app alerting."""
        try:
            market_id = alert_data.get("market_id")
            market_name = alert_data.get("market_name", "Unknown Market")
            roi = alert_data.get("expected_return_pct", alert_data.get("expected_profit_pct", 0.0))
            timestamp = alert_data.get("timestamp", alert_data.get("detected_at", datetime.now().isoformat()))
            reason = alert_data.get("metadata", {}).get("reason_detected", alert_data.get("reason", ""))
            expires_at = alert_data.get("expires_at")
            category = alert_data.get("category", "General")
            mode = alert_data.get("mode", self.config.mode)
            
            # Rule Checks
            if roi < self.config.alert_min_roi:
                return False
                
            liquidity = alert_data.get("liquidity", 0.0)
            if liquidity < self.config.alert_min_liquidity:
                 meta_liq = alert_data.get("metadata", {}).get("liquidity", 0.0)
                 if max(liquidity, meta_liq) < self.config.alert_min_liquidity:
                     return False

            # Deduplication
            unique_key = f"{market_id}_{timestamp}"
            
            conn = sqlite3.connect(self.config.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM in_app_alerts WHERE unique_key = ?", (unique_key,))
            if cursor.fetchone():
                conn.close()
                return False
                
            # Store Alert
            cursor.execute(
                """
                INSERT INTO in_app_alerts (market_id, market_name, roi, reason, timestamp, unique_key, expires_at, category, mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (market_id, market_name, roi, reason, timestamp, unique_key, expires_at, category, mode)
            )
            alert_id = cursor.lastrowid
            
            # Outbound Queue log
            payload_summary = f"ROI: {roi:.2f}%, Market: {market_name}"
            cursor.execute(
                """
                INSERT INTO outbound_queue (alert_id, created_at, type, payload_summary)
                VALUES (?, ?, ?, ?)
                """,
                (alert_id, datetime.now().isoformat(), "arb_alert", payload_summary)
            )
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error processing alert: {e}")
            return False

    def get_unread_alerts_count(self) -> int:
        """Count unread alerts."""
        try:
            conn = sqlite3.connect(self.config.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM in_app_alerts WHERE seen = 0")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except:
            return 0

    def get_recent_alerts(self, limit: int = 50, mode: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch recent alerts."""
        try:
            conn = sqlite3.connect(self.config.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM in_app_alerts"
            params = []
            if mode:
                query += " WHERE mode = ?"
                params.append(mode)
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except:
            return []

    def mark_all_as_seen(self):
        """Mark alerts as read."""
        try:
            conn = sqlite3.connect(self.config.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE in_app_alerts SET seen = 1")
            conn.commit()
            conn.close()
        except:
            pass

    def clear_all_alerts(self):
        """Delete all alert history."""
        try:
            conn = sqlite3.connect(self.config.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM outbound_queue")
            cursor.execute("DELETE FROM in_app_alerts")
            conn.commit()
            conn.close()
        except:
            pass
