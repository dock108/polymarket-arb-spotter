"""
Main entry point for the Replay & Label view.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from app.core.history_store import get_market_ids, get_ticks
from app.core.logger import init_db
from app.ui.utils import format_market_title
from app.ui.replay_tabs import render_price_chart_tab, render_annotation_tab, render_labels_tab

def render_replay_view():
    """Render the historical market replay interface."""
    st.title("🎬 Market Replay & Labeling")
    st.markdown("---")

    init_db()
    available_markets = get_market_ids()

    if not available_markets:
        st.warning("⚠️ No historical data available. Run a scan to populate history.")
        return

    # Handle deep-linking from History/Alerts
    initial_idx = 0
    def_end = datetime.now()
    def_start = def_end - timedelta(days=7)

    if "replay_market_id" in st.session_state and st.session_state.replay_market_id in available_markets:
        initial_idx = available_markets.index(st.session_state.replay_market_id)
        if "replay_timestamp" in st.session_state:
            ts = pd.to_datetime(st.session_state.replay_timestamp)
            def_start, def_end = ts - timedelta(hours=12), ts + timedelta(hours=12)

    st.sidebar.subheader("📋 Replay Controls")
    selected_market = st.sidebar.selectbox("Select Market", available_markets, index=initial_idx)
    
    date_range = st.sidebar.date_input("Date Range", value=(def_start.date(), def_end.date()))
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date = datetime.combine(date_range[0], datetime.min.time())
        end_date = datetime.combine(date_range[1], datetime.max.time())
    else:
        start_date, end_date = def_start, def_end

    st.subheader(f"📊 Replaying: {format_market_title(selected_market)}")

    ticks = get_ticks(market_id=selected_market, start=start_date, end=end_date, limit=10000)
    if not ticks:
        st.warning(f"No tick data found for {selected_market} in this range.")
        return

    df = pd.DataFrame(ticks)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    tab1, tab2, tab3 = st.tabs(["📈 Price Chart", "🏷️ Manual Label", "📋 View Labels"])
    with tab1: render_price_chart_tab(df, selected_market, start_date, end_date)
    with tab2: render_annotation_tab(df, selected_market, start_date, end_date)
    with tab3: render_labels_tab(selected_market, start_date, end_date)

    st.markdown("---")
    st.caption(f"Loaded {len(ticks)} data points. Last updated: {datetime.now().strftime('%H:%M:%S')}")
