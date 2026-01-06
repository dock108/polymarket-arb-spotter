"""
Price alerts view for managing and monitoring price alerts.

Allows users to:
- Add new price alerts with market ID, direction, and target price
- View all active alerts
- Remove existing alerts
- See recent alert triggers
"""

from datetime import datetime

import pandas as pd
import streamlit as st

from app.core.logger import fetch_recent_price_alerts, logger
from app.core.price_alerts import add_alert, list_alerts, remove_alert


def render_price_alerts_view():
    """
    Render the price alerts view page.

    Displays forms for adding/removing alerts, shows active alerts,
    and displays recent alert triggers from the database.
    """
    st.title("🔔 Price Alerts")
    st.markdown("---")

    # Add Alert Section
    st.subheader("➕ Add New Alert")

    with st.form("add_alert_form"):
        col1, col2, col3 = st.columns(3)

        with col1:
            market_id = st.text_input(
                "Market ID",
                help="Enter the unique market identifier",
                placeholder="e.g., market_123"
            )

        with col2:
            direction = st.selectbox(
                "Direction",
                ["above", "below"],
                help="Alert when price goes above or below target"
            )

        with col3:
            target_price = st.number_input(
                "Target Price",
                min_value=0.0,
                max_value=1.0,
                value=0.5,
                step=0.01,
                format="%.4f",
                help="Price threshold (0.0 - 1.0)"
            )

        submitted = st.form_submit_button("Add Alert", type="primary")

        if submitted:
            if not market_id or not market_id.strip():
                st.error("❌ Market ID cannot be empty")
            else:
                try:
                    alert_id = add_alert(market_id.strip(), direction, target_price)
                    st.success(f"✅ Alert added successfully! ID: {alert_id}")
                    logger.info(f"User added price alert: {alert_id}")
                    st.rerun()
                except ValueError as e:
                    st.error(f"❌ Error: {str(e)}")
                except Exception as e:
                    st.error(f"❌ Unexpected error: {str(e)}")
                    logger.error(f"Error adding alert: {e}", exc_info=True)

    st.markdown("---")

    # Active Alerts Section
    st.subheader("📋 Active Alerts")

    try:
        active_alerts = list_alerts()

        if active_alerts:
            # Convert to DataFrame for display
            df = pd.DataFrame(active_alerts)

            # Select and rename columns
            display_cols = [
                "id", "market_id", "direction", "target_price", "created_at"
            ]
            df_display = df[display_cols].copy()
            df_display.columns = [
                "Alert ID", "Market ID", "Direction", "Target Price", "Created At"
            ]

            # Format values
            df_display["Target Price"] = df_display["Target Price"].apply(
                lambda x: f"{x:.4f}"
            )

            # Display table
            st.dataframe(df_display, use_container_width=True)

            # Remove Alert Section
            st.markdown("---")
            st.subheader("🗑️ Remove Alert")

            col1, col2 = st.columns([3, 1])

            with col1:
                # Get list of alert IDs for selection
                alert_ids = [alert["id"] for alert in active_alerts]
                selected_alert_id = st.selectbox(
                    "Select Alert to Remove",
                    alert_ids,
                    help="Choose an alert ID to remove"
                )

            with col2:
                st.write("")  # Spacer
                st.write("")  # Spacer
                if st.button("Remove", type="secondary"):
                    try:
                        success = remove_alert(selected_alert_id)
                        if success:
                            st.success(
                                f"✅ Alert {selected_alert_id} removed successfully!"
                            )
                            logger.info(
                                f"User removed price alert: {selected_alert_id}"
                            )
                            st.rerun()
                        else:
                            st.error(f"❌ Alert {selected_alert_id} not found")
                    except Exception as e:
                        st.error(f"❌ Error removing alert: {str(e)}")
                        logger.error(f"Error removing alert: {e}", exc_info=True)

        else:
            st.info("No active alerts. Add one above to get started!")

    except Exception as e:
        st.error(f"Error loading active alerts: {e}")
        logger.error(f"Error in price alerts view: {e}", exc_info=True)

    st.markdown("---")

    # Recent Triggers Section
    st.subheader("🎯 Recent Alert Triggers")

    try:
        recent_triggers = fetch_recent_price_alerts(limit=50)

        if recent_triggers:
            # Convert to DataFrame for display
            df = pd.DataFrame(recent_triggers)

            # Select relevant columns
            display_cols = [
                "timestamp",
                "alert_id",
                "market_id",
                "direction",
                "target_price",
                "trigger_price"
            ]

            # Filter to only include columns that exist
            available_cols = [col for col in display_cols if col in df.columns]
            df_display = df[available_cols].copy()

            # Rename columns for display
            column_names = {
                "timestamp": "Time",
                "alert_id": "Alert ID",
                "market_id": "Market ID",
                "direction": "Direction",
                "target_price": "Target Price",
                "trigger_price": "Trigger Price"
            }
            df_display.columns = [
                column_names.get(col, col) for col in df_display.columns
            ]

            # Format price columns if they exist
            if "Target Price" in df_display.columns:
                df_display["Target Price"] = df_display["Target Price"].apply(
                    lambda x: f"{x:.4f}"
                )
            if "Trigger Price" in df_display.columns:
                df_display["Trigger Price"] = df_display["Trigger Price"].apply(
                    lambda x: f"{x:.4f}"
                )

            # Display table
            st.dataframe(df_display, use_container_width=True)

            # Statistics
            st.markdown("---")
            st.subheader("📊 Alert Statistics")

            stat_col1, stat_col2, stat_col3 = st.columns(3)

            with stat_col1:
                st.metric("Total Triggers", len(recent_triggers))

            with stat_col2:
                above_triggers = sum(
                    1 for t in recent_triggers if t.get("direction") == "above"
                )
                st.metric("Above Triggers", above_triggers)

            with stat_col3:
                below_triggers = sum(
                    1 for t in recent_triggers if t.get("direction") == "below"
                )
                st.metric("Below Triggers", below_triggers)

        else:
            st.info("No alert triggers recorded yet.")

    except Exception as e:
        st.error(f"Error loading recent triggers: {e}")
        logger.error(f"Error fetching recent triggers: {e}", exc_info=True)

    st.markdown("---")

    # Help Section
    with st.expander("ℹ️ Help & Information"):
        st.markdown("""
        **How to use Price Alerts:**

        1. **Add an Alert**: Enter a market ID, select direction (above/below),
           and set a target price
        2. **Monitor Active Alerts**: View all your currently active alerts in the table
        3. **Remove Alerts**: Select an alert from the dropdown and click Remove
           to delete it
        4. **Track Triggers**: See when alerts have been triggered in the
           Recent Alert Triggers section

        **About Price Alerts:**
        - Market IDs are unique identifiers for Polymarket markets
        - Direction determines if the alert triggers when price goes above or below
          the target
        - Target prices are between 0.0 and 1.0 (representing 0% to 100%)
        - Alerts persist until manually removed
        - Alert triggers are logged to the database for historical tracking

        **Note:** This view manages alert configuration. To actually watch markets
        and trigger alerts, you need to run the price alert watcher service separately.
        """)

    # Footer
    st.markdown("---")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    # For testing the price alerts view standalone
    st.set_page_config(
        page_title="Price Alerts - Polymarket Arbitrage Spotter",
        page_icon="🔔",
        layout="wide"
    )
    render_price_alerts_view()
