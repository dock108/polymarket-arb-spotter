"""
Main dashboard for Polymarket Arbitrage Spotter.
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
from app.core.notifications import get_notification_service
from app.core.insights import InsightsSummary
from app.core.narrative import get_hint

from app.ui.depth_view import render_depth_view
from app.ui.history_view import render_history_view
from app.ui.patterns_view import render_patterns_view
from app.ui.price_alerts_view import render_price_alerts_view
from app.ui.replay_view import render_replay_view
from app.ui.settings_view import render_settings_view
from app.ui.wallets_view import render_wallets_view
from app.ui.alerts_view import render_alerts_view, render_notification_handler
from app.ui.dashboard_components import render_metric_cards, render_top_opportunity
from app.ui.components.market_detail_drawer import render_market_detail_drawer
from app.ui.utils import format_market_title, format_expiry_date, render_category_badge

# Add project root to Python path if running directly
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))

def render_dashboard():
    """Render the main dashboard page with navigation."""
    render_notification_handler()

    # Sidebar navigation
    st.sidebar.title("📊 Navigation")
    
    notification_service = get_notification_service()
    unread_count = notification_service.get_unread_alerts_count()
    alert_label = f"🔔 Alerts ({unread_count})" if unread_count > 0 else "🔔 Alerts"

    pages = ["Dashboard", "Pattern Insights", "History", "Replay & Label", 
             alert_label, "Depth Monitor", "Price Alerts", "Settings"]
    
    if config.wallet_features_enabled:
        pages.insert(7, "Wallet Intelligence")

    if "selected_page" not in st.session_state:
        st.session_state.selected_page = "Dashboard"
    
    try:
        page_index = pages.index(st.session_state.selected_page)
    except ValueError:
        if st.session_state.selected_page.startswith("🔔 Alerts"):
            page_index = pages.index(alert_label)
        else:
            page_index = 0

    page = st.sidebar.radio("Go to", pages, index=page_index)
    
    if page != st.session_state.selected_page:
        st.session_state.selected_page = page
        st.rerun()

    # Mode toggle
    st.sidebar.markdown("---")
    st.sidebar.subheader("Mode")
    
    if "mode" not in st.session_state:
        st.session_state.mode = "Mock Mode" if config.mode == "mock" else "Live Read-Only"
    
    mode_options = ["Mock Mode", "Live Read-Only"]
    selected_mode_index = mode_options.index(st.session_state.mode)
    
    mode = st.sidebar.radio("Select Mode", mode_options, index=selected_mode_index)

    if mode != st.session_state.mode:
        st.session_state.mode = mode
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
    elif page.startswith("🔔 Alerts"):
        render_alerts_view()
    elif page == "Depth Monitor":
        render_depth_view()
    elif page == "Price Alerts":
        render_price_alerts_view()
    elif page == "Wallet Intelligence":
        render_wallets_view()
    elif page == "Settings":
        render_settings_view()

def render_dashboard_content():
    """Render the main dashboard content."""
    st.title("🎯 Polymarket Arbitrage Spotter")

    if "selected_market_id" not in st.session_state:
        st.session_state.selected_market_id = None

    mode_emoji = "🔧" if st.session_state.mode == "Mock Mode" else "📡"
    source_name = "LIVE API" if st.session_state.mode == "Live Read-Only" else "Mock Feed"
    
    status_col1, status_col2 = st.columns([3, 1])
    with status_col1:
        st.info(f"{mode_emoji} Running in: **{st.session_state.mode}** (Data Source: **{source_name}**)")
    
    with status_col2:
        if st.session_state.mode == "Live Read-Only":
            from app.core.api_client import PolymarketAPIClient
            if PolymarketAPIClient().health_check():
                st.success("🟢 API Connected")
            else:
                st.error("🔴 API Offline")
        else:
            st.success("🟢 Local Mock Active")

    st.markdown("---")

    detector = ArbitrageDetector()
    current_mode_key = "live" if st.session_state.mode == "Live Read-Only" else "mock"

    recent_opps = detector.get_recent_opportunities(limit=10, mode=current_mode_key)
    recent_opps = sorted(recent_opps, key=lambda x: (x.get("expected_return_pct", 0), x.get("expected_profit", 0)), reverse=True)
    recent_events = fetch_recent(limit=100, mode=current_mode_key)

    active_count = len(recent_opps)
    total_profit = sum(opp.get("expected_profit", 0) for opp in recent_opps)
    avg_return = sum(opp.get("expected_return_pct", 0) for opp in recent_opps) / len(recent_opps) if recent_opps else 0

    # Insights Cards (6.2)
    summary = InsightsSummary().get_summary(mode=current_mode_key)
    render_metric_cards(summary, active_count, avg_return, total_profit)

    st.markdown("---")

    if recent_opps:
        render_top_opportunity(recent_opps[0])
        st.markdown("---")

    # Layout: Main content vs Detail Drawer
    main_col, drawer_col = st.columns([2, 1]) if st.session_state.selected_market_id else (st.container(), None)

    with main_col:
        st.subheader("📊 Current Arbitrage Opportunities")
        if recent_opps:
            h_col1, h_col2, h_col3, h_col4, h_col5 = st.columns([0.5, 3, 1.2, 1.2, 1.3])
            h_col1.markdown("**View**")
            h_col2.markdown("**Market**")
            h_col3.markdown("**Profit ($)**")
            h_col4.markdown("**Return (%)**")
            h_col5.markdown("**Risk Score**", help=get_hint("untradeable_warning"))
            st.markdown("---")

            for i, opp in enumerate(recent_opps):
                roi = opp['expected_return_pct']
                bg_color = "rgba(40, 167, 69, 0.1)" if roi >= config.roi_high_threshold else "rgba(255, 193, 7, 0.1)" if roi >= config.roi_medium_threshold else "transparent"
                risk = opp['risk_score']
                risk_display = f"🟢 {risk:.2f} (Low)" if risk <= 0.2 else f"🟡 {risk:.2f} (Med)" if risk <= 0.4 else f"🔴 {risk:.2f} (High)"

                with st.container():
                    if bg_color != "transparent":
                        st.markdown(f'<div style="background-color: {bg_color}; padding: 10px; border-radius: 5px; margin-bottom: 5px;">', unsafe_allow_html=True)
                    r_col1, r_col2, r_col3, r_col4, r_col5 = st.columns([0.5, 3, 1.2, 1.2, 1.3])
                    with r_col1:
                        if st.button("👁️", key=f"view_{opp['market_id']}_{i}"):
                            st.session_state.selected_market_id = opp['market_id']
                            st.rerun()
                    with r_col2:
                        render_category_badge(opp.get('category'))
                        st.markdown(f"**{format_market_title(opp['market_name'])}**")
                        if opp.get('expires_at'):
                            try:
                                exp_dt = datetime.fromisoformat(opp['expires_at'])
                                st.caption(f"Expires: {format_expiry_date(exp_dt)}")
                            except: pass
                    r_col3.write(f"${opp['expected_profit']:.2f}")
                    r_col4.write(f"{roi:.2f}%")
                    r_col5.write(risk_display)
                    if bg_color != "transparent":
                        st.markdown("</div>", unsafe_allow_html=True)
                st.divider()
        else:
            st.info("No opportunities detected yet. Use the controls below to scan.")

    if drawer_col and st.session_state.selected_market_id:
        with drawer_col:
            source = get_data_source(current_mode_key)
            render_market_detail_drawer(st.session_state.selected_market_id, source)

    st.markdown("---")
    render_control_buttons(current_mode_key)

def render_control_buttons(mode_key: str):
    """Render manual scan/generate buttons."""
    if mode_key == "mock":
        st.subheader("🎮 Mock Controls")
        if st.button("🔄 Generate Data", type="primary"):
            run_data_cycle("mock")
            st.rerun()
    else:
        st.subheader("📡 Live Controls")
        if st.button("📡 Scan Live Markets", type="primary"):
            with st.spinner("Fetching live data..."):
                run_data_cycle("live")
            st.rerun()

def run_data_cycle(mode_key: str):
    """Run a single cycle of data fetching and arbitrage detection."""
    from app.core.logger import log_event, init_db
    init_db()
    source = get_data_source(mode_key)
    markets = source.get_markets(limit=20)
    
    for market in markets:
        record_market_tick(market_id=market.id, yes_price=market.yes_price, no_price=market.no_price, volume=market.volume_24h)

    detector = ArbitrageDetector()
    opportunities = detector.detect_opportunities(markets)
    from app.core.notifications import send_alert
    
    for opp in opportunities:
        opp.mode = mode_key
        detector.save_opportunity(opp)
        send_alert(opp.to_dict())
        log_event({
            "timestamp": opp.detected_at.isoformat(),
            "market_id": opp.market_id,
            "market_name": opp.market_name,
            "opportunity_type": opp.opportunity_type,
            "yes_price": opp.positions[0]["price"] if opp.positions else 0,
            "no_price": opp.positions[1]["price"] if len(opp.positions) > 1 else 0,
            "sum": sum(p["price"] for p in opp.positions),
            "expected_profit_pct": opp.expected_return_pct,
            "mode": mode_key,
            "decision": "alerted",
            "mock_result": "success" if mode_key == "mock" else None,
            "latency_ms": 0,
            "expires_at": opp.expires_at.isoformat() if opp.expires_at else None,
            "category": opp.category
        })
