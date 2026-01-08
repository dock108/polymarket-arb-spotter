"""
History view for viewing past arbitrage opportunities.

Displays recent arbitrage events from the database with filtering
and export functionality.
"""

from datetime import datetime
from typing import Any, Dict

import pandas as pd
import streamlit as st

from app.core.arb_detector import ArbitrageDetector
from app.core.signals.outcome_tracker import update_all_pending_outcomes
from app.ui.utils import format_market_title, format_expiry_date, render_category_badge


def render_history_view():
    """
    Render the history view page with filters.

    Shows logged arbitrage events with decision filter and profit filter.
    Includes failure reasons chart for debugging detection issues.
    """
    st.title("📜 Opportunity History")
    
    # Audit Controls
    with st.expander("🛠️ Signal Audit Controls", expanded=False):
        if st.button("🔄 Refresh Signal Outcomes", help="Evaluate 5m/30m performance for all signals"):
            with st.spinner("Analyzing historical price paths..."):
                update_all_pending_outcomes()
            st.success("Signal outcomes updated!")
            st.rerun()

    st.markdown("---")

    # Filters
    col1, col2, col3 = st.columns(3)

    detector = ArbitrageDetector()

    with col1:
        _ = st.selectbox(
            "Time Range", ["All Time", "Last 24 Hours", "Last 7 Days", "Last 30 Days"]
        )

    with col2:
        decision_filter = st.selectbox("Type", ["All", "two-way", "synthetic"])

    with col3:
        min_profit = st.number_input("Min ROI %", min_value=0.0, value=0.0, step=0.1)

    st.markdown("---")

    # Fetch history
    current_mode_key = "live" if st.session_state.get("mode") == "Live Read-Only" else "mock"
    events = detector.get_recent_opportunities(limit=1000, mode=current_mode_key)

    # Apply filters
    if decision_filter != "All":
        events = [
            e
            for e in events
            if e.get("opportunity_type", "").lower() == decision_filter.lower()
        ]

    if min_profit > 0:
        events = [e for e in events if e.get("expected_return_pct", 0) >= min_profit]

    # Statistics
    st.subheader("Summary Statistics")

    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)

    with stat_col1:
        st.metric("Total Events", len(events))

    with stat_col2:
        profitable = sum(1 for e in events if e.get("outcome", {}).get("window_30m", {}).get("classification") == "remained_profitable")
        st.metric("Remained Profitable (30m)", profitable)

    with stat_col3:
        if events:
            avg_profit = sum(e.get("expected_return_pct", 0) for e in events) / len(
                events
            )
            st.metric("Avg ROI %", f"{avg_profit:.2f}%")
        else:
            st.metric("Avg ROI %", "0.00%")

    with stat_col4:
        collapsed = sum(1 for e in events if e.get("outcome", {}).get("window_5m", {}).get("classification") == "collapsed")
        st.metric("Collapsed (5m)", collapsed)

    st.markdown("---")

    # History table
    st.subheader("Event History")

    if events:
        df = pd.DataFrame(events)

        # Select relevant columns
        display_cols = [
            "detected_at",
            "market_name",
            "expected_return_pct",
            "opportunity_type",
            "risk_score",
        ]
        
        # Add Outcome Summary if available
        if "outcome" in df.columns:
            df["Outcome (30m)"] = df["outcome"].apply(
                lambda x: x.get("window_30m", {}).get("classification", "pending") if isinstance(x, dict) else "pending"
            )
            display_cols.append("Outcome (30m)")
            
        # Add Reason if available
        if "metadata" in df.columns:
            df["Reason"] = df["metadata"].apply(
                lambda x: x.get("reason_detected", "") if isinstance(x, dict) else ""
            )
            display_cols.append("Reason")

        # Table Header
        h_col1, h_col2, h_col3, h_col4, h_col5, h_col6 = st.columns([0.8, 2, 3, 1, 1, 1])
        h_col1.markdown("**Replay**")
        h_col2.markdown("**Time**")
        h_col3.markdown("**Market**")
        h_col4.markdown("**ROI %**")
        h_col5.markdown("**Type**")
        h_col6.markdown("**Risk**")
        st.markdown("---")

        for i, event in enumerate(events):
            r_col1, r_col2, r_col3, r_col4, r_col5, r_col6 = st.columns([0.8, 2, 3, 1, 1, 1])
            
            with r_col1:
                if st.button("▶", key=f"replay_{i}", help="Replay this opportunity"):
                    st.session_state.selected_page = "Replay & Label"
                    st.session_state.replay_market_id = event.get("market_id")
                    st.session_state.replay_timestamp = event.get("detected_at")
                    st.rerun()
            
            r_col2.write(event.get("detected_at", "N/A"))
            
            with r_col3:
                render_category_badge(event.get("category"))
                st.write(format_market_title(event.get("market_name", "N/A")))
                
                exp_date = event.get("expires_at")
                if exp_date:
                    try:
                        exp_dt = datetime.fromisoformat(exp_date)
                        st.caption(f"Expires: {format_expiry_date(exp_dt)}")
                    except:
                        pass

            r_col4.write(f"{event.get('expected_return_pct', 0):.2f}%")
            r_col5.write(event.get("opportunity_type", "N/A"))
            
            risk = event.get("risk_score", 0)
            risk_color = "🟢" if risk <= 0.2 else "🟡" if risk <= 0.4 else "🔴"
            r_col6.write(f"{risk_color} {risk:.2f}")
            
            # Optional outcome row
            outcome = event.get("outcome", {}).get("window_30m", {}).get("classification", "pending") if isinstance(event.get("outcome"), dict) else "pending"
            if outcome != "pending":
                st.caption(f"Outcome (30m): {outcome}")
            
            st.divider()

        # Export option
        df_display = df[[col for col in display_cols if col in df.columns]].copy()
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
        failure_counts: Dict[str, int] = {}
        for event in failures_with_reasons:
            reason = event.get("failure_reason", "Unknown")
            failure_counts[reason] = failure_counts.get(reason, 0) + 1

        failure_df = pd.DataFrame(
            list(failure_counts.items()), columns=["Reason", "Count"]
        )
        st.bar_chart(failure_df.set_index("Reason"))
    else:
        st.info("No failures recorded.")


def show_opportunity_detail_modal(opportunity: Dict[str, Any]):
    """
    Show detailed modal for a specific opportunity.

    Args:
        opportunity: Opportunity data dictionary

    Note: Placeholder for future modal dialog implementation.
    """
    st.write("### Opportunity Details")
    st.json(opportunity)


if __name__ == "__main__":
    render_history_view()
