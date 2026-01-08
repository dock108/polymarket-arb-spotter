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
    Render the settings page with configurable alert rules.
    """
    st.title("⚙️ Settings")
    st.markdown("---")

    # In-App Alert Configuration (Section 4.2)
    st.subheader("🔔 Alert Configuration")
    
    with st.expander("🛠️ Alert Rules & Preferences", expanded=True):
        st.markdown("""
        **Note:** These rules control real-time alerts only. 
        All arbitrage signals are still tracked and logged in the History view regardless of these settings.
        """)
        
        col1, col2 = st.columns(2)
        with col1:
            config.alert_min_roi = st.number_input(
                "Minimum ROI Threshold (%)",
                min_value=0.0,
                max_value=100.0,
                value=config.alert_min_roi,
                help="Only notify if ROI is above this percentage."
            )
            config.alert_min_liquidity = st.number_input(
                "Minimum Liquidity Threshold ($)",
                min_value=0.0,
                value=config.alert_min_liquidity,
                help="Only notify if market liquidity is above this amount."
            )
            
        with col2:
            config.alert_banner_enabled = st.toggle(
                "Enable Notification Banners",
                value=config.alert_banner_enabled,
                help="Show a temporary toast notification when a new signal arrives."
            )
            config.alert_sound_enabled = st.toggle(
                "Enable Notification Sound",
                value=config.alert_sound_enabled,
                help="Play a sound when a new signal arrives."
            )

        # Category filtering (simplified for now)
        st.multiselect(
            "Ignored Categories",
            ["Politics", "Crypto", "Sports", "Entertainment", "Economy"],
            default=config.alert_ignored_categories,
            on_change=lambda: setattr(config, 'alert_ignored_categories', st.session_state.ignored_cats) if 'ignored_cats' in st.session_state else None,
            key="ignored_cats"
        )
        
        st.caption("Settings changed here persist for this application run.")

    st.markdown("---")

    # Outbound Event Queue Debug (Section 4.3)
    with st.expander("📡 Outbound Event Queue (Future-Safe)", expanded=False):
        st.markdown("""
        This queue stores events for future outbound delivery systems (Webhooks, Push, Email).
        Currently, events are stored internally only.
        """)
        
        from app.core.notifications import get_notification_service
        notification_service = get_notification_service()
        
        import sqlite3
        conn = sqlite3.connect(config.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM outbound_queue ORDER BY created_at DESC LIMIT 10")
        queue_items = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        if queue_items:
            st.table(queue_items)
        else:
            st.info("No outbound events in queue.")

    st.markdown("---")

    # API Configuration
    st.subheader("API Configuration")
    
    st.info(
        "📖 The following settings are loaded from .env and are read-only."
    )

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

    # Ethics & Safety Configuration
    st.subheader("Ethics & Safety")

    col1, col2 = st.columns(2)

    with col1:
        st.text_input(
            "Wallet Features Enabled",
            value="Yes" if config.wallet_features_enabled else "No",
            disabled=True,
            help="Controls whether wallet intelligence features are available.",
        )

    with col2:
        st.text_input(
            "Mask Full Wallet Addresses",
            value="Yes" if config.do_not_expose_full_addresses else "No",
            disabled=True,
            help="Prevents displaying full wallet addresses in UI or alerts.",
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
