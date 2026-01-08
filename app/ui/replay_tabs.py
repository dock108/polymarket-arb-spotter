"""
Tab renderers for the Replay View.
Splitting these out to keep file sizes manageable.
"""

import pandas as pd
import streamlit as st
import altair as alt
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.core.arb_detector import ArbitrageDetector
from app.core.logger import (
    fetch_history_labels,
    fetch_price_alert_events,
    fetch_depth_events,
    save_history_label,
    delete_history_label,
    fetch_user_annotations,
    save_user_annotation,
    delete_user_annotation,
    logger,
)
from app.ui.utils import format_market_title, format_expiry_date, render_category_badge

LABEL_TYPES = ["news-driven move", "whale entry", "arb collapse", "false signal"]
ANNOTATION_TAGS = ["Untradeable", "False Positive", "Executed"]

def render_price_chart_tab(df: pd.DataFrame, market_id: str, start_date: datetime, end_date: datetime):
    """Render the price chart tab with historical data and signal overlays."""
    st.markdown("### 📈 Price History")

    # Chart options
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        chart_type = st.radio("Chart Type", ["Yes & No Prices", "Yes Price Only", "No Price Only"], horizontal=True)
    with col2:
        show_volume = st.checkbox("Show Volume", value=True)
        show_signals = st.checkbox("Show Signals", value=True)
    with col3:
        annotation_mode = st.toggle("✎ Annotation Mode", key="annotation_mode_toggle")
        show_annotations = st.checkbox("Show Annotations", value=True)
    with col4:
        if st.button("🔄 Clear Replay Focus"):
            if "replay_market_id" in st.session_state: del st.session_state.replay_market_id
            if "replay_timestamp" in st.session_state: del st.session_state.replay_timestamp
            st.rerun()

    detector = ArbitrageDetector()
    current_mode_key = "live" if st.session_state.get("mode") == "Live Read-Only" else "mock"
    signals = detector.get_opportunities_for_market(market_id, start_date, end_date, mode=current_mode_key)
    
    user_annotations = fetch_user_annotations(market_id=market_id, start=start_date.isoformat(), end=end_date.isoformat(), mode=current_mode_key)

    plot_df = df.copy()
    base = alt.Chart(plot_df).encode(x=alt.X("timestamp:T", title="Time"))
    click_selection = alt.selection_point(name="chart_click", on="click", nearest=True, fields=["timestamp"], empty=False)

    lines = []
    if chart_type in ["Yes & No Prices", "Yes Price Only"]:
        lines.append(base.mark_line(color="#1f77b4", opacity=0.8).encode(y=alt.Y("yes_price:Q", title="Price", scale=alt.Scale(zero=False))))
    if chart_type in ["Yes & No Prices", "No Price Only"]:
        lines.append(base.mark_line(color="#ff7f0e", opacity=0.8).encode(y=alt.Y("no_price:Q", title="Price", scale=alt.Scale(zero=False))))

    chart = alt.layer(*lines)

    if show_signals and signals:
        sig_df = pd.DataFrame(signals)
        sig_df["timestamp"] = pd.to_datetime(sig_df["detected_at"])
        sig_df = pd.merge_asof(sig_df.sort_values("timestamp"), plot_df[["timestamp", "yes_price", "no_price"]].sort_values("timestamp"), on="timestamp", direction="nearest")
        
        # Volatility Logic
        from app.core.config import config
        from app.core.narrative import get_hint
        def get_vol_cat(v):
            v_val = abs(v - 1.0)
            if v_val < 0.005: return "Very Low"
            if v_val < 0.01: return "Low"
            if v_val < 0.02: return "Medium"
            if v_val < 0.05: return "High"
            return "Extreme"
        
        sig_df["volatility_label"] = (sig_df["yes_price"] + sig_df["no_price"]).apply(get_vol_cat)
        
        focus_ts = st.session_state.get("replay_timestamp")
        if focus_ts:
            focus_dt = pd.to_datetime(focus_ts)
            sig_df["is_focused"] = (sig_df["timestamp"] - focus_dt).abs() < pd.Timedelta(seconds=1)
            if not sig_df[sig_df["is_focused"]].empty:
                roi = sig_df[sig_df["is_focused"]].iloc[0]["expected_return_pct"]
                st.toast(f"🎯 Arb detected — ROI: {roi:.2f}%", icon="🎯")
        else:
            sig_df["is_focused"] = False

        markers = alt.Chart(sig_df[~sig_df["is_focused"]]).mark_point(size=100, filled=True, stroke="white", strokeWidth=1).encode(
            x="timestamp:T", y="yes_price:Q", color=alt.Color("expected_return_pct:Q", scale=alt.Scale(scheme="viridis"), title="ROI %"),
            tooltip=[alt.Tooltip("detected_at:T", title="Time"), alt.Tooltip("expected_return_pct:Q", title="ROI %", format=".2f"), alt.Tooltip("volatility_label:N", title="Volatility")]
        )
        
        focus_marker = alt.Chart(sig_df[sig_df["is_focused"]]).mark_point(size=300, filled=True, stroke="red", strokeWidth=3).encode(
            x="timestamp:T", y="yes_price:Q", color=alt.value("red"),
            tooltip=[alt.Tooltip("detected_at:T", title="FOCUS: Time"), alt.Tooltip("expected_return_pct:Q", title="ROI %", format=".2f")]
        )
        chart = chart + markers + focus_marker

    if show_annotations and user_annotations:
        ann_df = pd.DataFrame(user_annotations)
        ann_df["timestamp"] = pd.to_datetime(ann_df["timestamp"])
        ann_df = pd.merge_asof(ann_df.sort_values("timestamp"), plot_df[["timestamp", "yes_price"]].sort_values("timestamp"), on="timestamp", direction="nearest")
        pins = alt.Chart(ann_df).mark_text(text="📍", size=20, dy=-10).encode(
            x="timestamp:T", y="yes_price:Q", tooltip=[alt.Tooltip("tag:N", title="Tag"), alt.Tooltip("comment:N", title="Comment")]
        )
        chart = chart + pins

    if annotation_mode: chart = chart.add_params(click_selection)

    if show_volume and "volume" in plot_df.columns:
        vol_bars = base.mark_bar(color="#7f7f7f", opacity=0.3).encode(y=alt.Y("volume:Q", title="Volume (24h)", axis=alt.Axis(orient="right")))
        combined = alt.layer(chart, vol_bars).resolve_scale(y='independent')
        chart_result = st.altair_chart(combined.interactive(), use_container_width=True, on_select="rerun")
    else:
        chart_result = st.altair_chart(chart.interactive(), use_container_width=True, on_select="rerun")

    if annotation_mode:
        selected = chart_result.get("selection", {}).get("chart_click", [])
        if selected:
            ts = selected[0].get("timestamp")
            if ts:
                st.markdown("### 📝 Add Annotation")
                with st.form("add_annotation_form"):
                    tag = st.selectbox("Tag", ANNOTATION_TAGS)
                    comment = st.text_area("Comment (Optional)")
                    if st.form_submit_button("💾 Save Annotation"):
                        save_user_annotation({"market_id": market_id, "timestamp": ts, "tag": tag, "comment": comment, "mode": current_mode_key})
                        st.success("Annotation saved!")
                        st.rerun()

def render_annotation_tab(df: pd.DataFrame, market_id: str, start_date: datetime, end_date: datetime):
    """Render the manual labeling form tab."""
    st.markdown("### 🏷️ Add Pattern Label")
    st.info("💡 Use this to build a labeled dataset for training models.")
    with st.form("annotation_form"):
        col1, col2 = st.columns(2)
        with col1:
            l_date = st.date_input("Date", value=start_date.date())
            l_time = st.time_input("Time", value=datetime.now().time())
        with col2:
            l_type = st.selectbox("Label Type", LABEL_TYPES)
        notes = st.text_area("Notes (Optional)")
        if st.form_submit_button("💾 Save Label"):
            l_ts = datetime.combine(l_date, l_time)
            save_history_label({"timestamp": l_ts, "market_id": market_id, "label_type": l_type, "notes": notes})
            st.success("Label saved!")
            st.rerun()

def render_labels_tab(market_id: str, start_date: datetime, end_date: datetime):
    """Render the view/manage labels tab."""
    st.markdown("### 📋 All Labels for This Market")
    labels = fetch_history_labels(market_id=market_id, start=start_date.isoformat(), end=end_date.isoformat())
    if labels:
        df_labels = pd.DataFrame(labels)
        st.dataframe(df_labels[["timestamp", "label_type", "notes"]], use_container_width=True)
        if st.button("🗑️ Bulk Delete (Market Range)"):
            for l in labels: delete_history_label(l["id"])
            st.success("Labels cleared")
            st.rerun()
    else:
        st.info("No labels found.")
