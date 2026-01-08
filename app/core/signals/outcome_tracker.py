"""
Outcome Tracker for Polymarket Arbitrage Spotter.

Evaluates the performance of detected arbitrage signals over specified
time windows (e.g., T+5m, T+30m) by analyzing subsequent price movements.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json
import sqlite3

from app.core.logger import logger
from app.core.history_store import get_ticks

def evaluate_signal_outcome(
    market_id: str,
    signal_timestamp: datetime,
    initial_roi: float,
    window_minutes: int = 5
) -> Dict[str, Any]:
    """
    Evaluate the outcome of a signal after a specified window.
    
    Args:
        market_id: Market identifier.
        signal_timestamp: When the signal was detected.
        initial_roi: ROI at detection time.
        window_minutes: Time window to look ahead.
        
    Returns:
        Outcome classification and details.
    """
    end_time = signal_timestamp + timedelta(minutes=window_minutes)
    
    # Fetch ticks after the signal
    ticks = get_ticks(
        market_id=market_id,
        start=signal_timestamp,
        end=end_time,
        limit=100
    )
    
    if not ticks or len(ticks) < 2:
        return {
            "classification": "unknown",
            "reason": "Insufficient data in window",
            "final_roi": None
        }

    # Analyze profitability in the window
    # ROI = (1 / (yes_price + no_price)) - 1
    profits = []
    for tick in ticks:
        price_sum = tick["yes_price"] + tick["no_price"]
        if price_sum > 0:
            roi = (1.0 / price_sum - 1.0) * 100
            profits.append(roi)
    
    if not profits:
        return {"classification": "unknown", "reason": "No valid price data"}

    final_roi = profits[-1]
    avg_roi = sum(profits) / len(profits)
    max_roi = max(profits)
    
    # Classification logic
    # 1. Remained Profitable: ROI stayed above a threshold (e.g., 0.5%)
    if all(p > 0.5 for p in profits):
        classification = "remained_profitable"
        reason = f"Maintained ROI > 0.5% throughout {window_minutes}m window."
    # 2. Produced Loss: Final ROI is negative
    elif final_roi < 0:
        classification = "produced_loss"
        reason = f"Arbitrage reversed into a loss; final ROI: {final_roi:.2f}%."
    # 3. Collapsed: ROI dropped significantly
    elif final_roi < initial_roi * 0.2:
        classification = "collapsed"
        reason = f"Profitability decayed by > 80% in {window_minutes}m."
    else:
        classification = "neutral"
        reason = f"ROI fluctuated; final: {final_roi:.2f}%."

    return {
        "classification": classification,
        "reason": reason,
        "initial_roi": round(initial_roi, 4),
        "final_roi": round(final_roi, 4),
        "avg_roi": round(avg_roi, 4),
        "max_roi": round(max_roi, 4),
        "window_m": window_minutes
    }

def update_all_pending_outcomes(db_path: str = "data/polymarket_arb.db"):
    """
    Iterate through signals without outcomes and update them if enough time has passed.
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Find opportunities older than 30 mins with no outcome
        cutoff = (datetime.now() - timedelta(minutes=30)).isoformat()
        cursor.execute(
            "SELECT * FROM opportunities WHERE detected_at < ? AND outcome IS NULL",
            (cutoff,)
        )
        
        rows = cursor.fetchall()
        logger.info(f"Found {len(rows)} opportunities pending outcome evaluation.")
        
        for row in rows:
            opp_id = row["id"]
            market_id = row["market_id"]
            detected_at = datetime.fromisoformat(row["detected_at"])
            roi = row["expected_return_pct"]
            
            # Evaluate 5m and 30m windows
            outcome_5m = evaluate_signal_outcome(market_id, detected_at, roi, 5)
            outcome_30m = evaluate_signal_outcome(market_id, detected_at, roi, 30)
            
            outcome_data = {
                "window_5m": outcome_5m,
                "window_30m": outcome_30m,
                "summary": outcome_5m["reason"] if outcome_5m["classification"] != "unknown" else outcome_30m["reason"]
            }
            
            cursor.execute(
                "UPDATE opportunities SET outcome = ? WHERE id = ?",
                (json.dumps(outcome_data), opp_id)
            )
            
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error updating outcomes: {e}", exc_info=True)
