"""
Notification service for the Polymarket Arbitrage Spotter.
Handles outbound delivery via Telegram and Email.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional, Union, List
from datetime import datetime

import requests

from app.core.config import get_config
from app.core.alert_service import AlertService

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Service for sending outbound notifications (Telegram/Email).
    """

    def __init__(self, config=None):
        self.config = config or get_config()
        self._last_notification_time: Dict[str, datetime] = {}
        self._alert_service = AlertService(self.config)

    def send_alert(self, alert_object: Dict[str, Any]) -> bool:
        """
        Send a notification alert.
        """
        # Trigger internal in-app alerting pipeline first
        self._alert_service.process_in_app_alert(alert_object)

        if not self.config.alert_method:
            return False

        # Throttling
        if not self._check_throttle(alert_object):
            return False

        message = self._format_alert_message(alert_object)
        subject = self._format_alert_subject(alert_object)

        success = False
        if self.config.alert_method == "telegram":
            success = self._send_telegram(message)
        elif self.config.alert_method == "email":
            success = self._send_email(subject, message)

        if success:
            self._update_throttle(alert_object)
            logger.info(f"Alert sent via {self.config.alert_method}")

        return success

    def _check_throttle(self, alert_object: Dict[str, Any]) -> bool:
        throttle_key = alert_object.get("market_id") or alert_object.get("market_name", "default")
        if throttle_key not in self._last_notification_time:
            return True
        last_time = self._last_notification_time[throttle_key]
        elapsed = (datetime.now() - last_time).total_seconds()
        return elapsed >= self.config.notification_throttle_seconds

    def _update_throttle(self, alert_object: Dict[str, Any]) -> None:
        throttle_key = alert_object.get("market_id") or alert_object.get("market_name", "default")
        self._last_notification_time[throttle_key] = datetime.now()

    def _format_alert_subject(self, alert_object: Dict[str, Any]) -> str:
        market_name = alert_object.get("market_name", "Unknown Market")
        profit = alert_object.get("expected_profit_pct", 0.0)
        return f"🚨 Arbitrage Alert: {market_name} ({profit:.2f}% profit)"

    def _format_alert_message(self, alert_object: Dict[str, Any]) -> str:
        market_name = alert_object.get("market_name", "Unknown Market")
        profit = alert_object.get("expected_profit_pct", 0.0)
        prices = alert_object.get("prices", {})
        yes_price = prices.get("yes_price", 0.0)
        no_price = prices.get("no_price", 0.0)
        sum_price = alert_object.get("sum_price", yes_price + no_price)
        timestamp = alert_object.get("timestamp", datetime.now().isoformat())

        return f"""🚨 Arbitrage Opportunity Detected!

Market: {market_name}
Expected Profit: {profit:.2f}%

Prices:
- Yes: ${yes_price:.4f}
- No: ${no_price:.4f}
- Sum: ${sum_price:.4f}

Timestamp: {timestamp}
"""

    def _send_telegram(self, message: str) -> bool:
        if not self.config.telegram_api_key or not self.config.telegram_chat_id:
            return False
        try:
            url = f"https://api.telegram.org/bot{self.config.telegram_api_key}/sendMessage"
            payload = {"chat_id": self.config.telegram_chat_id, "text": message, "parse_mode": "HTML"}
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Telegram error: {e}")
            return False

    def _send_email(self, subject: str, body: str) -> bool:
        if not self.config.email_smtp_server or not all([self.config.email_username, self.config.email_password]):
            return False
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.config.email_from
            msg["To"] = self.config.email_to
            msg.attach(MIMEText(body, "plain"))
            with smtplib.SMTP(self.config.email_smtp_server, self.config.email_smtp_port) as server:
                server.starttls()
                server.login(self.config.email_username, self.config.email_password)
                server.send_message(msg)
            return True
        except Exception as e:
            logger.error(f"Email error: {e}")
            return False

    # Proxy methods for backward compatibility
    def get_unread_alerts_count(self) -> int:
        return self._alert_service.get_unread_alerts_count()

    def get_recent_alerts(self, limit: int = 50, mode: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._alert_service.get_recent_alerts(limit, mode)

    def mark_all_as_seen(self):
        self._alert_service.mark_all_as_seen()

    def clear_all_alerts(self):
        self._alert_service.clear_all_alerts()

# Global singleton
_notification_service = None

def get_notification_service() -> NotificationService:
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service

def send_alert(alert_object: Dict[str, Any]) -> bool:
    return get_notification_service().send_alert(alert_object)
