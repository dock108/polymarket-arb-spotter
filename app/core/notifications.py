"""
Notification service for the Polymarket Arbitrage Spotter.

Supports sending alerts via:
- Telegram bot (preferred default method)
- Email via SMTP (optional support)

Includes throttling to prevent notification spam and graceful handling
of missing credentials.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
from datetime import datetime

import requests

from app.core.config import get_config

# Setup logging
logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for sending notifications via email or Telegram.

    Features:
    - Supports Telegram bot and Email via SMTP
    - Graceful handling of missing credentials (logs instead of crashes)
    - Throttling to prevent notification spam
    """

    def __init__(self, config=None):
        """
        Initialize the notification service.

        Args:
            config: Optional Config object. If not provided, loads from global config.
        """
        self.config = config or get_config()
        self._last_notification_time: Dict[str, datetime] = {}

        # Log initialization status
        if self.config.alert_method:
            logger.info(
                f"NotificationService initialized with method: {self.config.alert_method}"
            )
        else:
            logger.info(
                "NotificationService initialized with no alert method configured"
            )

    def send_alert(self, alert_object: Dict[str, Any]) -> bool:
        """
        Send a notification alert.

        Args:
            alert_object: Dictionary containing alert information.
                Expected keys:
                - market_name: Name of the market
                - expected_profit_pct: Expected profit percentage
                - prices: Dictionary with yes_price and no_price
                - sum_price: Sum of prices
                - timestamp: Alert timestamp
                Other keys may be included and will be included in the message.

        Returns:
            True if notification was sent successfully, False otherwise
        """
        if not self.config.alert_method:
            logger.debug("No alert method configured, skipping notification")
            return False

        # Check throttling
        if not self._check_throttle(alert_object):
            logger.debug("Notification throttled")
            return False

        # Format the alert message
        message = self._format_alert_message(alert_object)
        subject = self._format_alert_subject(alert_object)

        # Send via configured method
        success = False
        if self.config.alert_method == "telegram":
            success = self._send_telegram(message)
        elif self.config.alert_method == "email":
            success = self._send_email(subject, message)

        if success:
            # Update last notification time
            self._update_throttle(alert_object)
            logger.info(f"Alert sent successfully via {self.config.alert_method}")

        return success

    def _check_throttle(self, alert_object: Dict[str, Any]) -> bool:
        """
        Check if notification should be throttled.

        Args:
            alert_object: Alert information

        Returns:
            True if notification should be sent, False if throttled
        """
        # Use market_id or market_name as throttle key
        throttle_key = alert_object.get("market_id") or alert_object.get(
            "market_name", "default"
        )

        if throttle_key not in self._last_notification_time:
            return True

        last_time = self._last_notification_time[throttle_key]
        elapsed = (datetime.now() - last_time).total_seconds()

        return elapsed >= self.config.notification_throttle_seconds

    def _update_throttle(self, alert_object: Dict[str, Any]) -> None:
        """
        Update the last notification time for throttling.

        Args:
            alert_object: Alert information
        """
        throttle_key = alert_object.get("market_id") or alert_object.get(
            "market_name", "default"
        )
        self._last_notification_time[throttle_key] = datetime.now()

    def _format_alert_subject(self, alert_object: Dict[str, Any]) -> str:
        """
        Format the alert subject line.

        Args:
            alert_object: Alert information

        Returns:
            Formatted subject string
        """
        market_name = alert_object.get("market_name", "Unknown Market")
        profit = alert_object.get("expected_profit_pct", 0.0)
        return f"🚨 Arbitrage Alert: {market_name} ({profit:.2f}% profit)"

    def _format_alert_message(self, alert_object: Dict[str, Any]) -> str:
        """
        Format the alert message body.

        Args:
            alert_object: Alert information

        Returns:
            Formatted message string
        """
        market_name = alert_object.get("market_name", "Unknown Market")
        profit = alert_object.get("expected_profit_pct", 0.0)
        prices = alert_object.get("prices", {})
        yes_price = prices.get("yes_price", 0.0)
        no_price = prices.get("no_price", 0.0)
        sum_price = alert_object.get("sum_price", yes_price + no_price)
        timestamp = alert_object.get("timestamp", datetime.now().isoformat())

        message = f"""🚨 Arbitrage Opportunity Detected!

Market: {market_name}
Expected Profit: {profit:.2f}%

Prices:
- Yes: ${yes_price:.4f}
- No: ${no_price:.4f}
- Sum: ${sum_price:.4f}

Timestamp: {timestamp}

This is an automated alert from Polymarket Arbitrage Spotter.
"""

        # Add threshold information if available
        if "threshold" in alert_object:
            message += f"Threshold: ${alert_object['threshold']:.4f}\n"

        # Add profit margin if available
        if "profit_margin" in alert_object:
            message += f"Profit Margin: ${alert_object['profit_margin']:.4f}\n"

        return message

    def _send_telegram(self, message: str) -> bool:
        """
        Send a notification via Telegram.

        Args:
            message: Message to send

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.config.telegram_api_key:
            logger.warning("Telegram API key not configured, cannot send notification")
            return False

        if not self.config.telegram_chat_id:
            logger.warning("Telegram chat ID not configured, cannot send notification")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.config.telegram_api_key}/sendMessage"
            payload = {
                "chat_id": self.config.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML",
            }

            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()

            logger.info("Telegram notification sent successfully")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Telegram notification: {e}")
            return False

    def _send_email(self, subject: str, body: str) -> bool:
        """
        Send a notification via email.

        Args:
            subject: Email subject
            body: Email body

        Returns:
            True if sent successfully, False otherwise
        """
        # Check for required email configuration
        if not self.config.email_smtp_server:
            logger.warning("Email SMTP server not configured, cannot send notification")
            return False

        if not all(
            [
                self.config.email_username,
                self.config.email_password,
                self.config.email_from,
                self.config.email_to,
            ]
        ):
            logger.warning("Email credentials incomplete, cannot send notification")
            return False

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.config.email_from
            msg["To"] = self.config.email_to

            # Add body
            text_part = MIMEText(body, "plain")
            msg.attach(text_part)

            # Connect to SMTP server
            with smtplib.SMTP(
                self.config.email_smtp_server, self.config.email_smtp_port
            ) as server:
                server.starttls()
                server.login(self.config.email_username, self.config.email_password)
                server.send_message(msg)

            logger.info("Email notification sent successfully")
            return True

        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email notification: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email notification: {e}")
            return False


# Global notification service instance
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """
    Get the global notification service instance.

    Returns:
        NotificationService instance
    """
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


def _reset_notification_service() -> None:
    """
    Reset the global notification service instance.

    This is primarily for testing purposes.
    """
    global _notification_service
    _notification_service = None


def send_alert(alert_object: Dict[str, Any]) -> bool:
    """
    Send a notification alert using the global notification service.

    This is a convenience function that uses the global notification service instance.

    Args:
        alert_object: Dictionary containing alert information.
            Expected keys:
            - market_name: Name of the market
            - expected_profit_pct: Expected profit percentage
            - prices: Dictionary with yes_price and no_price
            - sum_price: Sum of prices
            - timestamp: Alert timestamp

    Returns:
        True if notification was sent successfully, False otherwise
    """
    service = get_notification_service()
    return service.send_alert(alert_object)


def send_price_alert(alert: Any) -> bool:
    """
    Send a price alert notification using the global notification service.

    This function reuses the notification infrastructure to send alerts when
    market prices cross user-defined thresholds. It handles failures gracefully
    to prevent crashes in monitoring loops.

    Args:
        alert: PriceAlert object or dictionary containing alert information.
            Expected attributes/keys:
            - market_id: Market identifier
            - market_name (optional): Human-readable market name
            - current_price: Current market price
            - target_price: Threshold price that triggered the alert
            - direction: Alert direction ("above" or "below")
            - triggered_at: Timestamp when alert was triggered
            - alert_message (optional): Custom alert message

    Returns:
        True if notification was sent successfully, False otherwise.
        Always returns False (doesn't raise) if errors occur.

    Examples:
        >>> from app.core.price_alerts import PriceAlert
        >>> alert = PriceAlert(market_id="btc_100k", direction="above",
        ...                    target_price=0.65, current_price=0.70)
        >>> send_price_alert(alert)
    """
    try:
        # Handle both PriceAlert objects and dictionaries
        if hasattr(alert, "to_dict"):
            # It's a PriceAlert object
            alert_dict = alert.to_dict()
            market_id = alert.market_id
            market_name = getattr(alert, "market_name", None) or market_id
            current_price = alert.current_price
            target_price = alert.target_price
            direction = alert.direction
            triggered_at = alert.triggered_at
            alert_message = alert.alert_message
        else:
            # It's a dictionary
            alert_dict = alert
            market_id = alert_dict.get("market_id", "Unknown")
            market_name = alert_dict.get("market_name", market_id)
            current_price = alert_dict.get("current_price")
            target_price = alert_dict.get("target_price")
            direction = alert_dict.get("direction", "unknown")
            triggered_at = alert_dict.get("triggered_at")
            alert_message = alert_dict.get("alert_message", "")

        # Get the notification service
        service = get_notification_service()

        # Check if notifications are enabled
        if not service.config.alert_method:
            # Log instead of sending notification
            # Handle None values gracefully
            current_price_str = f"{current_price:.4f}" if current_price is not None else "N/A"
            target_price_str = f"{target_price:.4f}" if target_price is not None else "N/A"
            triggered_at_str = str(triggered_at) if triggered_at else "N/A"
            
            logger.info(
                f"Price alert triggered (notifications disabled): "
                f"{market_name} - Price {current_price_str} {direction} "
                f"threshold {target_price_str} at {triggered_at_str}"
            )
            return False

        # Format timestamp
        timestamp_str = triggered_at.isoformat() if triggered_at else datetime.now().isoformat()

        # Build notification payload
        notification_data = {
            "market_id": market_id,
            "market_name": market_name,
            "current_price": current_price,
            "target_price": target_price,
            "direction": direction,
            "timestamp": timestamp_str,
            "alert_message": alert_message,
        }

        # Format the message for price alerts
        message = _format_price_alert_message(notification_data)
        subject = _format_price_alert_subject(notification_data)

        # Send via configured method
        success = False
        if service.config.alert_method == "telegram":
            success = service._send_telegram(message)
        elif service.config.alert_method == "email":
            success = service._send_email(subject, message)

        if success:
            logger.info(
                f"Price alert sent successfully via {service.config.alert_method}: "
                f"{market_name} - {direction} {target_price:.4f}"
            )
        else:
            logger.warning(
                f"Failed to send price alert for {market_name} via "
                f"{service.config.alert_method}"
            )

        return success

    except Exception as e:
        # Gracefully handle any errors to prevent crashing the loop
        logger.error(f"Error sending price alert: {e}", exc_info=True)
        return False


def _format_price_alert_subject(alert_data: Dict[str, Any]) -> str:
    """
    Format the subject line for a price alert.

    Args:
        alert_data: Dictionary containing alert information

    Returns:
        Formatted subject string
    """
    market_name = alert_data.get("market_name", "Unknown Market")
    direction = alert_data.get("direction", "unknown")
    target_price = alert_data.get("target_price")
    current_price = alert_data.get("current_price")
    
    # Handle None values safely
    target_price_val = target_price if target_price is not None else 0.0
    current_price_val = current_price if current_price is not None else 0.0

    return (
        f"🔔 Price Alert: {market_name} "
        f"({current_price_val:.4f} {direction} {target_price_val:.4f})"
    )


def _format_price_alert_message(alert_data: Dict[str, Any]) -> str:
    """
    Format the message body for a price alert.

    Args:
        alert_data: Dictionary containing alert information

    Returns:
        Formatted message string
    """
    market_name = alert_data.get("market_name", "Unknown Market")
    market_id = alert_data.get("market_id", "unknown")
    current_price = alert_data.get("current_price")
    target_price = alert_data.get("target_price")
    direction = alert_data.get("direction", "unknown")
    timestamp = alert_data.get("timestamp", datetime.now().isoformat())
    alert_message = alert_data.get("alert_message", "")
    
    # Handle None values safely
    current_price_val = current_price if current_price is not None else 0.0
    target_price_val = target_price if target_price is not None else 0.0

    message = f"""🔔 Price Alert Triggered!

Market: {market_name}
Market ID: {market_id}

Current Price: ${current_price_val:.4f}
Threshold: ${target_price_val:.4f}
Direction: {direction.upper()}

Alert: Price moved {direction} threshold
{alert_message}

Timestamp: {timestamp}

This is an automated price alert from Polymarket Arbitrage Spotter.
"""

    return message
