"""
Main dashboard for Polymarket Arbitrage Spotter.
"""

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from app.core.arb_detector import ArbitrageDetector
from app.core.config import config
from app.core.logger import fetch_recent, logger
from app.core.mock_data import MockDataGenerator
from app.ui.depth_view import render_depth_view
from app.ui.price_alerts_view import render_price_alerts_view

# Add project root to Python path if running directly
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))


def render_dashboard():
    """
    Render the main dashboard page with navigation.
    """
    st.set_page_config(
        page_title="Polymarket Arbitrage Spotter", page_icon="🎯", layout="wide"
    )

    # Sidebar navigation
    st.sidebar.title("📊 Navigation")
    page = st.sidebar.radio(
        "Go to", ["Dashboard", "History", "Depth Monitor", "Price Alerts", "Settings"]
    )

    # Mode toggle in sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("Mode")
    mode = st.sidebar.radio(
        "Select Mode",
        ["Mock Mode", "Live Read-Only"],
        help="Mock Mode uses simulated data. Live Read-Only reads from API without trading.",
    )

    # Store mode in session state
    st.session_state.mode = mode

    # Render appropriate page
    if page == "Dashboard":
        render_dashboard_content()
    elif page == "History":
        render_history_view()
    elif page == "Depth Monitor":
        render_depth_view()
    elif page == "Price Alerts":
        render_price_alerts_view()
    elif page == "Settings":
        render_settings_view()


def render_dashboard_content():
    """
    Render the main dashboard content.
    """
    st.title("🎯 Polymarket Arbitrage Spotter")

    # Display current mode
    mode_emoji = "🔧" if st.session_state.mode == "Mock Mode" else "📡"
    st.info(f"{mode_emoji} Running in: **{st.session_state.mode}**")

    st.markdown("---")

    # Initialize detector
    detector = ArbitrageDetector()

    # Get recent opportunities from database
    recent_opps = detector.get_recent_opportunities(limit=10)

    # Get event logs
    recent_events = fetch_recent(limit=100)

    # Calculate metrics
    active_count = len(recent_opps)
    total_profit = sum(opp.get("expected_profit", 0) for opp in recent_opps)
    avg_return = (
        sum(opp.get("expected_return_pct", 0) for opp in recent_opps) / len(recent_opps)
        if recent_opps
        else 0
    )

    # Count failures
    failure_count = sum(1 for event in recent_events if event.get("failure_reason"))

    # Header with key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Active Opportunities", active_count)

    with col2:
        st.metric("Events Logged", len(recent_events))

    with col3:
        st.metric("Potential Profit", f"${total_profit:.2f}")

    with col4:
        st.metric("Avg Return", f"{avg_return:.2f}%")

    st.markdown("---")

    # Main content area - Current Opportunities
    st.subheader("📊 Current Arbitrage Opportunities")

    if recent_opps:
        # Convert to DataFrame for display
        df = pd.DataFrame(recent_opps)

        # Select and rename columns for display
        display_cols = [
            "detected_at",
            "market_name",
            "opportunity_type",
            "expected_profit",
            "expected_return_pct",
            "risk_score",
        ]
        df_display = df[display_cols].copy()
        df_display.columns = [
            "Time",
            "Market",
            "Type",
            "Profit ($)",
            "Return (%)",
            "Risk",
        ]

        # Format values
        df_display["Profit ($)"] = df_display["Profit ($)"].apply(lambda x: f"${x:.2f}")
        df_display["Return (%)"] = df_display["Return (%)"].apply(lambda x: f"{x:.2f}%")
        df_display["Risk"] = df_display["Risk"].apply(lambda x: f"{x:.2f}")

        st.dataframe(df_display, use_container_width=True)
    else:
        st.info(
            "No opportunities detected yet. Generate some data using the controls below."
        )

    st.markdown("---")

    # Profitability Summary
    st.subheader("💰 Profitability Summary")

    summary_col1, summary_col2 = st.columns(2)

    with summary_col1:
        st.metric("Total Opportunities", len(recent_events))
        profitable_count = sum(
            1 for event in recent_events if event.get("decision") == "alerted"
        )
        st.metric("Profitable Detected", profitable_count)

    with summary_col2:
        if recent_events:
            avg_profit_pct = sum(
                event.get("expected_profit_pct", 0) for event in recent_events
            ) / len(recent_events)
            st.metric("Avg Profit %", f"{avg_profit_pct:.2f}%")
        else:
            st.metric("Avg Profit %", "0.00%")
        st.metric("Failed Detections", failure_count)

    st.markdown("---")

    # Failure Reasons Chart
    st.subheader("📉 Failure Reasons")

    if failure_count > 0:
        failure_reasons = {}
        for event in recent_events:
            reason = event.get("failure_reason")
            if reason:
                failure_reasons[reason] = failure_reasons.get(reason, 0) + 1

        # Create DataFrame for chart
        failure_df = pd.DataFrame(
            list(failure_reasons.items()), columns=["Reason", "Count"]
        )
        st.bar_chart(failure_df.set_index("Reason"))
    else:
        st.info("No failures recorded.")

    st.markdown("---")

    # Control buttons - Mock mode only
    if st.session_state.mode == "Mock Mode":
        st.subheader("🎮 Mock Controls")

        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            if st.button("🔄 Generate Data", type="primary"):
                generate_mock_data()
                st.success("Mock data generated! Refresh to see results.")
                st.rerun()
    else:
        st.info(
            "📡 Live Read-Only Mode - Monitoring Polymarket API (not yet implemented)"
        )

    st.markdown("---")

    # System Status
    st.subheader("🔍 System Status")

    status_col1, status_col2 = st.columns(2)

    with status_col1:
        st.markdown("**Database Status**")
        try:
            # Test database connection
            detector.get_recent_opportunities(limit=1)
            st.success("🟢 Connected")
        except Exception as e:
            st.error(f"🔴 Error: {str(e)}")

    with status_col2:
        st.markdown("**Mode**")
        st.info(f"{st.session_state.mode}")

    # Footer
    st.markdown("---")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def generate_mock_data():
    """Generate mock data for testing."""
    from app.core.logger import log_event, init_db

    # Initialize database
    init_db()

    # Generate mock data
    generator = MockDataGenerator(arb_frequency=0.3)
    markets = generator.generate_snapshots(count=20)

    # Initialize detector
    detector = ArbitrageDetector()

    # Detect opportunities
    opportunities = detector.detect_opportunities(markets)

    # Save opportunities to database
    for opp in opportunities:
        detector.save_opportunity(opp)

        # Also log as event
        log_event(
            {
                "timestamp": opp.detected_at.isoformat(),
                "market_id": opp.market_id,
                "market_name": opp.market_name,
                "yes_price": opp.positions[0]["price"] if opp.positions else 0,
                "no_price": opp.positions[1]["price"] if len(opp.positions) > 1 else 0,
                "sum": sum(p["price"] for p in opp.positions),
                "expected_profit_pct": opp.expected_return_pct,
                "mode": "mock",
                "decision": "alerted",
                "mock_result": "success",
                "failure_reason": None,
                "latency_ms": 0,
            }
        )

    logger.info(
        f"Generated {len(opportunities)} opportunities from {len(markets)} markets"
    )


def render_history_view():
    """
    Render the history view page with filters.
    """
    from app.core.logger import fetch_recent

    st.title("📜 Opportunity History")
    st.markdown("---")

    # Filters (placeholder - not currently applied to results)
    col1, col2, col3 = st.columns(3)

    with col1:
        _ = st.selectbox(
            "Time Range", ["All Time", "Last 24 Hours", "Last 7 Days", "Last 30 Days"]
        )

    with col2:
        decision_filter = st.selectbox("Decision", ["All", "Alerted", "Ignored"])

    with col3:
        min_profit = st.number_input("Min Profit %", min_value=0.0, value=0.0, step=0.1)

    st.markdown("---")

    # Fetch history
    events = fetch_recent(limit=1000)

    # Apply filters
    if decision_filter != "All":
        events = [
            e
            for e in events
            if e.get("decision", "").lower() == decision_filter.lower()
        ]

    if min_profit > 0:
        events = [e for e in events if e.get("expected_profit_pct", 0) >= min_profit]

    # Statistics
    st.subheader("Summary Statistics")

    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)

    with stat_col1:
        st.metric("Total Events", len(events))

    with stat_col2:
        alerted = sum(1 for e in events if e.get("decision") == "alerted")
        st.metric("Alerted", alerted)

    with stat_col3:
        if events:
            avg_profit = sum(e.get("expected_profit_pct", 0) for e in events) / len(
                events
            )
            st.metric("Avg Profit %", f"{avg_profit:.2f}%")
        else:
            st.metric("Avg Profit %", "0.00%")

    with stat_col4:
        failures = sum(1 for e in events if e.get("failure_reason"))
        st.metric("Failures", failures)

    st.markdown("---")

    # History table
    st.subheader("Event History")

    if events:
        df = pd.DataFrame(events)

        # Select relevant columns
        display_cols = [
            "timestamp",
            "market_name",
            "expected_profit_pct",
            "decision",
            "mode",
            "failure_reason",
        ]
        df_display = df[[col for col in display_cols if col in df.columns]].copy()

        # Rename columns
        column_names = {
            "timestamp": "Time",
            "market_name": "Market",
            "expected_profit_pct": "Profit %",
            "decision": "Decision",
            "mode": "Mode",
            "failure_reason": "Failure Reason",
        }
        df_display.columns = [column_names.get(col, col) for col in df_display.columns]

        st.dataframe(df_display, use_container_width=True)

        # Export option
        if st.button("📥 Export to CSV"):
            csv = df_display.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"opportunities_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
            )
    else:
        st.info("No historical events found.")

    st.markdown("---")

    # Failure reasons chart
    st.subheader("📉 Failure Reasons")

    failures_with_reasons = [e for e in events if e.get("failure_reason")]

    if failures_with_reasons:
        failure_counts = {}
        for event in failures_with_reasons:
            reason = event.get("failure_reason", "Unknown")
            failure_counts[reason] = failure_counts.get(reason, 0) + 1

        failure_df = pd.DataFrame(
            list(failure_counts.items()), columns=["Reason", "Count"]
        )
        st.bar_chart(failure_df.set_index("Reason"))
    else:
        st.info("No failures recorded.")


def render_settings_view():
    """
    Render the settings page (read-only display of current config).
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
    render_dashboard()
