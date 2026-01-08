"""
Insights service for calculating high-level market metrics.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from app.core.config import config

class InsightsSummary:
    """Aggregates historical data into actionable insights."""
    
    def __init__(self, db_path: str = "data/arb_logs.sqlite"):
        self.db_path = db_path

    def get_summary(self, mode: Optional[str] = None) -> Dict[str, Any]:
        """Calculate weekly metrics and top signal types."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 1. Opportunities this week
            seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
            
            where_clause = "WHERE decision = 'alerted' AND timestamp >= ?"
            params = [seven_days_ago]
            if mode:
                where_clause += " AND mode = ?"
                params.append(mode)

            cursor.execute(
                f"SELECT COUNT(*) FROM arbitrage_events {where_clause}",
                tuple(params)
            )
            opps_this_week = cursor.fetchone()[0]
            
            # 2. Average ROI
            cursor.execute(
                f"SELECT AVG(expected_profit_pct) FROM arbitrage_events {where_clause}",
                tuple(params)
            )
            avg_roi = cursor.fetchone()[0] or 0.0
            
            # 3. Most Reliable Signal
            group_where = "WHERE decision = 'alerted' AND opportunity_type IS NOT NULL"
            group_params = []
            if mode:
                group_where += " AND mode = ?"
                group_params.append(mode)

            cursor.execute(f"""
                SELECT opportunity_type, COUNT(*) as total, 
                SUM(CASE WHEN mock_result = 'success' THEN 1 ELSE 0 END) as successes
                FROM arbitrage_events 
                {group_where}
                GROUP BY opportunity_type
                HAVING total >= 3
                ORDER BY (CAST(successes AS FLOAT) / total) DESC, total DESC
                LIMIT 1
            """, tuple(group_params))
            top_signal = cursor.fetchone()
            
            top_signal_data = None
            if top_signal:
                win_rate = (top_signal['successes'] / top_signal['total']) * 100
                top_signal_data = {
                    "name": top_signal['opportunity_type'],
                    "win_rate": f"{win_rate:.1f}%"
                }
            
            conn.close()
            
            return {
                "opportunities_this_week": opps_this_week,
                "average_roi": f"{avg_roi:.2f}%",
                "top_signal_type": top_signal_data
            }
        except Exception as e:
            from app.core.logger import logger
            logger.error(f"Error calculating insights: {e}")
            return {}
