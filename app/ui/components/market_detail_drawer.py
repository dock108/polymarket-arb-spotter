"""
Market Detail Drawer component for Polymarket Arbitrage Spotter.
"""

import streamlit as st
from app.core.config import config
from app.core.data_source import DataSource
from app.ui.utils import format_market_title, format_expiry_date, render_category_badge
from datetime import datetime

def render_market_detail_drawer(market_id: str, data_source: DataSource):
    """
    Render a right-side detail panel for a specific market.
    """
    # Header with close button
    col_title, col_close = st.columns([5, 1])
    with col_title:
        st.subheader("🔍 Market Details")
    with col_close:
        if st.button("X", key="close_drawer"):
            st.session_state.selected_market_id = None
            st.rerun()

    # Fetch market details
    with st.spinner("Fetching market data..."):
        market = data_source.get_market_details(market_id)

    if not market:
        st.error(f"Market details not found for ID: {market_id}")
        return

    # Market Title
    render_category_badge(market.category)
    st.markdown(f"### {format_market_title(market.title)}")
    
    if market.expires_at:
        st.caption(f"**Expires:** {format_expiry_date(market.expires_at)}")
    
    # Prices
    p_col1, p_col2 = st.columns(2)
    with p_col1:
        st.metric("YES Price", f"${market.yes_price:.2f}" if market.yes_price is not None else "N/A")
    with p_col2:
        st.metric("NO Price", f"${market.no_price:.2f}" if market.no_price is not None else "N/A")

    # Gap calculation
    gap = 0.0
    if market.yes_price is not None and market.no_price is not None:
        gap = abs(market.yes_price + market.no_price - 1.0) * 100
        # Wait, the requirement says "Gap % (absolute pricing difference)"
        # Usually arbitrage is sum < 1.0 or sum > 1.0. 
        # But the prompt says "Math.abs(yes_price - no_price) * 100" - which is weird for arb.
        # Arbitrage gap is usually abs(1.0 - (yes_price + no_price)) * 100.
        # I'll stick to what the user explicitly asked for in Step 3 of instructions:
        # const gap = Math.abs(yes_price - no_price) * 100
        gap = abs(market.yes_price - market.no_price) * 100
        
    st.metric("Gap %", f"{gap:.2f}%")

    # Liquidity
    liquidity_str = "N/A"
    if market.liquidity:
        liquidity_str = f"${market.liquidity:,.2f}"
    
    from app.core.narrative import get_hint
    liq_help = get_hint("liquidity_thin") if market.liquidity and market.liquidity < 1000 else get_hint("liquidity_deep")
    st.metric("Available Liquidity", liquidity_str, help=liq_help)

    # Expected Profit
    # DEFAULT_STAKE * (gap / 100) per Step 3
    expected_profit = config.default_stake * (gap / 100)
    
    profit_help = None
    if gap > 10 and market.liquidity and market.liquidity < 500:
        profit_help = get_hint("untradeable_warning")
        
    st.metric(f"Expected Profit (Stake: ${config.default_stake})", f"${expected_profit:.2f}", help=profit_help)

    st.markdown("---")

    # Polymarket URL
    market_url = None
    if market.slug:
        market_url = f"{config.polymarket_base_url}{market.slug}"
    elif market.id:
        market_url = f"https://polymarket.com/market/{market.id}"

    if market_url:
        st.link_button("Open in Polymarket →", market_url, type="primary", use_container_width=True)
    else:
        st.button("Open in Polymarket →", disabled=True, use_container_width=True, help="Market URL not available")

    # Last Updated
    if market.last_updated:
        st.caption(f"Last updated: {market.last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        st.caption("Last updated: N/A")
