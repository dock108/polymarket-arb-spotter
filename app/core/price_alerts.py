"""
Price alert functionality for Polymarket markets.

Implements functions to watch selected markets and trigger alerts when
price crosses user-defined thresholds. Returns alert objects without
sending notifications. Includes persistent JSON storage for alerts.
"""

import json
import os
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, Literal, List, Callable
from app.core.logger import logger


# Default storage path for price alerts
ALERTS_STORAGE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "price_alerts.json",
)


@dataclass
class PriceAlert:
    """
    Represents a price alert configuration and result.

    Attributes:
        market_id: Unique identifier for the market
        direction: Alert direction - "above" or "below"
        target_price: Price threshold that triggers the alert
        current_price: Current market price at time of check
        triggered: Whether the alert condition has been met
        triggered_at: Timestamp when alert was triggered (if triggered)
        alert_message: Human-readable description of the alert
    """

    market_id: str
    direction: Literal["above", "below"]
    target_price: float
    current_price: Optional[float] = None
    triggered: bool = False
    triggered_at: Optional[datetime] = None
    alert_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary representation."""
        return {
            "market_id": self.market_id,
            "direction": self.direction,
            "target_price": self.target_price,
            "current_price": self.current_price,
            "triggered": self.triggered,
            "triggered_at": (
                self.triggered_at.isoformat() if self.triggered_at else None
            ),
            "alert_message": self.alert_message,
        }


def create_price_alert(
    market_id: str,
    direction: Literal["above", "below"],
    target_price: float,
) -> PriceAlert:
    """
    Create a new price alert configuration.

    Args:
        market_id: Unique identifier for the market to watch
        direction: Alert direction - "above" triggers when price goes above target,
                   "below" triggers when price goes below target
        target_price: Price threshold that triggers the alert (must be between 0 and 1)

    Returns:
        PriceAlert object with the specified configuration

    Raises:
        ValueError: If inputs are invalid
    """
    # Validate inputs
    if not market_id or not isinstance(market_id, str):
        raise ValueError("market_id must be a non-empty string")

    if not market_id.strip():
        raise ValueError("market_id cannot be only whitespace")

    if direction not in ["above", "below"]:
        raise ValueError("direction must be 'above' or 'below'")

    if not isinstance(target_price, (int, float)):
        raise ValueError("target_price must be a number")

    if target_price < 0 or target_price > 1:
        raise ValueError("target_price must be between 0 and 1")

    logger.info(
        f"Creating price alert for market {market_id}: "
        f"{direction} {target_price:.4f}"
    )

    return PriceAlert(
        market_id=market_id,
        direction=direction,
        target_price=target_price,
        alert_message=f"Alert: Price {direction} {target_price:.4f}",
    )


def check_price_alert(alert: PriceAlert, current_price: float) -> PriceAlert:
    """
    Check if a price alert should be triggered based on current price.

    Updates the alert object with current price, triggered status,
    and timestamp if the condition is met.

    Args:
        alert: PriceAlert object to check
        current_price: Current market price to evaluate

    Returns:
        Updated PriceAlert object with triggered status and timestamp

    Raises:
        ValueError: If current_price is invalid
    """
    if not isinstance(current_price, (int, float)):
        raise ValueError("current_price must be a number")

    if current_price < 0 or current_price > 1:
        raise ValueError("current_price must be between 0 and 1")

    # Update current price
    alert.current_price = current_price

    # Check if alert condition is met
    if alert.direction == "above" and current_price > alert.target_price:
        alert.triggered = True
        alert.triggered_at = datetime.now()
        alert.alert_message = (
            f"Alert triggered: Price {current_price:.4f} is above "
            f"target {alert.target_price:.4f}"
        )
        logger.info(
            f"Price alert triggered for market {alert.market_id}: "
            f"{alert.alert_message}"
        )
    elif alert.direction == "below" and current_price < alert.target_price:
        alert.triggered = True
        alert.triggered_at = datetime.now()
        alert.alert_message = (
            f"Alert triggered: Price {current_price:.4f} is below "
            f"target {alert.target_price:.4f}"
        )
        logger.info(
            f"Price alert triggered for market {alert.market_id}: "
            f"{alert.alert_message}"
        )
    else:
        alert.triggered = False
        alert.triggered_at = None
        alert.alert_message = (
            f"Alert not triggered: Price {current_price:.4f} is "
            f"{'below' if alert.direction == 'above' else 'above'} "
            f"target {alert.target_price:.4f}"
        )

    return alert


def watch_market_price(
    market_id: str,
    direction: Literal["above", "below"],
    target_price: float,
    market_data: Dict[str, Any],
) -> PriceAlert:
    """
    Watch a market and trigger alert if price crosses threshold.

    This is a convenience function that combines create_price_alert
    and check_price_alert into a single operation.

    Args:
        market_id: Unique identifier for the market
        direction: Alert direction - "above" or "below"
        target_price: Price threshold that triggers the alert
        market_data: Market data dictionary containing price information
                     Expected format: {"outcomes": [{"price": float, ...}, ...]}

    Returns:
        PriceAlert object with triggered status

    Raises:
        ValueError: If inputs are invalid or market_data is malformed
    """
    # Create the alert
    alert = create_price_alert(market_id, direction, target_price)

    # Extract price from market data
    # For binary markets, use the first outcome's price
    outcomes = market_data.get("outcomes", [])

    if not outcomes or len(outcomes) < 1:
        raise ValueError("market_data must contain at least one outcome with price")

    # Get the first outcome's price (typically "Yes" in binary markets)
    first_outcome = outcomes[0]
    current_price = first_outcome.get("price")

    if current_price is None:
        raise ValueError("outcome must contain a 'price' field")

    # Check the alert
    return check_price_alert(alert, current_price)


# ============================================================================
# Persistent Storage Functions
# ============================================================================


def _validate_market_id_format(market_id: str) -> None:
    """
    Validate market_id format.

    Market IDs should be non-empty strings. This function can be extended
    to enforce more specific format requirements if needed.

    Args:
        market_id: Market ID to validate

    Raises:
        ValueError: If market_id format is invalid
    """
    if not market_id or not isinstance(market_id, str):
        raise ValueError("market_id must be a non-empty string")

    if not market_id.strip():
        raise ValueError("market_id cannot be only whitespace")


def _load_alerts(storage_path: str = ALERTS_STORAGE_PATH) -> Dict[str, Dict[str, Any]]:
    """
    Load alerts from JSON file.

    Args:
        storage_path: Path to JSON storage file

    Returns:
        Dictionary mapping alert IDs to alert data
    """
    # Ensure data directory exists
    os.makedirs(os.path.dirname(storage_path), exist_ok=True)

    # Create file if it doesn't exist
    if not os.path.exists(storage_path):
        logger.info(f"Creating new alerts storage file at {storage_path}")
        _save_alerts({}, storage_path)
        return {}

    try:
        with open(storage_path, "r") as f:
            alerts = json.load(f)
            logger.debug(f"Loaded {len(alerts)} alerts from {storage_path}")
            return alerts
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {storage_path}: {e}")
        # Backup corrupted file and create new one
        backup_path = f"{storage_path}.backup"
        os.rename(storage_path, backup_path)
        logger.warning(f"Corrupted file backed up to {backup_path}")
        return {}
    except Exception as e:
        logger.error(f"Error loading alerts from {storage_path}: {e}")
        return {}


def _save_alerts(
    alerts: Dict[str, Dict[str, Any]], storage_path: str = ALERTS_STORAGE_PATH
) -> None:
    """
    Save alerts to JSON file.

    Args:
        alerts: Dictionary mapping alert IDs to alert data
        storage_path: Path to JSON storage file
    """
    # Ensure data directory exists
    os.makedirs(os.path.dirname(storage_path), exist_ok=True)

    try:
        with open(storage_path, "w") as f:
            json.dump(alerts, f, indent=2)
            logger.debug(f"Saved {len(alerts)} alerts to {storage_path}")
    except Exception as e:
        logger.error(f"Error saving alerts to {storage_path}: {e}")
        raise


def add_alert(
    market_id: str,
    direction: Literal["above", "below"],
    target_price: float,
    alert_id: Optional[str] = None,
    storage_path: str = ALERTS_STORAGE_PATH,
) -> str:
    """
    Add a price alert to persistent storage.

    Args:
        market_id: Unique identifier for the market
        direction: Alert direction - "above" or "below"
        target_price: Price threshold that triggers the alert (0-1)
        alert_id: Optional custom alert ID. If not provided, generates one
        storage_path: Path to JSON storage file

    Returns:
        Alert ID (string) of the added alert

    Raises:
        ValueError: If inputs are invalid or alert_id already exists
    """
    # Validate inputs using existing validation in create_price_alert
    _ = create_price_alert(market_id, direction, target_price)

    # Generate alert ID if not provided
    if alert_id is None:
        alert_id = str(uuid.uuid4())

    # Load existing alerts
    alerts = _load_alerts(storage_path)

    # Check if alert_id already exists
    if alert_id in alerts:
        raise ValueError(f"Alert with ID '{alert_id}' already exists")

    # Store alert data
    alert_data = {
        "id": alert_id,
        "market_id": market_id,
        "direction": direction,
        "target_price": target_price,
        "created_at": datetime.now().isoformat(),
    }

    alerts[alert_id] = alert_data
    _save_alerts(alerts, storage_path)

    logger.info(
        f"Added price alert {alert_id} for market {market_id}: "
        f"{direction} {target_price:.4f}"
    )

    return alert_id


def remove_alert(
    alert_id: str,
    storage_path: str = ALERTS_STORAGE_PATH,
) -> bool:
    """
    Remove a price alert from persistent storage.

    Args:
        alert_id: ID of the alert to remove
        storage_path: Path to JSON storage file

    Returns:
        True if alert was removed, False if alert was not found
    """
    alerts = _load_alerts(storage_path)

    if alert_id not in alerts:
        logger.warning(f"Alert {alert_id} not found for removal")
        return False

    removed_alert = alerts.pop(alert_id)
    _save_alerts(alerts, storage_path)

    logger.info(
        f"Removed price alert {alert_id} for market " f"{removed_alert['market_id']}"
    )

    return True


def list_alerts(
    storage_path: str = ALERTS_STORAGE_PATH,
) -> List[Dict[str, Any]]:
    """
    List all price alerts from persistent storage.

    Args:
        storage_path: Path to JSON storage file

    Returns:
        List of alert dictionaries, sorted by creation time (newest first)
    """
    alerts = _load_alerts(storage_path)

    # Convert to list and sort by created_at
    alert_list = list(alerts.values())
    alert_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    logger.debug(f"Listed {len(alert_list)} alerts")

    return alert_list


# ============================================================================
# Price Alert Watcher
# ============================================================================


class PriceAlertWatcher:
    """
    Watches markets and triggers price alerts based on configured thresholds.

    This watcher subscribes to real-time price updates via WebSocket and
    monitors markets that have active alerts. When a price crosses a threshold,
    it fires the alert and tracks the last trigger time to prevent duplicates.

    Attributes:
        api_client: PolymarketAPIClient instance for fetching prices
        storage_path: Path to JSON file storing alerts
        alert_cooldown: Minimum time between duplicate alerts (seconds)
        on_alert_triggered: Optional callback when alert triggers
    """

    def __init__(
        self,
        api_client: Any,  # PolymarketAPIClient
        storage_path: str = ALERTS_STORAGE_PATH,
        alert_cooldown: float = 300.0,  # 5 minutes default
        on_alert_triggered: Optional[Callable[[PriceAlert], None]] = None,
    ):
        """
        Initialize the price alert watcher.

        Args:
            api_client: PolymarketAPIClient instance for WebSocket subscriptions
            storage_path: Path to JSON file storing alerts
            alert_cooldown: Minimum seconds between duplicate alerts (default: 300)
            on_alert_triggered: Optional callback function(alert) when alert triggers
        """
        self.api_client = api_client
        self.storage_path = storage_path
        self.alert_cooldown = alert_cooldown
        self.on_alert_triggered = on_alert_triggered

        # Track last trigger time for each alert to prevent duplicates
        self._last_trigger_times: Dict[str, datetime] = {}

        # Thread control
        self._running = False
        self._watch_thread: Optional[threading.Thread] = None

        logger.info(f"PriceAlertWatcher initialized with {alert_cooldown}s cooldown")

    def start(self) -> None:
        """
        Start watching markets with active alerts.

        Loads alerts from storage, subscribes to relevant markets via WebSocket,
        and begins monitoring prices in a background thread.
        """
        if self._running:
            logger.warning("PriceAlertWatcher is already running")
            return

        # Load alerts to determine which markets to watch
        alerts = list_alerts(self.storage_path)

        if not alerts:
            logger.info("No alerts to watch, starting with empty watch list")

        # Extract unique market IDs from alerts
        market_ids = list(set(alert["market_id"] for alert in alerts))

        if not market_ids:
            logger.warning("No market IDs found in alerts")
            return

        logger.info(f"Starting watcher for {len(market_ids)} markets")

        # Start the watch thread
        self._running = True
        self._watch_thread = threading.Thread(
            target=self._watch_loop,
            args=(market_ids,),
            daemon=True,
        )
        self._watch_thread.start()

        logger.info("PriceAlertWatcher started successfully")

    def stop(self) -> None:
        """
        Stop watching markets and clean up resources.
        """
        if not self._running:
            logger.warning("PriceAlertWatcher is not running")
            return

        logger.info("Stopping PriceAlertWatcher...")
        self._running = False

        # Stop WebSocket connection
        try:
            self.api_client.stop_websocket()
        except Exception as e:
            logger.warning(f"Error stopping WebSocket: {e}")

        # Wait for thread to finish
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=5.0)

        logger.info("PriceAlertWatcher stopped")

    def _watch_loop(self, market_ids: List[str]) -> None:
        """
        Main watch loop that subscribes to markets and processes price updates.

        Args:
            market_ids: List of market IDs to watch
        """
        try:
            self.api_client.subscribe_to_markets(
                market_ids=market_ids,
                on_price_update=self._handle_price_update,
                on_error=self._handle_error,
            )
        except Exception as e:
            logger.error(f"Error in watch loop: {e}")
            self._running = False

    def _handle_price_update(
        self,
        market_id: str,
        orderbook: Any,  # NormalizedOrderBook
    ) -> None:
        """
        Handle a price update for a market.

        Checks all alerts for this market and triggers those whose
        conditions are met, respecting the cooldown period.

        Args:
            market_id: Market identifier
            orderbook: NormalizedOrderBook with latest prices
        """
        if not self._running:
            return

        # Load current alerts for this market
        all_alerts = list_alerts(self.storage_path)
        market_alerts = [
            alert for alert in all_alerts if alert["market_id"] == market_id
        ]

        if not market_alerts:
            return

        # Use yes_best_ask as the current price (most conservative for YES)
        # Could also use yes_best_bid or midpoint depending on requirements
        current_price = orderbook.yes_best_ask

        if current_price is None:
            logger.debug(f"No price available for market {market_id}")
            return

        logger.debug(f"Price update for {market_id}: {current_price:.4f}")

        # Check each alert
        for alert_data in market_alerts:
            alert_id = alert_data["id"]
            direction = alert_data["direction"]
            target_price = alert_data["target_price"]

            # Create PriceAlert object
            alert = create_price_alert(
                market_id=market_id,
                direction=direction,
                target_price=target_price,
            )

            # Check if alert should trigger
            result = check_price_alert(alert, current_price)

            if result.triggered:
                # Check cooldown to prevent duplicate alerts
                if self._should_fire_alert(alert_id):
                    self._fire_alert(alert_id, result)

    def _should_fire_alert(self, alert_id: str) -> bool:
        """
        Check if enough time has passed since last trigger to fire alert again.

        Args:
            alert_id: Alert identifier

        Returns:
            True if alert should be fired, False if still in cooldown
        """
        now = datetime.now()
        last_trigger = self._last_trigger_times.get(alert_id)

        if last_trigger is None:
            return True

        time_since_last = (now - last_trigger).total_seconds()
        return time_since_last >= self.alert_cooldown

    def _fire_alert(self, alert_id: str, alert: PriceAlert) -> None:
        """
        Fire an alert by logging it and calling the callback.

        Args:
            alert_id: Alert identifier
            alert: PriceAlert object with triggered status
        """
        # Update last trigger time
        self._last_trigger_times[alert_id] = datetime.now()

        logger.info(f"ALERT FIRED [{alert_id}]: {alert.alert_message}")

        # Call callback if provided
        if self.on_alert_triggered:
            try:
                self.on_alert_triggered(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

    def _handle_error(self, error: Exception) -> None:
        """
        Handle errors from WebSocket connection.

        Args:
            error: Exception that occurred
        """
        logger.error(f"WebSocket error in PriceAlertWatcher: {error}")

    def is_running(self) -> bool:
        """
        Check if the watcher is currently running.

        Returns:
            True if watcher is running, False otherwise
        """
        return self._running

    def reload_alerts(self) -> None:
        """
        Reload alerts from storage and update subscriptions.

        This can be called to pick up new alerts without restarting the watcher.
        Note: Currently requires a restart to change subscriptions.
        """
        logger.info("Reloading alerts (restart required to update subscriptions)")
        # For now, just log. Full implementation would require dynamic
        # subscription management in the WebSocket connection.
