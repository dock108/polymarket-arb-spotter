"""
Settings view for configuring the arbitrage spotter.

Note: This is a placeholder UI. Full settings persistence will be
implemented in a future version. Currently displays configuration
values from .env file but changes are not saved.
"""

from datetime import datetime
from typing import Any, Dict

import streamlit as st

from app.core.config import config
from app.core.logger import logger


def render_settings_view():
    """
    Render the settings page.

    Currently displays configuration values but does not persist changes.
    Settings must be modified in .env file and application restarted.
    """
    st.title("⚙️ Settings")
    st.markdown("---")

    # API Configuration
    st.subheader("API Configuration")

    # Note: Values are displayed but not currently persisted
    _ = st.text_input(
        "API Endpoint", value=config.api_endpoint, help="Polymarket API endpoint URL"
    )

    _ = st.text_input(
        "API Key (Optional)",
        value=config.api_key or "",
        type="password",
        help="Your Polymarket API key if required",
    )

    st.markdown("---")

    # Detection Parameters
    st.subheader("Detection Parameters")

    col1, col2 = st.columns(2)

    with col1:
        _ = st.number_input(
            "Minimum Profit Threshold",
            min_value=0.0,
            max_value=1.0,
            value=config.min_profit_threshold,
            step=0.001,
            format="%.3f",
            help=(
                "Minimum profit percentage to consider an opportunity "
                "(e.g., 0.01 = 1%)"
            ),
        )

    with col2:
        _ = st.number_input(
            "Maximum Stake ($)",
            min_value=0.0,
            value=config.max_stake,
            step=100.0,
            help="Maximum amount to stake per arbitrage opportunity",
        )

    st.markdown("---")

    # Database Configuration
    st.subheader("Database Configuration")

    _ = st.text_input(
        "Database Path", value=config.db_path, help="Path to SQLite database file"
    )

    st.markdown("---")

    # Logging Configuration
    st.subheader("Logging Configuration")

    col1, col2 = st.columns(2)

    with col1:
        _ = st.selectbox(
            "Log Level",
            ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            index=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].index(
                config.log_level
            ),
        )

    with col2:
        _ = st.text_input(
            "Log File Path", value=config.log_file, help="Path to log file"
        )

    st.markdown("---")

    # Notification Settings
    st.subheader("Notification Settings")

    enable_notifications = st.checkbox(
        "Enable Notifications",
        value=False,
        help="Enable notifications for new opportunities",
    )

    if enable_notifications:
        _ = st.selectbox(
            "Notification Method", ["Email", "Telegram", "Discord", "Webhook"]
        )

        _ = st.text_input(
            "Notification Target",
            help="Email address, bot token, webhook URL, etc.",
        )

    st.markdown("---")

    # Advanced Settings
    with st.expander("🔧 Advanced Settings"):
        st.markdown("**Performance**")

        _ = st.number_input(
            "Refresh Interval (seconds)",
            min_value=1,
            max_value=300,
            value=5,
            help="How often to check for new opportunities",
        )

        _ = st.number_input(
            "Max Worker Threads",
            min_value=1,
            max_value=32,
            value=4,
            help="Number of parallel workers for detection",
        )

        st.markdown("**Risk Management**")

        _ = st.slider(
            "Maximum Risk Score",
            min_value=0.0,
            max_value=10.0,
            value=5.0,
            step=0.1,
            help="Maximum acceptable risk score for opportunities",
        )

    st.markdown("---")

    # Action buttons
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button("💾 Save Settings", type="primary"):
            st.warning(
                "⚠️ Settings persistence not yet implemented. Please update .env file manually."
            )
            logger.info("Settings save attempted (not implemented)")

    with col2:
        if st.button("🔄 Reset to Defaults"):
            st.info("ℹ️ Reset not yet implemented. Current values are from .env file.")
            logger.info("Settings reset attempted (not implemented)")

    st.markdown("---")

    # System Information
    st.subheader("System Information")

    info_col1, info_col2 = st.columns(2)

    with info_col1:
        st.write("**Database Status**")
        st.success("🟢 Connected")

        st.write("**API Status**")
        st.success("🟢 Connected")

    with info_col2:
        st.write("**Version**")
        st.text("v0.1.0-alpha")

        st.write("**Last Updated**")
        st.text(datetime.now().strftime("%Y-%m-%d"))


def validate_settings(settings: Dict[str, Any]) -> bool:
    """
    Validate settings before saving.

    Args:
        settings: Settings dictionary

    Returns:
        True if valid, False otherwise

    Note: Placeholder for future implementation when persistence is added.
    """
    # Placeholder - validation will be implemented with persistence
    return True


if __name__ == "__main__":
    # For testing the settings view standalone
    render_settings_view()
