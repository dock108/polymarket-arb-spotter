"""
Depth view for monitoring orderbook depth metrics.

Allows users to:
- View live depth metrics (total depth, bid-ask gaps, imbalances)
- Highlight thin books with color-coded indicators
- See recent depth alerts and events
- Edit depth configuration thresholds
"""

from datetime import datetime
from typing import Any, Dict

import pandas as pd
import streamlit as st

from app.core.depth_scanner import (
    DepthSignal,
    analyze_depth,
    detect_depth_signals,
    load_depth_config,
    save_depth_config,
    DEFAULT_CONFIG,
)
from app.core.logger import fetch_recent_depth_events, logger


def render_depth_view():
    """
    Render the depth view page.

    Displays live depth metrics, highlights thin books,
    lists recent alerts, and allows editing thresholds.
    """
    st.title("📊 Depth Monitor")
    st.markdown("---")

    # Load current configuration
    try:
        depth_config = load_depth_config()
    except Exception as e:
        logger.error(f"Error loading depth config: {e}")
        depth_config = DEFAULT_CONFIG.copy()

    # Create tabs for different sections
    tab1, tab2, tab3 = st.tabs(["📈 Live Metrics", "🔔 Recent Alerts", "⚙️ Thresholds"])

    with tab1:
        _render_live_metrics_tab(depth_config)

    with tab2:
        _render_recent_alerts_tab()

    with tab3:
        _render_thresholds_tab(depth_config)

    # Footer
    st.markdown("---")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def _render_live_metrics_tab(config: Dict[str, Any]):
    """
    Render the live depth metrics tab.

    Args:
        config: Depth configuration dictionary
    """
    st.subheader("Live Depth Metrics")
    st.info(
        "💡 This view displays sample depth metrics. "
        "Connect to a live data source to see real-time updates."
    )

    # Sample orderbooks for demonstration
    sample_orderbooks = _get_sample_orderbooks()

    if not sample_orderbooks:
        st.warning("No orderbook data available.")
        return

    # Display metrics for each sample market
    for market_id, orderbook in sample_orderbooks.items():
        with st.expander(f"📊 {market_id}", expanded=True):
            _render_market_depth(market_id, orderbook, config)


def _render_market_depth(
    market_id: str, orderbook: Dict[str, Any], config: Dict[str, Any]
):
    """
    Render depth metrics for a single market.

    Args:
        market_id: Market identifier
        orderbook: Orderbook data dictionary
        config: Depth configuration dictionary
    """
    # Analyze depth metrics
    metrics = analyze_depth(orderbook)

    # Detect any depth signals (thin books, large gaps, imbalances)
    signals = detect_depth_signals(metrics, config=config)

    # Create columns for metrics display
    col1, col2, col3 = st.columns(3)

    with col1:
        total_depth = metrics.get("total_yes_depth", 0) + metrics.get(
            "total_no_depth", 0
        )
        min_depth_threshold = config.get("min_depth", DEFAULT_CONFIG["min_depth"])

        # Highlight thin books
        is_thin = total_depth < min_depth_threshold
        depth_color = "🔴" if is_thin else "🟢"
        st.metric(
            f"{depth_color} Total Depth",
            f"${total_depth:,.2f}",
            delta=f"Threshold: ${min_depth_threshold:,.0f}",
            delta_color="inverse" if is_thin else "normal",
        )

    with col2:
        top_gap_yes = metrics.get("top_gap_yes", 0)
        top_gap_no = metrics.get("top_gap_no", 0)
        max_gap = max(top_gap_yes, top_gap_no)
        max_gap_threshold = config.get("max_gap", DEFAULT_CONFIG["max_gap"])

        is_large_gap = max_gap > max_gap_threshold
        gap_color = "🔴" if is_large_gap else "🟢"
        st.metric(
            f"{gap_color} Bid-Ask Gap",
            f"{max_gap:.4f}",
            delta=f"Threshold: {max_gap_threshold:.4f}",
            delta_color="inverse" if is_large_gap else "normal",
        )

    with col3:
        imbalance = abs(metrics.get("imbalance", 0))
        imbalance_threshold = config.get(
            "imbalance_ratio", DEFAULT_CONFIG["imbalance_ratio"]
        )

        is_imbalanced = imbalance > imbalance_threshold
        imbalance_color = "🔴" if is_imbalanced else "🟢"
        st.metric(
            f"{imbalance_color} Imbalance",
            f"${imbalance:,.2f}",
            delta=f"Threshold: ${imbalance_threshold:,.0f}",
            delta_color="inverse" if is_imbalanced else "normal",
        )

    # Display active signals/alerts
    if signals:
        st.markdown("**⚠️ Active Signals:**")
        for signal in signals:
            _render_signal_alert(signal)
    else:
        st.success("✅ No depth alerts for this market")


def _render_signal_alert(signal: DepthSignal):
    """
    Render a single depth signal alert.

    Args:
        signal: DepthSignal object to display
    """
    signal_icons = {
        "thin_depth": "📉",
        "large_gap": "↔️",
        "strong_imbalance": "⚖️",
    }

    icon = signal_icons.get(signal.signal_type, "⚠️")
    st.warning(f"{icon} **{signal.signal_type}**: {signal.reason}")


def _render_recent_alerts_tab():
    """Render the recent alerts tab."""
    st.subheader("🔔 Recent Depth Alerts")

    try:
        recent_alerts = fetch_recent_depth_events(limit=50)

        if recent_alerts:
            # Convert to DataFrame for display
            df = pd.DataFrame(recent_alerts)

            # Select relevant columns if they exist
            display_cols = [
                "timestamp",
                "market_id",
                "signal_type",
                "threshold_hit",
                "mode",
            ]
            available_cols = [col for col in display_cols if col in df.columns]

            if available_cols:
                df_display = df[available_cols].copy()

                # Rename columns for display
                column_names = {
                    "timestamp": "Time",
                    "market_id": "Market ID",
                    "signal_type": "Signal Type",
                    "threshold_hit": "Threshold Hit",
                    "mode": "Mode",
                }
                df_display.columns = [
                    column_names.get(col, col) for col in df_display.columns
                ]

                # Display table
                st.dataframe(df_display, use_container_width=True)

                # Statistics
                st.markdown("---")
                st.subheader("📊 Alert Statistics")

                stat_col1, stat_col2, stat_col3 = st.columns(3)

                with stat_col1:
                    st.metric("Total Alerts", len(recent_alerts))

                with stat_col2:
                    thin_depth_count = sum(
                        1
                        for a in recent_alerts
                        if a.get("signal_type") == "thin_depth"
                    )
                    st.metric("Thin Depth Alerts", thin_depth_count)

                with stat_col3:
                    large_gap_count = sum(
                        1 for a in recent_alerts if a.get("signal_type") == "large_gap"
                    )
                    st.metric("Large Gap Alerts", large_gap_count)
            else:
                st.dataframe(df, use_container_width=True)
        else:
            st.info("No depth alerts recorded yet.")

    except Exception as e:
        st.error(f"Error loading recent alerts: {e}")
        logger.error(f"Error fetching depth events: {e}", exc_info=True)


def _render_thresholds_tab(config: Dict[str, Any]):
    """
    Render the thresholds configuration tab.

    Args:
        config: Current depth configuration dictionary
    """
    st.subheader("⚙️ Depth Thresholds Configuration")
    st.info(
        "Configure the thresholds used for detecting depth signals. "
        "Changes will be saved to the configuration file."
    )

    with st.form("depth_config_form"):
        col1, col2 = st.columns(2)

        with col1:
            min_depth = st.number_input(
                "Minimum Total Depth ($)",
                min_value=0.0,
                max_value=100000.0,
                value=float(config.get("min_depth", DEFAULT_CONFIG["min_depth"])),
                step=100.0,
                help="Alert when total orderbook depth falls below this value",
            )

            max_gap = st.number_input(
                "Maximum Bid-Ask Gap",
                min_value=0.0,
                max_value=1.0,
                value=float(config.get("max_gap", DEFAULT_CONFIG["max_gap"])),
                step=0.01,
                format="%.4f",
                help="Alert when bid-ask spread exceeds this value (0.10 = 10%)",
            )

        with col2:
            imbalance_ratio = st.number_input(
                "Imbalance Threshold ($)",
                min_value=0.0,
                max_value=10000.0,
                value=float(
                    config.get("imbalance_ratio", DEFAULT_CONFIG["imbalance_ratio"])
                ),
                step=50.0,
                help="Alert when depth imbalance exceeds this value",
            )

            markets_to_watch_str = st.text_area(
                "Markets to Watch",
                value="\n".join(
                    config.get("markets_to_watch", DEFAULT_CONFIG["markets_to_watch"])
                ),
                height=100,
                help="Enter market IDs to watch (one per line). Leave empty to watch all markets.",
            )

        st.markdown("---")

        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            submitted = st.form_submit_button("💾 Save Settings", type="primary")

        with col2:
            reset = st.form_submit_button("🔄 Reset to Defaults")

        if submitted:
            try:
                # Parse markets to watch
                markets_list = [
                    m.strip()
                    for m in markets_to_watch_str.split("\n")
                    if m.strip()
                ]

                new_config = {
                    "min_depth": min_depth,
                    "max_gap": max_gap,
                    "imbalance_ratio": imbalance_ratio,
                    "markets_to_watch": markets_list,
                }

                save_depth_config(new_config)
                st.success("✅ Settings saved successfully!")
                logger.info(f"Depth config updated: {new_config}")
                st.rerun()

            except Exception as e:
                st.error(f"❌ Error saving settings: {e}")
                logger.error(f"Error saving depth config: {e}", exc_info=True)

        if reset:
            try:
                save_depth_config(DEFAULT_CONFIG.copy())
                st.success("✅ Settings reset to defaults!")
                logger.info("Depth config reset to defaults")
                st.rerun()

            except Exception as e:
                st.error(f"❌ Error resetting settings: {e}")
                logger.error(f"Error resetting depth config: {e}", exc_info=True)

    # Display current configuration summary
    st.markdown("---")
    st.subheader("📋 Current Configuration")

    config_col1, config_col2 = st.columns(2)

    with config_col1:
        st.markdown(f"**Minimum Depth:** ${config.get('min_depth', 0):,.2f}")
        st.markdown(f"**Maximum Gap:** {config.get('max_gap', 0):.4f}")

    with config_col2:
        st.markdown(f"**Imbalance Threshold:** ${config.get('imbalance_ratio', 0):,.2f}")
        markets = config.get("markets_to_watch", [])
        if markets:
            st.markdown(f"**Markets Watched:** {len(markets)}")
        else:
            st.markdown("**Markets Watched:** All")


def _get_sample_orderbooks() -> Dict[str, Dict[str, Any]]:
    """
    Get sample orderbooks for demonstration.

    Returns:
        Dictionary mapping market IDs to orderbook data
    """
    return {
        "Sample Market 1": {
            "bids": [
                {"price": "0.45", "size": "150"},
                {"price": "0.44", "size": "200"},
                {"price": "0.43", "size": "300"},
            ],
            "asks": [
                {"price": "0.55", "size": "180"},
                {"price": "0.56", "size": "220"},
                {"price": "0.57", "size": "350"},
            ],
        },
        "Sample Market 2 (Thin)": {
            "bids": [
                {"price": "0.48", "size": "50"},
                {"price": "0.47", "size": "30"},
            ],
            "asks": [
                {"price": "0.72", "size": "40"},
                {"price": "0.73", "size": "25"},
            ],
        },
        "Sample Market 3 (Healthy)": {
            "bids": [
                {"price": "0.50", "size": "500"},
                {"price": "0.49", "size": "600"},
                {"price": "0.48", "size": "700"},
            ],
            "asks": [
                {"price": "0.52", "size": "450"},
                {"price": "0.53", "size": "550"},
                {"price": "0.54", "size": "650"},
            ],
        },
    }


if __name__ == "__main__":
    # For testing the depth view standalone
    st.set_page_config(
        page_title="Depth Monitor - Polymarket Arbitrage Spotter",
        page_icon="📊",
        layout="wide",
    )
    render_depth_view()
