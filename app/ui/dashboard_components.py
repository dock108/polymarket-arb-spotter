"""
Shared UI components for the Dashboard.
"""

import streamlit as st
from typing import Dict, Any, Optional
from app.core.narrative import get_hint
from app.ui.utils import format_market_title, format_expiry_date, render_category_badge
from datetime import datetime

def render_metric_cards(summary: Dict[str, Any], active_count: int, avg_return: float, total_profit: float):
    """Render the high-level summary cards at the top of the dashboard."""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        val = summary.get("opportunities_this_week", active_count)
        st.metric("Opportunities (7d)", val)

    with col2:
        val = summary.get("average_roi", f"{avg_return:.2f}%")
        st.metric("Avg ROI (7d)", val)

    with col3:
        top_sig = summary.get("top_signal_type")
        if top_sig:
            st.metric("Top Signal", top_sig["name"], help=f"{get_hint('top_signal_intro')} | Win Rate: {top_sig['win_rate']}")
        else:
            st.metric("Top Signal", "N/A", help=get_hint("empty_history"))

    with col4:
        st.metric("Potential Profit", f"${total_profit:.2f}", help=get_hint("untradeable_warning"))

def render_top_opportunity(top_opp: Dict[str, Any]):
    """Render the featured top opportunity card."""
    st.info("⭐ **TOP OPPORTUNITY**")
    t_col1, t_col2, t_col3, t_col4 = st.columns([3, 1, 1, 1])
    with t_col1:
        render_category_badge(top_opp.get('category'))
        st.markdown(f"**{format_market_title(top_opp['market_name'])}**")
        
        exp_date = top_opp.get('expires_at')
        if exp_date:
            try:
                exp_dt = datetime.fromisoformat(exp_date)
                st.caption(f"Expires: {format_expiry_date(exp_dt)}")
            except:
                pass
        st.caption("Highest return available right now.")
    with t_col2:
        st.metric("ROI", f"{top_opp['expected_return_pct']:.2f}%")
    with t_col3:
        st.metric("Profit", f"${top_opp['expected_profit']:.2f}")
    with t_col4:
        if st.button("Inspect Top 🔍", key="inspect_top", type="primary"):
            st.session_state.selected_market_id = top_opp['market_id']
            st.rerun()
