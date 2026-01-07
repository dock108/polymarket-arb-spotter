"""
History view for viewing past arbitrage opportunities.

Displays recent arbitrage events from the database with filtering
and export functionality.
"""

from datetime import datetime
from typing import Any, Dict

import pandas as pd
import streamlit as st

from app.core.logger import fetch_recent


def render_history_view():
    """
    Render the history view page with filters.

    Shows logged arbitrage events with decision filter and profit filter.
    Includes failure reasons chart for debugging detection issues.
    """
    st.title("📜 Opportunity History")
    st.markdown("---")

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        _ = st.selectbox(
            "Time Range", ["All Time", "Last 24 Hours", "Last 7 Days", "Last 30 Days"]
        )

    with col2:
        decision_filter = st.selectbox("Decision", ["All", "Alerted", "Ignored"])

    with col3:
        min_profit = st.number_input("Min Profit %", min_value=0.0, value=0.0, step=0.1)

    st.markdown("---")

    # Fetch history
    events = fetch_recent(limit=1000)

    # Apply filters
    if decision_filter != "All":
        events = [
            e
            for e in events
            if e.get("decision", "").lower() == decision_filter.lower()
        ]

    if min_profit > 0:
        events = [e for e in events if e.get("expected_profit_pct", 0) >= min_profit]

    # Statistics
    st.subheader("Summary Statistics")

    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)

    with stat_col1:
        st.metric("Total Events", len(events))

    with stat_col2:
        alerted = sum(1 for e in events if e.get("decision") == "alerted")
        st.metric("Alerted", alerted)

    with stat_col3:
        if events:
            avg_profit = sum(e.get("expected_profit_pct", 0) for e in events) / len(
                events
            )
            st.metric("Avg Profit %", f"{avg_profit:.2f}%")
        else:
            st.metric("Avg Profit %", "0.00%")

    with stat_col4:
        failures = sum(1 for e in events if e.get("failure_reason"))
        st.metric("Failures", failures)

    st.markdown("---")

    # History table
    st.subheader("Event History")

    if events:
        df = pd.DataFrame(events)

        # Select relevant columns
        display_cols = [
            "timestamp",
            "market_name",
            "expected_profit_pct",
            "decision",
            "mode",
            "failure_reason",
        ]
        df_display = df[[col for col in display_cols if col in df.columns]].copy()

        # Rename columns
        column_names = {
            "timestamp": "Time",
            "market_name": "Market",
            "expected_profit_pct": "Profit %",
            "decision": "Decision",
            "mode": "Mode",
            "failure_reason": "Failure Reason",
        }
        df_display.columns = [column_names.get(col, col) for col in df_display.columns]

        st.dataframe(df_display, use_container_width=True)

        # Export option
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
