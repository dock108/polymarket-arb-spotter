"""
UI utility functions for formatting and presentation.
"""

from datetime import datetime
from typing import Optional
import streamlit as st

def format_market_title(title: str, max_length: int = 60) -> str:
    """Truncate title nicely."""
    if not title:
        return "Unknown Market"
    if len(title) <= max_length:
        return title
    return title[:max_length-3] + "..."

def format_expiry_date(dt: Optional[datetime]) -> str:
    """Format expiration date: Jan 18, 2026 — 3:15 PM UTC"""
    if not dt:
        return "No expiration"
    return dt.strftime("%b %d, %Y — %I:%M %p UTC")

def render_category_badge(category: Optional[str]):
    """Render a small badge for category."""
    if not category:
        return
    st.markdown(f"""
        <span style="
            background-color: rgba(255, 255, 255, 0.1);
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.7rem;
            color: #ccc;
            border: 1px solid rgba(255, 255, 255, 0.2);
            margin-right: 5px;
            vertical-align: middle;
        ">{category.upper()}</span>
    """, unsafe_allow_html=True)
