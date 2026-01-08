"""
Main dashboard for Polymarket Arbitrage Spotter.

Renders the main dashboard page with navigation to different views.
"""

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from app.core.arb_detector import ArbitrageDetector
from app.core.history_recorder import record_market_tick
from app.core.logger import fetch_recent, logger
from app.core.config import config
from app.core.data_source import get_data_source
from app.core.mock_data import MockDataGenerator
from app.ui.depth_view import render_depth_view
from app.ui.history_view import render_history_view
from app.ui.patterns_view import render_patterns_view
from app.ui.price_alerts_view import render_price_alerts_view
from app.ui.replay_view import render_replay_view
from app.ui.settings_view import render_settings_view
from app.ui.wallets_view import render_wallets_view

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
    pages = [
        "Dashboard",
        "Pattern Insights",
        "History",
        "Replay & Label",
        "Depth Monitor",
        "Price Alerts",
        "Settings",
    ]
    if config.wallet_features_enabled:
        pages.insert(6, "Wallet Intelligence")
    else:
        st.sidebar.caption(
            "Wallet intelligence is disabled. Set WALLET_FEATURES_ENABLED=true "
            "to enable."
        )

    page = st.sidebar.radio("Go to", pages)

    # Mode toggle in sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("Mode")
    
    # Initialize mode from config if not in session state
    if "mode" not in st.session_state:
        st.session_state.mode = "Mock Mode" if config.mode == "mock" else "Live Read-Only"
    
    mode_options = ["Mock Mode", "Live Read-Only"]
    selected_mode_index = mode_options.index(st.session_state.mode)
    
    mode = st.sidebar.radio(
        "Select Mode",
        mode_options,
        index=selected_mode_index,
        help="Mock Mode uses simulated data. Live Read-Only reads from API without trading.",
    )

    # Update session state and config if changed
    if mode != st.session_state.mode:
        st.session_state.mode = mode
        # Also update config for other parts of the app
        config.mode = "live" if mode == "Live Read-Only" else "mock"
        st.rerun()

    # Render appropriate page
    if page == "Dashboard":
        render_dashboard_content()
    elif page == "Pattern Insights":
        render_patterns_view()
    elif page == "History":
        render_history_view()
    elif page == "Replay & Label":
        render_replay_view()
    elif page == "Depth Monitor":
        render_depth_view()
    elif page == "Price Alerts":
        render_price_alerts_view()
    elif page == "Wallet Intelligence":
        render_wallets_view()
    elif page == "Settings":
        render_settings_view()


def render_dashboard_content():
    """
    Render the main dashboard content.
    """
    st.title("🎯 Polymarket Arbitrage Spotter")

    # Display current mode and status
    mode_emoji = "🔧" if st.session_state.mode == "Mock Mode" else "📡"
    
    status_col1, status_col2 = st.columns([3, 1])
    with status_col1:
        st.info(f"{mode_emoji} Running in: **{st.session_state.mode}**")
    
    with status_col2:
        if st.session_state.mode == "Live Read-Only":
            # Check API health
            from app.core.api_client import PolymarketAPIClient
            client = PolymarketAPIClient()
            if client.health_check():
                st.success("🟢 API Connected")
            else:
                st.error("🔴 API Offline")
        else:
            st.success("🟢 Local Mock Active")

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

    # Control buttons
    if st.session_state.mode == "Mock Mode":
        st.subheader("🎮 Mock Controls")
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("🔄 Generate Data", type="primary"):
                run_data_cycle()
                st.success("Mock data generated!")
                st.rerun()
    else:
        st.subheader("📡 Live Controls")
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("📡 Scan Live Markets", type="primary"):
                with st.spinner("Fetching live data from Polymarket..."):
                    run_data_cycle()
                st.success("Live scan complete!")
                st.rerun()
        
        with col2:
            auto_refresh = st.checkbox("Auto-refresh (30s)", value=False)
            if auto_refresh:
                st.info("Auto-refresh is active")
                # We'll use streamlit's native sleep/rerun for simple auto-refresh
                import time
                time.sleep(30)
                run_data_cycle()
                st.rerun()

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


def run_data_cycle():
    """Run a single cycle of data fetching and arbitrage detection."""
    from app.core.logger import log_event, init_db
    
    # Initialize database
    init_db()
    
    # Get the appropriate data source
    mode_key = "live" if st.session_state.mode == "Live Read-Only" else "mock"
    source = get_data_source(mode_key)
    
    # Fetch markets
    markets = source.get_markets(limit=20)
    
    # Record market data to history
    for market in markets:
        record_market_tick(
            market_id=market.id,
            yes_price=market.yes_price,
            no_price=market.no_price,
            volume=market.volume_24h,
        )

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
                "mode": mode_key,
                "decision": "alerted",
                "mock_result": "success" if mode_key == "mock" else None,
                "failure_reason": None,
                "latency_ms": 0,
            }
        )

    logger.info(
        f"Completed {mode_key} data cycle: {len(opportunities)} opportunities from {len(markets)} markets"
    )


def generate_mock_data():
    """
    Deprecated: Use run_data_cycle instead.
    """
    run_data_cycle()


if __name__ == "__main__":
    render_dashboard()
