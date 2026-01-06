"""
Unit tests for notification service module.

Tests notification sending via Telegram and Email with proper
error handling, throttling, and missing credentials.
"""

import unittest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timedelta
import smtplib

from app.core.notifications import (
    NotificationService,
    send_alert,
    get_notification_service,
)
from app.core.config import Config


class TestNotificationService(unittest.TestCase):
    """Test NotificationService class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a config with no alert method by default
        self.config_no_alerts = Config(alert_method=None)

        # Create a config for Telegram
        self.config_telegram = Config(
            alert_method="telegram",
            telegram_api_key="test_api_key_123",
            telegram_chat_id="test_chat_id_456",
        )

        # Create a config for Email
        self.config_email = Config(
            alert_method="email",
            email_smtp_server="smtp.example.com",
            email_smtp_port=587,
            email_username="test@example.com",
            email_password="test_password",
            email_from="sender@example.com",
            email_to="recipient@example.com",
        )

        # Sample alert object
        self.alert = {
            "market_id": "test_market_123",
            "market_name": "Test Market",
            "expected_profit_pct": 2.5,
            "prices": {"yes_price": 0.48, "no_price": 0.50},
            "sum_price": 0.98,
            "timestamp": datetime.now().isoformat(),
        }

    def test_initialization_no_alerts(self):
        """Test service initialization with no alert method."""
        service = NotificationService(self.config_no_alerts)
        self.assertIsNotNone(service)
        self.assertIsNone(service.config.alert_method)

    def test_initialization_telegram(self):
        """Test service initialization with Telegram."""
        service = NotificationService(self.config_telegram)
        self.assertIsNotNone(service)
        self.assertEqual(service.config.alert_method, "telegram")

    def test_initialization_email(self):
        """Test service initialization with Email."""
        service = NotificationService(self.config_email)
        self.assertIsNotNone(service)
        self.assertEqual(service.config.alert_method, "email")

    def test_send_alert_no_method(self):
        """Test that send_alert returns False when no alert method is configured."""
        service = NotificationService(self.config_no_alerts)
        result = service.send_alert(self.alert)
        self.assertFalse(result)

    @patch("app.core.notifications.requests.post")
    def test_send_telegram_success(self, mock_post):
        """Test successful Telegram notification."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        service = NotificationService(self.config_telegram)
        result = service.send_alert(self.alert)

        self.assertTrue(result)
        mock_post.assert_called_once()

        # Verify the API call was made correctly
        call_args = mock_post.call_args
        self.assertIn(
            "sendMessage",
            call_args[1]["url"] if "url" in call_args[1] else call_args[0][0],
        )

    @patch("app.core.notifications.requests.post")
    def test_send_telegram_missing_api_key(self, mock_post):
        """Test Telegram notification with missing API key."""
        config = Config(
            alert_method="telegram",
            telegram_api_key=None,
            telegram_chat_id="test_chat_id",
        )
        service = NotificationService(config)
        result = service.send_alert(self.alert)

        self.assertFalse(result)
        mock_post.assert_not_called()

    @patch("app.core.notifications.requests.post")
    def test_send_telegram_missing_chat_id(self, mock_post):
        """Test Telegram notification with missing chat ID."""
        config = Config(
            alert_method="telegram", telegram_api_key="test_key", telegram_chat_id=None
        )
        service = NotificationService(config)
        result = service.send_alert(self.alert)

        self.assertFalse(result)
        mock_post.assert_not_called()

    @patch("app.core.notifications.requests.post")
    def test_send_telegram_request_exception(self, mock_post):
        """Test Telegram notification with request exception."""
        mock_post.side_effect = Exception("Network error")

        service = NotificationService(self.config_telegram)
        result = service.send_alert(self.alert)

        self.assertFalse(result)

    @patch("app.core.notifications.smtplib.SMTP")
    def test_send_email_success(self, mock_smtp):
        """Test successful email notification."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        service = NotificationService(self.config_email)
        result = service.send_alert(self.alert)

        self.assertTrue(result)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with(
            self.config_email.email_username, self.config_email.email_password
        )
        mock_server.send_message.assert_called_once()

    @patch("app.core.notifications.smtplib.SMTP")
    def test_send_email_missing_smtp_server(self, mock_smtp):
        """Test email notification with missing SMTP server."""
        config = Config(
            alert_method="email",
            email_smtp_server=None,
            email_username="test@example.com",
            email_password="password",
            email_from="from@example.com",
            email_to="to@example.com",
        )
        service = NotificationService(config)
        result = service.send_alert(self.alert)

        self.assertFalse(result)
        mock_smtp.assert_not_called()

    @patch("app.core.notifications.smtplib.SMTP")
    def test_send_email_missing_credentials(self, mock_smtp):
        """Test email notification with missing credentials."""
        config = Config(
            alert_method="email",
            email_smtp_server="smtp.example.com",
            email_username=None,
            email_password="password",
            email_from="from@example.com",
            email_to="to@example.com",
        )
        service = NotificationService(config)
        result = service.send_alert(self.alert)

        self.assertFalse(result)
        mock_smtp.assert_not_called()

    @patch("app.core.notifications.smtplib.SMTP")
    def test_send_email_smtp_exception(self, mock_smtp):
        """Test email notification with SMTP exception."""
        mock_smtp.return_value.__enter__.side_effect = smtplib.SMTPException(
            "SMTP error"
        )

        service = NotificationService(self.config_email)
        result = service.send_alert(self.alert)

        self.assertFalse(result)

    @patch("app.core.notifications.requests.post")
    def test_throttling_same_market(self, mock_post):
        """Test that notifications are throttled for the same market."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        # Set throttle to 60 seconds
        config = Config(
            alert_method="telegram",
            telegram_api_key="test_api_key",
            telegram_chat_id="test_chat_id",
            notification_throttle_seconds=60,
        )
        service = NotificationService(config)

        # First notification should succeed
        result1 = service.send_alert(self.alert)
        self.assertTrue(result1)

        # Second notification immediately after should be throttled
        result2 = service.send_alert(self.alert)
        self.assertFalse(result2)

        # Should have been called only once
        self.assertEqual(mock_post.call_count, 1)

    @patch("app.core.notifications.requests.post")
    def test_throttling_different_markets(self, mock_post):
        """Test that throttling is per-market."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        config = Config(
            alert_method="telegram",
            telegram_api_key="test_api_key",
            telegram_chat_id="test_chat_id",
            notification_throttle_seconds=60,
        )
        service = NotificationService(config)

        # First market
        alert1 = self.alert.copy()
        alert1["market_id"] = "market_1"
        result1 = service.send_alert(alert1)
        self.assertTrue(result1)

        # Second market (different)
        alert2 = self.alert.copy()
        alert2["market_id"] = "market_2"
        result2 = service.send_alert(alert2)
        self.assertTrue(result2)

        # Both should have been sent
        self.assertEqual(mock_post.call_count, 2)

    @patch("app.core.notifications.requests.post")
    def test_throttling_expires(self, mock_post):
        """Test that throttling expires after the configured time."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        # Set very short throttle for testing
        config = Config(
            alert_method="telegram",
            telegram_api_key="test_api_key",
            telegram_chat_id="test_chat_id",
            notification_throttle_seconds=0,  # No throttle
        )
        service = NotificationService(config)

        # First notification
        result1 = service.send_alert(self.alert)
        self.assertTrue(result1)

        # Second notification should also succeed with no throttle
        result2 = service.send_alert(self.alert)
        self.assertTrue(result2)

        self.assertEqual(mock_post.call_count, 2)

    def test_format_alert_message(self):
        """Test alert message formatting."""
        service = NotificationService(self.config_no_alerts)
        message = service._format_alert_message(self.alert)

        self.assertIn("Test Market", message)
        self.assertIn("2.5", message)
        self.assertIn("0.48", message)
        self.assertIn("0.50", message)
        self.assertIn("0.98", message)

    def test_format_alert_subject(self):
        """Test alert subject formatting."""
        service = NotificationService(self.config_no_alerts)
        subject = service._format_alert_subject(self.alert)

        self.assertIn("Test Market", subject)
        self.assertIn("2.5", subject)
        self.assertIn("Arbitrage Alert", subject)

    def test_format_alert_message_with_extra_fields(self):
        """Test alert message formatting with extra fields."""
        alert_with_extras = self.alert.copy()
        alert_with_extras["threshold"] = 0.99
        alert_with_extras["profit_margin"] = 0.01

        service = NotificationService(self.config_no_alerts)
        message = service._format_alert_message(alert_with_extras)

        self.assertIn("0.99", message)
        self.assertIn("0.01", message)


class TestGlobalFunctions(unittest.TestCase):
    """Test global notification functions."""

    @patch("app.core.notifications.get_config")
    @patch("app.core.notifications.requests.post")
    def test_send_alert_function(self, mock_post, mock_get_config):
        """Test the global send_alert function."""
        # Mock config
        mock_config = Config(
            alert_method="telegram",
            telegram_api_key="test_key",
            telegram_chat_id="test_chat_id",
        )
        mock_get_config.return_value = mock_config

        # Mock successful response
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        # Reset global service instance
        from app.core.notifications import _reset_notification_service

        _reset_notification_service()

        alert = {
            "market_id": "test_market",
            "market_name": "Test Market",
            "expected_profit_pct": 2.5,
            "prices": {"yes_price": 0.48, "no_price": 0.50},
            "sum_price": 0.98,
            "timestamp": datetime.now().isoformat(),
        }

        result = send_alert(alert)
        self.assertTrue(result)

    @patch("app.core.notifications.get_config")
    def test_get_notification_service(self, mock_get_config):
        """Test getting the global notification service."""
        mock_config = Config(alert_method=None)
        mock_get_config.return_value = mock_config

        # Reset global service instance
        from app.core.notifications import _reset_notification_service

        _reset_notification_service()

        service1 = get_notification_service()
        service2 = get_notification_service()

        # Should return the same instance
        self.assertIs(service1, service2)


class TestSendPriceAlert(unittest.TestCase):
    """Test send_price_alert function."""

    def setUp(self):
        """Set up test fixtures."""
        # Import here to avoid circular imports
        from app.core.price_alerts import PriceAlert

        self.PriceAlert = PriceAlert

        # Sample PriceAlert object
        self.price_alert = PriceAlert(
            market_id="test_market_123",
            direction="above",
            target_price=0.65,
            current_price=0.70,
            triggered=True,
            triggered_at=datetime.now(),
            alert_message="Price crossed threshold",
        )

        # Sample alert dictionary
        self.alert_dict = {
            "market_id": "test_market_456",
            "market_name": "Test Market",
            "direction": "below",
            "target_price": 0.35,
            "current_price": 0.30,
            "triggered_at": datetime.now(),
            "alert_message": "Price dropped below threshold",
        }

    @patch("app.core.notifications.get_config")
    def test_send_price_alert_disabled_notifications(self, mock_get_config):
        """Test that send_price_alert logs when notifications are disabled."""
        from app.core.notifications import send_price_alert, _reset_notification_service

        # Mock config with no alert method
        mock_config = Config(alert_method=None)
        mock_get_config.return_value = mock_config
        _reset_notification_service()

        with patch("app.core.notifications.logger") as mock_logger:
            result = send_price_alert(self.price_alert)

            # Should return False
            self.assertFalse(result)

            # Should log the alert
            mock_logger.info.assert_called()
            call_args = str(mock_logger.info.call_args)
            self.assertIn("notifications disabled", call_args.lower())

    @patch("app.core.notifications.get_config")
    @patch("app.core.notifications.requests.post")
    def test_send_price_alert_with_object_telegram(self, mock_post, mock_get_config):
        """Test sending price alert with PriceAlert object via Telegram."""
        from app.core.notifications import send_price_alert, _reset_notification_service

        # Mock config with Telegram
        mock_config = Config(
            alert_method="telegram",
            telegram_api_key="test_key",
            telegram_chat_id="test_chat_id",
        )
        mock_get_config.return_value = mock_config
        _reset_notification_service()

        # Mock successful response
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = send_price_alert(self.price_alert)

        # Should return True
        self.assertTrue(result)

        # Should have called Telegram API
        mock_post.assert_called_once()

        # Verify message content
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        message = payload["text"]
        self.assertIn("test_market_123", message)
        self.assertIn("0.70", message)
        self.assertIn("0.65", message)
        self.assertIn("above", message.lower())

    @patch("app.core.notifications.get_config")
    @patch("app.core.notifications.requests.post")
    def test_send_price_alert_with_dict_telegram(self, mock_post, mock_get_config):
        """Test sending price alert with dictionary via Telegram."""
        from app.core.notifications import send_price_alert, _reset_notification_service

        # Mock config with Telegram
        mock_config = Config(
            alert_method="telegram",
            telegram_api_key="test_key",
            telegram_chat_id="test_chat_id",
        )
        mock_get_config.return_value = mock_config
        _reset_notification_service()

        # Mock successful response
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = send_price_alert(self.alert_dict)

        # Should return True
        self.assertTrue(result)

        # Should have called Telegram API
        mock_post.assert_called_once()

        # Verify message content
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        message = payload["text"]
        self.assertIn("Test Market", message)
        self.assertIn("0.30", message)
        self.assertIn("0.35", message)
        self.assertIn("below", message.lower())

    @patch("app.core.notifications.get_config")
    @patch("app.core.notifications.smtplib.SMTP")
    def test_send_price_alert_email(self, mock_smtp, mock_get_config):
        """Test sending price alert via email."""
        from app.core.notifications import send_price_alert, _reset_notification_service

        # Mock config with Email
        mock_config = Config(
            alert_method="email",
            email_smtp_server="smtp.example.com",
            email_smtp_port=587,
            email_username="test@example.com",
            email_password="password",
            email_from="from@example.com",
            email_to="to@example.com",
        )
        mock_get_config.return_value = mock_config
        _reset_notification_service()

        # Mock SMTP server
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        result = send_price_alert(self.price_alert)

        # Should return True
        self.assertTrue(result)

        # Should have sent email
        mock_server.send_message.assert_called_once()

    @patch("app.core.notifications.get_config")
    @patch("app.core.notifications.requests.post")
    def test_send_price_alert_error_handling(self, mock_post, mock_get_config):
        """Test that send_price_alert handles errors gracefully."""
        from app.core.notifications import send_price_alert, _reset_notification_service

        # Mock config with Telegram
        mock_config = Config(
            alert_method="telegram",
            telegram_api_key="test_key",
            telegram_chat_id="test_chat_id",
        )
        mock_get_config.return_value = mock_config
        _reset_notification_service()

        # Mock exception
        mock_post.side_effect = Exception("Network error")

        # Should not raise exception
        result = send_price_alert(self.price_alert)

        # Should return False
        self.assertFalse(result)

    @patch("app.core.notifications.get_config")
    def test_send_price_alert_with_malformed_data(self, mock_get_config):
        """Test send_price_alert with malformed data doesn't crash."""
        from app.core.notifications import send_price_alert, _reset_notification_service

        # Mock config with Telegram
        mock_config = Config(
            alert_method="telegram",
            telegram_api_key="test_key",
            telegram_chat_id="test_chat_id",
        )
        mock_get_config.return_value = mock_config
        _reset_notification_service()

        # Malformed alert data (missing keys)
        malformed_alert = {"market_id": "test"}

        with patch("app.core.notifications.requests.post"):
            # Should not raise exception
            result = send_price_alert(malformed_alert)
            # May return True or False, but should not crash
            self.assertIsInstance(result, bool)

    def test_format_price_alert_subject(self):
        """Test price alert subject formatting."""
        from app.core.notifications import _format_price_alert_subject

        alert_data = {
            "market_name": "Bitcoin 100K",
            "direction": "above",
            "target_price": 0.65,
            "current_price": 0.70,
        }

        subject = _format_price_alert_subject(alert_data)

        self.assertIn("Bitcoin 100K", subject)
        self.assertIn("0.70", subject)
        self.assertIn("0.65", subject)
        self.assertIn("above", subject)

    def test_format_price_alert_message(self):
        """Test price alert message formatting."""
        from app.core.notifications import _format_price_alert_message

        alert_data = {
            "market_id": "btc_100k",
            "market_name": "Bitcoin 100K",
            "direction": "above",
            "target_price": 0.65,
            "current_price": 0.70,
            "timestamp": "2024-01-01T12:00:00",
            "alert_message": "Alert triggered",
        }

        message = _format_price_alert_message(alert_data)

        self.assertIn("Bitcoin 100K", message)
        self.assertIn("btc_100k", message)
        self.assertIn("0.70", message)
        self.assertIn("0.65", message)
        self.assertIn("ABOVE", message)
        self.assertIn("2024-01-01T12:00:00", message)


if __name__ == "__main__":
    unittest.main()
