"""
Alerts History and background notification handler.
"""

import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.core.config import config
from app.core.notifications import get_notification_service
from app.ui.utils import format_market_title, format_expiry_date, render_category_badge

def render_alerts_view():
    """Render the alerts history panel."""
    st.title("🔔 Alerts History")
    
    notification_service = get_notification_service()
    
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("Review recent arbitrage signals that matched your alert rules.")
    with col2:
        if st.button("🗑️ Clear All"):
            notification_service.clear_all_alerts()
            st.success("Alerts cleared!")
            st.rerun()
            
    st.markdown("---")
    
    # We want to show alerts for the current mode
    current_mode_key = "live" if st.session_state.get("mode") == "Live Read-Only" else "mock"
    alerts = notification_service.get_recent_alerts(mode=current_mode_key)
    
    if not alerts:
        st.info("No alerts found for this mode. Signals that meet your ROI and Liquidity rules will appear here.")
        return
        
    # Mark as seen when viewing the panel
    notification_service.mark_all_as_seen()
    
    for alert in alerts:
        with st.container():
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                render_category_badge(alert.get('category'))
                st.markdown(f"**{format_market_title(alert['market_name'])}**")
                
                exp_date = alert.get('expires_at')
                if exp_date:
                    try:
                        exp_dt = datetime.fromisoformat(exp_date)
                        st.caption(f"Expires: {format_expiry_date(exp_dt)}")
                    except:
                        pass
                st.caption(f"{alert['timestamp']} • {alert['reason']}")
            with c2:
                st.markdown(f"**ROI: {alert['roi']:.2f}%**")
            with c3:
                if st.button("Inspect 🔍", key=f"inspect_alert_{alert['id']}"):
                    st.session_state.selected_market_id = alert['market_id']
                    st.session_state.selected_page = "Dashboard"
                    st.rerun()
            st.divider()

def render_notification_handler():
    """Handle background notifications (toasts and sounds)."""
    notification_service = get_notification_service()
    
    if "announced_alert_ids" not in st.session_state:
        st.session_state.announced_alert_ids = set()
        
    current_mode_key = "live" if st.session_state.get("mode") == "Live Read-Only" else "mock"
    recent_alerts = notification_service.get_recent_alerts(limit=5, mode=current_mode_key)
    
    new_alerts = [a for a in recent_alerts if a['id'] not in st.session_state.announced_alert_ids]
    
    if new_alerts:
        for alert in new_alerts:
            if config.alert_banner_enabled:
                st.toast(f"🚨 **New Arb Opportunity**\n\n{alert['market_name']} — ROI: {alert['roi']:.2f}%", icon="🎯")
            
            if config.alert_sound_enabled:
                sound_html = """
                <audio autoplay style="display:none;">
                  <source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg">
                </audio>
                """
                components.html(sound_html, height=0)
                
            st.session_state.announced_alert_ids.add(alert['id'])
