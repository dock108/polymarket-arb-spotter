#!/usr/bin/env python3
"""
Main entry point for running the Polymarket Arbitrage Spotter with Streamlit UI.

Usage:
    streamlit run run_live.py
"""

import streamlit as st

# Page configuration MUST be the first Streamlit command
st.set_page_config(
    page_title="Polymarket Arb Spotter",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

from app.ui.dashboard import render_dashboard
from app.ui.history_view import render_history_view
from app.ui.settings_view import render_settings_view
from app.core.logger import logger, start_heartbeat
from app.core.history_recorder import start_history_recorder, stop_history_recorder


# Initialize heartbeat monitor at module level (only once per Streamlit session)
if "heartbeat" not in st.session_state:
    st.session_state.heartbeat = start_heartbeat(
        interval=60, callback=lambda: {"status": "monitoring", "mode": "live_ui"}
    )

# Initialize history recorder at module level (only once per Streamlit session)
if "history_recorder" not in st.session_state:
    st.session_state.history_recorder = start_history_recorder()


def main():
    """Main application entry point."""
    logger.info("Starting Polymarket Arbitrage Spotter")

    # The dashboard module now handles its own internal navigation
    # and provides a more comprehensive set of views.
    render_dashboard()


if __name__ == "__main__":
    main()
