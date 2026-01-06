"""
Price alert functionality for Polymarket markets.

Implements functions to watch selected markets and trigger alerts when
price crosses user-defined thresholds. Returns alert objects without
sending notifications.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, Literal
from app.core.logger import logger


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

    if direction not in ["above", "below"]:
        raise ValueError("direction must be 'above' or 'below'")

    if not isinstance(target_price, (int, float)):
        raise ValueError("target_price must be a number")

    if target_price < 0 or target_price > 1:
        raise ValueError("target_price must be between 0 and 1")

    logger.info(
        f"Creating price alert for market {market_id}: "
        f"{direction} ${target_price:.4f}"
    )

    return PriceAlert(
        market_id=market_id,
        direction=direction,
        target_price=target_price,
        alert_message=f"Alert: Price {direction} ${target_price:.4f}",
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
            f"Alert triggered: Price ${current_price:.4f} is above "
            f"target ${alert.target_price:.4f}"
        )
        logger.info(
            f"Price alert triggered for market {alert.market_id}: "
            f"{alert.alert_message}"
        )
    elif alert.direction == "below" and current_price < alert.target_price:
        alert.triggered = True
        alert.triggered_at = datetime.now()
        alert.alert_message = (
            f"Alert triggered: Price ${current_price:.4f} is below "
            f"target ${alert.target_price:.4f}"
        )
        logger.info(
            f"Price alert triggered for market {alert.market_id}: "
            f"{alert.alert_message}"
        )
    else:
        alert.triggered = False
        alert.triggered_at = None
        alert.alert_message = (
            f"Alert not triggered: Price ${current_price:.4f} is "
            f"{'below' if alert.direction == 'above' else 'above'} "
            f"target ${alert.target_price:.4f}"
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

    if not outcomes:
        raise ValueError("market_data must contain at least one outcome")

    if len(outcomes) < 1:
        raise ValueError("market_data must contain at least one outcome with price")

    # Get the first outcome's price (typically "Yes" in binary markets)
    first_outcome = outcomes[0]
    current_price = first_outcome.get("price")

    if current_price is None:
        raise ValueError("outcome must contain a 'price' field")

    # Check the alert
    return check_price_alert(alert, current_price)
