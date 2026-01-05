"""
Unit tests for configuration module.

Tests configuration loading from environment variables,
validation, default values, and error handling.
"""

import unittest
import os
from unittest.mock import patch
from app.core.config import Config, get_config


class TestConfig(unittest.TestCase):
    """Test configuration management."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = Config()
        self.assertIsNotNone(config.api_endpoint)
        self.assertIsNotNone(config.db_path)
        self.assertGreater(config.min_profit_threshold, 0)
        self.assertGreater(config.max_stake, 0)
        self.assertEqual(config.log_db_path, "data/arb_logs.sqlite")
        self.assertEqual(config.min_profit_percent, 1.0)
        self.assertEqual(config.fee_buffer_percent, 0.5)
    
    def test_config_validation(self):
        """Test configuration validation."""
        config = Config()
        self.assertTrue(config.validate())
    
    def test_invalid_profit_threshold(self):
        """Test validation with invalid profit threshold."""
        config = Config(min_profit_percent=-1.0)
        self.assertFalse(config.validate())
    
    def test_invalid_fee_buffer(self):
        """Test validation with invalid fee buffer."""
        config = Config(fee_buffer_percent=-0.5)
        self.assertFalse(config.validate())
    
    @patch.dict(os.environ, {
        "MIN_PROFIT_PERCENT": "2.5",
        "FEE_BUFFER_PERCENT": "1.0",
        "LOG_DB_PATH": "custom/path/logs.db",
        "ALERT_METHOD": "telegram",
        "TELEGRAM_API_KEY": "test_key_123"
    })
    def test_from_env_with_custom_values(self):
        """Test loading configuration from environment variables."""
        config = Config.from_env()
        self.assertEqual(config.min_profit_percent, 2.5)
        self.assertEqual(config.fee_buffer_percent, 1.0)
        self.assertEqual(config.log_db_path, "custom/path/logs.db")
        self.assertEqual(config.alert_method, "telegram")
        self.assertEqual(config.telegram_api_key, "test_key_123")
        # min_profit_threshold should be decimal form
        self.assertAlmostEqual(config.min_profit_threshold, 0.025)
    
    @patch.dict(os.environ, {
        "ALERT_METHOD": "email",
        "EMAIL_SMTP_SERVER": "smtp.example.com:587"
    })
    def test_from_env_email_alert(self):
        """Test email alert configuration."""
        config = Config.from_env()
        self.assertEqual(config.alert_method, "email")
        self.assertEqual(config.email_smtp_server, "smtp.example.com:587")
    
    @patch.dict(os.environ, {"ALERT_METHOD": "invalid_method"})
    def test_invalid_alert_method(self):
        """Test that invalid alert method is ignored."""
        config = Config.from_env()
        self.assertIsNone(config.alert_method)
    
    @patch.dict(os.environ, {}, clear=True)
    def test_from_env_defaults(self):
        """Test that from_env uses defaults when env vars not set."""
        config = Config.from_env()
        self.assertEqual(config.min_profit_percent, 1.0)
        self.assertEqual(config.fee_buffer_percent, 0.5)
        self.assertEqual(config.log_db_path, "data/arb_logs.sqlite")
        self.assertIsNone(config.alert_method)
    
    def test_get_config_helper(self):
        """Test get_config() helper function."""
        config = get_config()
        self.assertIsInstance(config, Config)
        self.assertIsNotNone(config.min_profit_percent)
    
    @patch.dict(os.environ, {
        "MIN_PROFIT_PERCENT": "5.0",
        "MAX_STAKE": "5000.0"
    })
    def test_numeric_env_vars(self):
        """Test that numeric environment variables are properly converted."""
        config = Config.from_env()
        self.assertEqual(config.min_profit_percent, 5.0)
        self.assertEqual(config.max_stake, 5000.0)
    
    def test_alert_validation_telegram(self):
        """Test validation warns when telegram configured without API key."""
        config = Config(alert_method="telegram", telegram_api_key=None)
        # Should still be valid but log warning
        self.assertTrue(config.validate())
    
    def test_alert_validation_email(self):
        """Test validation warns when email configured without SMTP server."""
        config = Config(alert_method="email", email_smtp_server=None)
        # Should still be valid but log warning
        self.assertTrue(config.validate())


if __name__ == '__main__':
    unittest.main()
