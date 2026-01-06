"""
Configuration management for the Polymarket Arbitrage Spotter.

Loads configuration from environment variables using python-dotenv.
Supports critical settings like profit thresholds, fees, and alerting.
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional, Literal
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Setup basic logging for config module
_logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Configuration for the application."""

    # API Configuration
    api_endpoint: str = "https://api.polymarket.com"
    api_key: Optional[str] = None

    # Database Configuration
    db_path: str = "data/polymarket_arb.db"
    log_db_path: str = "data/arb_logs.sqlite"

    # Arbitrage Detection Configuration
    min_profit_threshold: float = 0.01  # 1% minimum profit
    min_profit_percent: float = 1.0  # 1% minimum profit (percentage form)
    fee_buffer_percent: float = 0.5  # 0.5% fee buffer
    max_stake: float = 1000.0  # Maximum stake per arbitrage

    # Alert Configuration
    alert_method: Optional[Literal["email", "telegram"]] = None
    telegram_api_key: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    email_smtp_server: Optional[str] = None
    email_smtp_port: int = 587
    email_username: Optional[str] = None
    email_password: Optional[str] = None
    email_from: Optional[str] = None
    email_to: Optional[str] = None
    notification_throttle_seconds: int = 300  # 5 minutes default

    # Logging Configuration
    log_level: str = "INFO"
    log_file: str = "data/polymarket_arb.log"

    @classmethod
    def from_env(cls) -> "Config":
        """
        Load configuration from environment variables.

        Environment variables supported:
        - MIN_PROFIT_PERCENT: Minimum profit percentage (default: 1.0)
        - FEE_BUFFER_PERCENT: Fee buffer percentage (default: 0.5)
        - ALERT_METHOD: Alert method - "email" or "telegram" (optional)
        - TELEGRAM_API_KEY: Telegram bot API key (optional)
        - TELEGRAM_CHAT_ID: Telegram chat ID (optional)
        - EMAIL_SMTP_SERVER: Email SMTP server (optional)
        - EMAIL_SMTP_PORT: Email SMTP port (default: 587)
        - EMAIL_USERNAME: Email username for authentication (optional)
        - EMAIL_PASSWORD: Email password for authentication (optional)
        - EMAIL_FROM: Email sender address (optional)
        - EMAIL_TO: Email recipient address (optional)
        - NOTIFICATION_THROTTLE_SECONDS: Seconds between notifications (default: 300)
        - LOG_DB_PATH: Path to log database (default: data/arb_logs.sqlite)
        - LOG_LEVEL: Logging level (default: INFO)
        - API_ENDPOINT: Polymarket API endpoint
        - API_KEY: Polymarket API key
        - DB_PATH: Main database path
        - MAX_STAKE: Maximum stake per arbitrage

        Returns:
            Config instance with values loaded from environment
        """
        # Load arbitrage detection parameters
        min_profit_percent = float(os.getenv("MIN_PROFIT_PERCENT", "1.0"))
        fee_buffer_percent = float(os.getenv("FEE_BUFFER_PERCENT", "0.5"))

        # Load alert configuration
        alert_method = os.getenv("ALERT_METHOD")
        if alert_method and alert_method.lower() not in ["email", "telegram"]:
            _logger.warning(
                f"Invalid ALERT_METHOD '{alert_method}'. Must be 'email' or 'telegram'. "
                "Alerts will be disabled."
            )
            alert_method = None
        elif alert_method:
            alert_method = alert_method.lower()

        telegram_api_key = os.getenv("TELEGRAM_API_KEY")
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        email_smtp_server = os.getenv("EMAIL_SMTP_SERVER")
        email_smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
        email_username = os.getenv("EMAIL_USERNAME")
        email_password = os.getenv("EMAIL_PASSWORD")
        email_from = os.getenv("EMAIL_FROM")
        email_to = os.getenv("EMAIL_TO")
        notification_throttle_seconds = int(
            os.getenv("NOTIFICATION_THROTTLE_SECONDS", "300")
        )

        # Load database path
        log_db_path = os.getenv("LOG_DB_PATH", "data/arb_logs.sqlite")

        # Load other configuration
        api_endpoint = os.getenv("API_ENDPOINT", "https://api.polymarket.com")
        api_key = os.getenv("API_KEY")
        db_path = os.getenv("DB_PATH", "data/polymarket_arb.db")
        log_level = os.getenv("LOG_LEVEL", "INFO")
        log_file = os.getenv("LOG_FILE", "data/polymarket_arb.log")
        max_stake = float(os.getenv("MAX_STAKE", "1000.0"))

        # Create config instance
        config = cls(
            api_endpoint=api_endpoint,
            api_key=api_key,
            db_path=db_path,
            log_db_path=log_db_path,
            min_profit_threshold=min_profit_percent / 100.0,  # Convert to decimal
            min_profit_percent=min_profit_percent,
            fee_buffer_percent=fee_buffer_percent,
            max_stake=max_stake,
            alert_method=alert_method,
            telegram_api_key=telegram_api_key,
            telegram_chat_id=telegram_chat_id,
            email_smtp_server=email_smtp_server,
            email_smtp_port=email_smtp_port,
            email_username=email_username,
            email_password=email_password,
            email_from=email_from,
            email_to=email_to,
            notification_throttle_seconds=notification_throttle_seconds,
            log_level=log_level,
            log_file=log_file,
        )

        # Validate and log configuration
        config.validate()

        return config

    def validate(self) -> bool:
        """
        Validate configuration values and log warnings for missing critical settings.

        Returns:
            True if configuration is valid (has minimum required settings)
        """
        is_valid = True

        # Validate profit thresholds
        if self.min_profit_percent <= 0:
            _logger.error(
                f"Invalid MIN_PROFIT_PERCENT: {self.min_profit_percent}. "
                "Must be greater than 0."
            )
            is_valid = False

        if self.fee_buffer_percent < 0:
            _logger.error(
                f"Invalid FEE_BUFFER_PERCENT: {self.fee_buffer_percent}. "
                "Must be non-negative."
            )
            is_valid = False

        # Validate alert configuration
        if self.alert_method == "telegram" and not self.telegram_api_key:
            _logger.warning(
                "ALERT_METHOD is set to 'telegram' but TELEGRAM_API_KEY is not configured. "
                "Telegram alerts will not work."
            )

        if self.alert_method == "telegram" and not self.telegram_chat_id:
            _logger.warning(
                "ALERT_METHOD is set to 'telegram' but TELEGRAM_CHAT_ID is not configured. "
                "Telegram alerts will not work."
            )

        if self.alert_method == "email" and not self.email_smtp_server:
            _logger.warning(
                "ALERT_METHOD is set to 'email' but EMAIL_SMTP_SERVER is not configured. "
                "Email alerts will not work."
            )

        if self.alert_method == "email" and not all(
            [self.email_username, self.email_password, self.email_from, self.email_to]
        ):
            _logger.warning(
                "ALERT_METHOD is set to 'email' but one or more email credentials are missing "
                "(EMAIL_USERNAME, EMAIL_PASSWORD, EMAIL_FROM, EMAIL_TO). Email alerts will not work."
            )

        # Log configuration summary
        _logger.info("Configuration loaded successfully:")
        _logger.info(f"  MIN_PROFIT_PERCENT: {self.min_profit_percent}%")
        _logger.info(f"  FEE_BUFFER_PERCENT: {self.fee_buffer_percent}%")
        _logger.info(f"  ALERT_METHOD: {self.alert_method or 'None'}")
        _logger.info(f"  LOG_DB_PATH: {self.log_db_path}")

        # Ensure directories exist
        self._ensure_directories()

        return is_valid

    def _ensure_directories(self) -> None:
        """Ensure that all required directories exist."""
        for path_str in [self.db_path, self.log_db_path, self.log_file]:
            path = Path(path_str)
            path.parent.mkdir(parents=True, exist_ok=True)


def get_config() -> Config:
    """
    Get the global configuration instance.

    This helper function returns the global config object loaded from
    environment variables. Call this function to access configuration
    throughout the application.

    Returns:
        Config instance with current configuration
    """
    return config


# Global configuration instance - loaded from environment variables
config = Config.from_env()
