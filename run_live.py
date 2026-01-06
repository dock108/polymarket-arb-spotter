#!/usr/bin/env python3
"""
Main entry point for running the Polymarket Arbitrage Spotter with Streamlit UI.

Usage:
    streamlit run run_live.py

TODO: Add command-line arguments for configuration
TODO: Implement background monitoring thread
TODO: Add graceful shutdown handling
"""

import streamlit as st

from app.ui.dashboard import render_dashboard
from app.ui.history_view import render_history_view
from app.ui.settings_view import render_settings_view
from app.core.logger import logger, start_heartbeat


# Initialize heartbeat monitor at module level (only once per Streamlit session)
if 'heartbeat' not in st.session_state:
    st.session_state.heartbeat = start_heartbeat(
        interval=60,
        callback=lambda: {
            "status": "monitoring",
            "mode": "live_ui"
        }
    )


def main():
    """
    Main application entry point.
    
    TODO: Add navigation between pages
    TODO: Implement session state management
    TODO: Add authentication if needed
    """
    logger.info("Starting Polymarket Arbitrage Spotter")
    
    # Page configuration
    st.set_page_config(
        page_title="Polymarket Arb Spotter",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Sidebar navigation
    st.sidebar.title("🎯 Polymarket Arb Spotter")
    st.sidebar.markdown("---")
    
    page = st.sidebar.radio(
        "Navigation",
        ["Dashboard", "History", "Settings"],
        index=0
    )
    
    st.sidebar.markdown("---")
    
    # Status indicators
    st.sidebar.subheader("Status")
    st.sidebar.success("🟢 System Online")
    st.sidebar.info("ℹ️ Monitoring: Paused")
    
    st.sidebar.markdown("---")
    
    # Info
    st.sidebar.markdown("### About")
    st.sidebar.markdown(
        "Polymarket Arbitrage Spotter detects arbitrage opportunities "
        "in prediction markets. This tool is for detection only - "
        "no trading is performed."
    )
    
    st.sidebar.markdown("---")
    st.sidebar.caption("Version: 0.1.0-alpha")
    
    # Render selected page
    if page == "Dashboard":
        render_dashboard()
    elif page == "History":
        render_history_view()
    elif page == "Settings":
        render_settings_view()


if __name__ == "__main__":
    main()
