"""
Pattern labeling interface for historical market replay.

Allows users to:
- Choose market + date range
- Replay chart + events timeline
- Annotate labels manually
- Persist labels to database
"""

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from app.core.history_store import get_market_ids, get_ticks
from app.core.logger import (
    fetch_history_labels,
    fetch_price_alert_events,
    fetch_depth_events,
    save_history_label,
    delete_history_label,
    init_db,
    logger,
)


# Label types available for annotation
LABEL_TYPES = [
    "news-driven move",
    "whale entry",
    "arb collapse",
    "false signal",
]

# UI display constants
MAX_MARKET_DISPLAY_LENGTH = 30
MAX_MARKET_ID_FILENAME_LENGTH = 10


def render_replay_view():
    """
    Render the pattern labeling replay view.

    Displays historical market data with annotation capabilities
    for building a labeled dataset.
    """
    st.title("🎬 Pattern Labeling - Replay View")
    st.markdown("---")

    # Initialize database
    init_db()

    # Sidebar controls for market and date range selection
    st.sidebar.subheader("📋 Replay Controls")

    # Get available markets
    available_markets = get_market_ids()

    if not available_markets:
        st.warning(
            "⚠️ No historical data available. "
            "Please run the data collection script first to populate the history store."
        )
        return

    # Market selection
    selected_market = st.sidebar.selectbox(
        "Select Market",
        available_markets,
        help="Choose a market to replay and annotate",
    )

    # Date range selection
    st.sidebar.markdown("### 📅 Date Range")

    # Default to last 7 days
    default_end = datetime.now()
    default_start = default_end - timedelta(days=7)

    date_range = st.sidebar.date_input(
        "Select Date Range",
        value=(default_start.date(), default_end.date()),
        help="Choose the date range for replay",
    )

    # Handle date range input
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date = datetime.combine(date_range[0], datetime.min.time())
        end_date = datetime.combine(date_range[1], datetime.max.time())
    else:
        start_date = default_start
        end_date = default_end

    st.sidebar.markdown("---")

    # Display selected parameters
    st.sidebar.info(
        f"**Market:** {selected_market[:MAX_MARKET_DISPLAY_LENGTH]}...\n\n"
        f"**Range:** {start_date.date()} to {end_date.date()}"
    )

    # Main content area
    st.subheader(f"📊 Market Replay: {selected_market}")

    # Fetch historical ticks for the selected market and date range
    ticks = get_ticks(
        market_id=selected_market,
        start=start_date,
        end=end_date,
        limit=10000,
    )

    if not ticks:
        st.warning(
            f"No tick data found for market **{selected_market}** "
            f"in the selected date range."
        )
        return

    st.info(f"📈 Loaded {len(ticks)} data points")

    # Convert ticks to DataFrame for charting
    df = pd.DataFrame(ticks)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Create tabs for different views
    tab1, tab2, tab3 = st.tabs(["📈 Price Chart", "🏷️ Annotate", "📋 View Labels"])

    with tab1:
        _render_price_chart_tab(df, selected_market, start_date, end_date)

    with tab2:
        _render_annotation_tab(df, selected_market, start_date, end_date)

    with tab3:
        _render_labels_tab(selected_market, start_date, end_date)

    # Footer
    st.markdown("---")
    st.caption(
        f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        f"Data points: {len(ticks)}"
    )


def _render_price_chart_tab(
    df: pd.DataFrame,
    market_id: str,
    start_date: datetime,
    end_date: datetime,
):
    """
    Render the price chart tab with historical data.

    Args:
        df: DataFrame with tick data
        market_id: Market identifier
        start_date: Start of date range
        end_date: End of date range
    """
    st.markdown("### 📈 Price History")

    # Chart options
    col1, col2 = st.columns([3, 1])

    with col1:
        chart_type = st.radio(
            "Chart Type",
            ["Yes & No Prices", "Yes Price Only", "No Price Only"],
            horizontal=True,
        )

    with col2:
        show_volume = st.checkbox("Show Volume", value=False)

    # Prepare data for charting
    chart_df = df.set_index("timestamp")

    # Plot based on selection
    if chart_type == "Yes & No Prices":
        st.line_chart(chart_df[["yes_price", "no_price"]])
    elif chart_type == "Yes Price Only":
        st.line_chart(chart_df[["yes_price"]])
    else:
        st.line_chart(chart_df[["no_price"]])

    if show_volume and "volume" in chart_df.columns:
        st.markdown("#### Volume")
        st.line_chart(chart_df[["volume"]])

    # Fetch all events: labels, alerts, and depth signals
    labels = fetch_history_labels(
        market_id=market_id,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
    )

    alerts = fetch_price_alert_events(
        market_id=market_id,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
    )

    depth_signals = fetch_depth_events(
        market_id=market_id,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
    )

    # Combine all events into a unified timeline
    all_events = []

    # Add labels
    for label in labels:
        all_events.append(
            {
                "timestamp": label["timestamp"],
                "event_type": "Label",
                "detail": label["label_type"],
                "notes": label.get("notes", ""),
                "emoji": {
                    "news-driven move": "📰",
                    "whale entry": "🐋",
                    "arb collapse": "📉",
                    "false signal": "❌",
                }.get(label["label_type"], "🏷️"),
            }
        )

    # Add alerts
    for alert in alerts:
        direction = alert.get("direction", "")
        target_price = alert.get("target_price", 0)
        all_events.append(
            {
                "timestamp": alert["timestamp"],
                "event_type": "Price Alert",
                "detail": f"{direction} {target_price:.3f}",
                "notes": f"Triggered at {alert.get('trigger_price', 0):.3f}",
                "emoji": "🔔",
            }
        )

    # Add depth signals
    for depth in depth_signals:
        signal_type = depth.get("signal_type", "")
        threshold = depth.get("threshold_hit", "")
        all_events.append(
            {
                "timestamp": depth["timestamp"],
                "event_type": "Depth Signal",
                "detail": signal_type,
                "notes": threshold,
                "emoji": {
                    "thin_depth": "📊",
                    "large_gap": "↔️",
                    "strong_imbalance": "⚖️",
                }.get(signal_type, "📈"),
            }
        )

    if all_events:
        st.markdown("### 🎯 Events Timeline (Labels + Alerts + Depth Signals)")

        # Create a DataFrame for all events
        events_df = pd.DataFrame(all_events)
        events_df["timestamp"] = pd.to_datetime(events_df["timestamp"])
        events_df = events_df.sort_values("timestamp", ascending=False)

        # Display as table
        display_df = events_df[["timestamp", "event_type", "detail", "notes"]].copy()
        display_df.columns = ["Time", "Type", "Detail", "Notes"]
        st.dataframe(display_df, use_container_width=True)

        # Show events on timeline with visual markers
        st.markdown("#### 📍 Event Markers")
        for _, event in events_df.iterrows():
            timestamp = event["timestamp"]
            event_type = event["event_type"]
            detail = event["detail"]
            notes = event.get("notes", "")
            emoji = event.get("emoji", "📌")

            st.text(
                f"{emoji} {timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {event_type}: {detail}"
                + (f" - {notes}" if notes else "")
            )


def _render_annotation_tab(
    df: pd.DataFrame,
    market_id: str,
    start_date: datetime,
    end_date: datetime,
):
    """
    Render the annotation tab for adding labels.

    Args:
        df: DataFrame with tick data
        market_id: Market identifier
        start_date: Start of date range
        end_date: End of date range
    """
    st.markdown("### 🏷️ Add Pattern Label")

    st.info(
        "💡 Use this interface to annotate specific points in time with pattern labels. "
        "These labels will be stored in the database to build a training dataset."
    )

    # Annotation form
    with st.form("annotation_form"):
        col1, col2 = st.columns([1, 1])

        with col1:
            # Timestamp selection
            label_date = st.date_input(
                "Date",
                value=start_date.date(),
                min_value=start_date.date(),
                max_value=end_date.date(),
            )

            label_time = st.time_input(
                "Time",
                value=datetime.now().time(),
            )

        with col2:
            # Label type selection
            label_type = st.selectbox(
                "Label Type",
                LABEL_TYPES,
                help="Select the pattern type you're annotating",
            )

        # Notes field
        notes = st.text_area(
            "Notes (Optional)",
            placeholder="Add any relevant notes about this pattern...",
            help="Additional context or observations about this labeled event",
        )

        # Submit button
        submitted = st.form_submit_button("💾 Save Label", type="primary")

        if submitted:
            # Combine date and time
            label_timestamp = datetime.combine(label_date, label_time)

            # Validate timestamp is within range
            if label_timestamp < start_date or label_timestamp > end_date:
                st.error(
                    "⚠️ Timestamp must be within the selected date range. "
                    f"({start_date.date()} to {end_date.date()})"
                )
            else:
                # Save label to database
                label_data = {
                    "timestamp": label_timestamp,
                    "market_id": market_id,
                    "label_type": label_type,
                    "notes": notes or "",
                }

                try:
                    save_history_label(label_data)
                    st.success(
                        f"✅ Label saved successfully!\n\n"
                        f"**Type:** {label_type}\n\n"
                        f"**Time:** {label_timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    st.balloons()
                except Exception as e:
                    st.error(f"❌ Error saving label: {str(e)}")
                    logger.error(f"Error saving label: {e}", exc_info=True)

    # Show recent labels
    st.markdown("---")
    st.markdown("### 📋 Recent Labels for This Market")

    recent_labels = fetch_history_labels(
        market_id=market_id,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
        limit=10,
    )

    if recent_labels:
        for label in recent_labels:
            with st.expander(
                f"🏷️ {label['label_type']} - {label['timestamp']}", expanded=False
            ):
                st.write(f"**Timestamp:** {label['timestamp']}")
                st.write(f"**Type:** {label['label_type']}")
                if label.get("notes"):
                    st.write(f"**Notes:** {label['notes']}")

                # Delete button
                if st.button("🗑️ Delete", key=f"delete_{label['id']}", type="secondary"):
                    if delete_history_label(label["id"]):
                        st.success("Label deleted successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to delete label")
    else:
        st.info("No labels found for this market in the selected date range.")


def _render_labels_tab(market_id: str, start_date: datetime, end_date: datetime):
    """
    Render the view labels tab.

    Args:
        market_id: Market identifier
        start_date: Start of date range
        end_date: End of date range
    """
    st.markdown("### 📋 All Labels for This Market")

    # Filters
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        label_filter = st.selectbox(
            "Filter by Label Type",
            ["All"] + LABEL_TYPES,
        )

    with col2:
        sort_order = st.radio(
            "Sort Order",
            ["Newest First", "Oldest First"],
            horizontal=True,
        )

    # Fetch labels
    labels = fetch_history_labels(
        market_id=market_id,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
        limit=1000,
    )

    # Apply filters
    if label_filter != "All":
        labels = [label for label in labels if label["label_type"] == label_filter]

    # Sort
    if sort_order == "Oldest First":
        labels = sorted(labels, key=lambda x: x["timestamp"])

    # Display statistics
    if labels:
        st.markdown("#### 📊 Statistics")

        stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)

        with stat_col1:
            st.metric("Total Labels", len(labels))

        with stat_col2:
            news_driven = sum(
                1 for label in labels if label["label_type"] == "news-driven move"
            )
            st.metric("News-Driven", news_driven)

        with stat_col3:
            whale_entry = sum(
                1 for label in labels if label["label_type"] == "whale entry"
            )
            st.metric("Whale Entry", whale_entry)

        with stat_col4:
            arb_collapse = sum(
                1 for label in labels if label["label_type"] == "arb collapse"
            )
            st.metric("Arb Collapse", arb_collapse)

        st.markdown("---")

        # Display labels table
        st.markdown("#### 🗂️ Labels List")

        labels_df = pd.DataFrame(labels)
        labels_df["timestamp"] = pd.to_datetime(labels_df["timestamp"])

        # Select columns for display
        display_cols = ["timestamp", "label_type", "notes"]
        if "id" in labels_df.columns:
            display_cols.insert(0, "id")

        display_df = labels_df[display_cols].copy()
        display_df.columns = [col.replace("_", " ").title() for col in display_cols]

        st.dataframe(display_df, use_container_width=True)

        # Export option
        if st.button("📥 Export Labels to CSV"):
            csv = display_df.to_csv(index=False)
            # Truncate market ID for filename to avoid overly long filenames
            market_id_short = market_id[:MAX_MARKET_ID_FILENAME_LENGTH]
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"labels_{market_id_short}_{timestamp_str}.csv"
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=filename,
                mime="text/csv",
            )

        # Bulk delete option
        st.markdown("---")
        st.markdown("#### 🗑️ Bulk Actions")

        with st.expander("⚠️ Danger Zone - Delete All Labels", expanded=False):
            st.warning(
                "This will delete all labels for this market in the selected date range. "
                "This action cannot be undone!"
            )

            confirm_text = st.text_input(
                "Type 'DELETE' to confirm:",
                key="confirm_delete",
            )

            if st.button("Delete All Labels", type="secondary"):
                if confirm_text == "DELETE":
                    deleted_count = 0
                    for label in labels:
                        if delete_history_label(label["id"]):
                            deleted_count += 1

                    st.success(f"Deleted {deleted_count} labels")
                    st.rerun()
                else:
                    st.error("Please type 'DELETE' to confirm")

    else:
        st.info(
            "No labels found for this market in the selected date range. "
            "Use the 'Annotate' tab to add labels."
        )


if __name__ == "__main__":
    render_replay_view()
