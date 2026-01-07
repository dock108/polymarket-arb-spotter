"""Utility helpers for pattern analysis."""

from datetime import datetime
from typing import Optional


def parse_timestamp(timestamp: str) -> Optional[datetime]:
    """Parse ISO format timestamp string to datetime."""
    try:
        if timestamp.endswith("Z"):
            timestamp = timestamp[:-1] + "+00:00"
        return datetime.fromisoformat(timestamp)
    except (ValueError, AttributeError):
        return None
