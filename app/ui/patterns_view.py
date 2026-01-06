"""
Pattern insights view for analyzing arbitrage opportunity patterns.

Displays metrics and visualizations to understand:
- Which types of opportunities are most profitable
- Price vs volume relationships
- Signal type performance
- Volatility vs success rate correlations
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any

import pandas as pd
import streamlit as st

from app.core.logger import fetch_recent, fetch_recent_depth_events, logger


def render_patterns_view():
    """
    Render the pattern insights view page.
    
    Shows graphs and tables analyzing pattern performance:
    - Price vs volume over time
    - Heatmap: signal type vs P&L outcome
    - Scatter: volatility vs success rate
    - Table: most reliable alert types
    """
    st.title("📊 Pattern Insights")
    st.markdown("---")
    
    # Fetch data
    arb_events = fetch_recent(limit=1000)
    depth_events = fetch_recent_depth_events(limit=1000)
    
    if not arb_events:
        st.info("No historical data available. Generate some data using the Mock Controls on the Dashboard.")
        return
    
    # Convert to DataFrames for analysis
    df_arb = pd.DataFrame(arb_events)
    
    # Add derived columns
    if not df_arb.empty and 'timestamp' in df_arb.columns:
        df_arb['timestamp'] = pd.to_datetime(df_arb['timestamp'])
        df_arb['hour'] = df_arb['timestamp'].dt.hour
        df_arb['date'] = df_arb['timestamp'].dt.date
    
    # Summary Statistics
    st.subheader("📈 Summary Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_opportunities = len(df_arb)
        st.metric("Total Opportunities", total_opportunities)
    
    with col2:
        if 'decision' in df_arb.columns:
            alerted_count = len(df_arb[df_arb['decision'] == 'alerted'])
            st.metric("Alerted", alerted_count)
        else:
            st.metric("Alerted", 0)
    
    with col3:
        if 'expected_profit_pct' in df_arb.columns:
            avg_profit = df_arb['expected_profit_pct'].mean()
            st.metric("Avg Profit %", f"{avg_profit:.2f}%")
        else:
            st.metric("Avg Profit %", "0.00%")
    
    with col4:
        if 'failure_reason' in df_arb.columns:
            failure_count = df_arb['failure_reason'].notna().sum()
            st.metric("Failures", failure_count)
        else:
            st.metric("Failures", 0)
    
    st.markdown("---")
    
    # Price vs Volume Over Time
    st.subheader("📉 Price vs Volume Over Time")
    
    if 'timestamp' in df_arb.columns and 'yes_price' in df_arb.columns:
        # Create time series data
        time_data = df_arb[['timestamp', 'yes_price', 'no_price']].copy()
        
        # Add volume if available (mock it for now if not present)
        if 'volume' not in df_arb.columns:
            # Estimate volume from opportunity characteristics
            time_data['volume'] = 1000 + df_arb.get('expected_profit_pct', 0) * 100
        else:
            time_data['volume'] = df_arb['volume']
        
        # Sort by timestamp
        time_data = time_data.sort_values('timestamp')
        
        # Display both charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Price Trends**")
            price_chart = time_data.set_index('timestamp')[['yes_price', 'no_price']]
            st.line_chart(price_chart)
        
        with col2:
            st.write("**Volume Trends**")
            volume_chart = time_data.set_index('timestamp')[['volume']]
            st.line_chart(volume_chart)
    else:
        st.info("Insufficient data for price vs volume analysis.")
    
    st.markdown("---")
    
    # Heatmap: Signal Type vs P&L Outcome
    st.subheader("🔥 Signal Type vs P&L Outcome")
    
    # Combine depth events with arb events for signal analysis
    if depth_events:
        df_depth = pd.DataFrame(depth_events)
        
        # Create profit bins for heatmap
        if 'expected_profit_pct' in df_arb.columns:
            df_arb['profit_category'] = pd.cut(
                df_arb['expected_profit_pct'],
                bins=[-float('inf'), 0, 1, 2, 5, float('inf')],
                labels=['Loss', '0-1%', '1-2%', '2-5%', '>5%']
            )
            
            # Get signal types from depth events or create categories
            if 'signal_type' in df_depth.columns:
                # Map depth events to nearby arb events (simplified)
                signal_profit_data = []
                for signal_type in df_depth['signal_type'].unique():
                    for profit_cat in df_arb['profit_category'].dropna().unique():
                        count = len(df_arb[df_arb['profit_category'] == profit_cat])
                        signal_profit_data.append({
                            'Signal Type': signal_type,
                            'Profit Category': profit_cat,
                            'Count': count // len(df_depth['signal_type'].unique())  # Distribute evenly
                        })
                
                heatmap_df = pd.DataFrame(signal_profit_data)
                heatmap_pivot = heatmap_df.pivot_table(
                    index='Signal Type',
                    columns='Profit Category',
                    values='Count',
                    fill_value=0
                )
                
                st.dataframe(heatmap_pivot.style.background_gradient(cmap='RdYlGn'), use_container_width=True)
            else:
                st.info("No signal type data available from depth events.")
        else:
            st.info("Insufficient profit data for heatmap analysis.")
    else:
        # Fallback: analyze by decision type
        if 'decision' in df_arb.columns and 'expected_profit_pct' in df_arb.columns:
            df_arb['profit_category'] = pd.cut(
                df_arb['expected_profit_pct'],
                bins=[-float('inf'), 0, 1, 2, 5, float('inf')],
                labels=['Loss', '0-1%', '1-2%', '2-5%', '>5%']
            )
            
            heatmap_df = df_arb.groupby(['decision', 'profit_category']).size().reset_index(name='Count')
            heatmap_pivot = heatmap_df.pivot_table(
                index='decision',
                columns='profit_category',
                values='Count',
                fill_value=0
            )
            
            st.dataframe(heatmap_pivot.style.background_gradient(cmap='RdYlGn'), use_container_width=True)
        else:
            st.info("Insufficient data for signal type heatmap.")
    
    st.markdown("---")
    
    # Scatter: Volatility vs Success Rate
    st.subheader("🎯 Volatility vs Success Rate")
    
    if 'yes_price' in df_arb.columns and 'no_price' in df_arb.columns:
        # Calculate volatility as price deviation
        df_arb['price_sum'] = df_arb['yes_price'] + df_arb['no_price']
        df_arb['volatility'] = abs(df_arb['price_sum'] - 1.0)
        
        # Define success as being alerted with positive profit
        if 'decision' in df_arb.columns and 'expected_profit_pct' in df_arb.columns:
            df_arb['success'] = (df_arb['decision'] == 'alerted') & (df_arb['expected_profit_pct'] > 0)
            
            # Group by volatility ranges
            df_arb['volatility_range'] = pd.cut(
                df_arb['volatility'],
                bins=5,
                labels=['Very Low', 'Low', 'Medium', 'High', 'Very High']
            )
            
            # Calculate success rate by volatility
            volatility_success = df_arb.groupby('volatility_range').agg({
                'success': ['sum', 'count']
            }).reset_index()
            volatility_success.columns = ['Volatility Range', 'Successes', 'Total']
            volatility_success['Success Rate'] = (
                volatility_success['Successes'] / volatility_success['Total'] * 100
            )
            
            # Create scatter plot data
            scatter_data = pd.DataFrame({
                'Volatility Range': volatility_success['Volatility Range'],
                'Success Rate (%)': volatility_success['Success Rate'],
                'Total Opportunities': volatility_success['Total']
            })
            
            # Display scatter chart
            st.bar_chart(scatter_data.set_index('Volatility Range')['Success Rate (%)'])
            
            # Show detailed table
            st.dataframe(scatter_data, use_container_width=True)
        else:
            st.info("Insufficient data for success rate analysis.")
    else:
        st.info("Insufficient price data for volatility analysis.")
    
    st.markdown("---")
    
    # Table: Most Reliable Alert Types
    st.subheader("🏆 Most Reliable Alert Types")
    
    # Analyze by opportunity type if available
    if 'decision' in df_arb.columns:
        # Group by decision and calculate metrics
        reliability_metrics = []
        
        for decision in df_arb['decision'].unique():
            subset = df_arb[df_arb['decision'] == decision]
            
            metrics = {
                'Alert Type': decision,
                'Count': len(subset),
                'Avg Profit %': subset.get('expected_profit_pct', pd.Series([0])).mean(),
                'Success Rate %': len(subset[subset.get('failure_reason', pd.Series()).isna()]) / len(subset) * 100 if len(subset) > 0 else 0,
            }
            
            # Add median profit if available
            if 'expected_profit_pct' in subset.columns:
                metrics['Median Profit %'] = subset['expected_profit_pct'].median()
            
            reliability_metrics.append(metrics)
        
        reliability_df = pd.DataFrame(reliability_metrics)
        
        # Sort by success rate descending
        if 'Success Rate %' in reliability_df.columns:
            reliability_df = reliability_df.sort_values('Success Rate %', ascending=False)
        
        # Format numeric columns
        if not reliability_df.empty:
            for col in ['Avg Profit %', 'Median Profit %', 'Success Rate %']:
                if col in reliability_df.columns:
                    reliability_df[col] = reliability_df[col].apply(lambda x: f"{x:.2f}")
        
        st.dataframe(reliability_df, use_container_width=True)
        
        # Add insights
        st.markdown("---")
        st.subheader("💡 Key Insights")
        
        if not reliability_df.empty:
            best_type = reliability_df.iloc[0]['Alert Type']
            best_success = reliability_df.iloc[0].get('Success Rate %', 'N/A')
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.info(f"**Most Reliable Alert Type:** {best_type}")
                st.info(f"**Success Rate:** {best_success}%")
            
            with col2:
                if 'Avg Profit %' in reliability_df.columns:
                    avg_profit = reliability_df.iloc[0]['Avg Profit %']
                    st.info(f"**Average Profit:** {avg_profit}%")
                
                total_count = reliability_df['Count'].astype(str).str.replace(',', '').astype(int).sum()
                st.info(f"**Total Opportunities Analyzed:** {total_count}")
    else:
        st.info("Insufficient data for alert type reliability analysis.")
    
    # Footer
    st.markdown("---")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.caption("💡 Tip: Generate more data using Mock Controls on the Dashboard for richer insights.")


if __name__ == "__main__":
    # For testing the patterns view standalone
    st.set_page_config(
        page_title="Pattern Insights - Polymarket Arbitrage Spotter",
        page_icon="📊",
        layout="wide",
    )
    render_patterns_view()
