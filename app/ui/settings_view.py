"""
Settings view for configuring the arbitrage spotter.

Displays current configuration values from .env file.
Settings are read-only and must be modified via .env file.
"""

from datetime import datetime

import streamlit as st

from app.core.arb_detector import ArbitrageDetector
from app.core.config import config


def render_settings_view():
    """
    Render the settings page (read-only display of current config).

    Settings cannot be modified through the UI - configure via
    environment variables or .env file.
    """
    st.title("⚙️ Settings")
    st.markdown("---")

    st.info(
        "📖 Settings are currently read-only. Configure via environment "
        "variables or .env file."
    )

    # API Configuration
    st.subheader("API Configuration")

    col1, col2 = st.columns(2)

    with col1:
        st.text_input(
            "API Endpoint",
            value=config.api_endpoint,
            disabled=True,
            help="Polymarket API endpoint URL",
        )

    with col2:
        api_key_display = "***" if config.api_key else "Not set"
        st.text_input(
            "API Key",
            value=api_key_display,
            disabled=True,
            help="Your Polymarket API key if required",
        )

    st.markdown("---")

    # Detection Parameters
    st.subheader("Detection Parameters")

    col1, col2 = st.columns(2)

    with col1:
        st.number_input(
            "Minimum Profit Threshold",
            value=config.min_profit_threshold,
            disabled=True,
            format="%.3f",
            help="Minimum profit threshold to consider an opportunity",
        )

    with col2:
        st.number_input(
            "Maximum Stake ($)",
            value=config.max_stake,
            disabled=True,
            help="Maximum amount to stake per arbitrage opportunity",
        )

    col1, col2 = st.columns(2)

    with col1:
        st.number_input(
            "Min Profit Percent",
            value=config.min_profit_percent,
            disabled=True,
            format="%.2f",
            help="Minimum profit percentage",
        )

    with col2:
        st.number_input(
            "Fee Buffer Percent",
            value=config.fee_buffer_percent,
            disabled=True,
            format="%.2f",
            help="Fee buffer percentage",
        )

    st.markdown("---")

    # Database Configuration
    st.subheader("Database Configuration")

    col1, col2 = st.columns(2)

    with col1:
        st.text_input(
            "Database Path",
            value=config.db_path,
            disabled=True,
            help="Path to SQLite database file",
        )

    with col2:
        st.text_input(
            "Log Database Path",
            value=config.log_db_path,
            disabled=True,
            help="Path to log database file",
        )

    st.markdown("---")

    # Logging Configuration
    st.subheader("Logging Configuration")

    col1, col2 = st.columns(2)

    with col1:
        st.text_input("Log Level", value=config.log_level, disabled=True)

    with col2:
        st.text_input(
            "Log File Path",
            value=config.log_file,
            disabled=True,
            help="Path to log file",
        )

    st.markdown("---")

    # Alert Configuration
    st.subheader("Alert Configuration")

    alert_method_display = config.alert_method or "Not configured"
    st.text_input(
        "Alert Method",
        value=alert_method_display,
        disabled=True,
        help="Alert method (email/telegram)",
    )

    if config.alert_method == "telegram":
        col1, col2 = st.columns(2)
        with col1:
            st.text_input(
                "Telegram API Key",
                value="***" if config.telegram_api_key else "Not set",
                disabled=True,
            )
        with col2:
            st.text_input(
                "Telegram Chat ID",
                value=config.telegram_chat_id or "Not set",
                disabled=True,
            )

    st.markdown("---")

    # System Information
    st.subheader("System Information")

    info_col1, info_col2 = st.columns(2)

    with info_col1:
        st.write("**Database Status**")
        try:
            detector = ArbitrageDetector()
            detector.get_recent_opportunities(limit=1)
            st.success("🟢 Connected")
        except Exception as e:
            st.error(f"🔴 Error: {str(e)}")

        st.write("**Python Version**")
        import sys

        st.text(sys.version.split()[0])

    with info_col2:
        st.write("**Streamlit Version**")
        st.text(st.__version__)

        st.write("**Last Updated**")
        st.text(datetime.now().strftime("%Y-%m-%d"))


if __name__ == "__main__":
    render_settings_view()
