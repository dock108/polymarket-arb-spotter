"""
Background watcher for price alerts.
Periodically checks market prices and triggers configured alerts.
"""

import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from app.core.logger import logger
from app.core.price_alerts import PriceAlert, load_price_alerts, save_price_alerts

class PriceAlertWatcher:
    """
    Background watcher that monitors markets for price alert triggers.
    """

    def __init__(
        self,
        data_source: Any,
        check_interval: int = 60,
        on_alert: Optional[Callable[[PriceAlert], None]] = None,
    ):
        """
        Initialize the price alert watcher.

        Args:
            data_source: DataSource instance to fetch prices from
            check_interval: Interval in seconds between checks
            on_alert: Optional callback function called when an alert triggers
        """
        self.data_source = data_source
        self.check_interval = check_interval
        self.on_alert = on_alert
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        """Start the background watcher thread."""
        if self._running: return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"PriceAlertWatcher started (interval: {self.check_interval}s)")

    def stop(self) -> None:
        """Stop the background watcher thread."""
        if not self._running: return
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self.check_interval + 1)
            self._thread = None
        logger.info("PriceAlertWatcher stopped")

    def _run(self) -> None:
        """Main watcher loop."""
        while self._running and not self._stop_event.is_set():
            try:
                self._check_alerts()
            except Exception as e:
                logger.error(f"Error in PriceAlertWatcher loop: {e}")
            self._stop_event.wait(timeout=self.check_interval)

    def _check_alerts(self) -> None:
        """Fetch current prices and evaluate all active alerts."""
        alerts = load_price_alerts()
        active_alerts = [a for a in alerts if not a.triggered]
        if not active_alerts: return

        # Group by market_id to minimize API calls
        market_ids = list(set(a.market_id for a in active_alerts))
        for m_id in market_ids:
            market = self.data_source.get_market_details(m_id)
            if not market: continue
            
            # Check all alerts for this market
            for alert in [a for a in active_alerts if a.market_id == m_id]:
                if self._evaluate_alert(alert, market.yes_price):
                    if self.on_alert:
                        try: self.on_alert(alert)
                        except Exception as e: logger.error(f"Alert callback error: {e}")
        
        save_price_alerts(alerts)

    def _evaluate_alert(self, alert: PriceAlert, current_price: float) -> bool:
        """Evaluate a single alert against the current price."""
        triggered = False
        if alert.direction == "above" and current_price >= alert.target_price:
            triggered = True
        elif alert.direction == "below" and current_price <= alert.target_price:
            triggered = True
            
        if triggered:
            alert.triggered = True
            alert.triggered_at = datetime.now()
            alert.current_price = current_price
            alert.alert_message = f"Price {alert.direction} {alert.target_price} (Current: {current_price:.4f})"
            logger.info(f"ALERT TRIGGERED: {alert.market_id} {alert.alert_message}")
            
        return triggered
