"""
Facade for pattern analysis and interesting moment detection.
"""

from app.core.patterns_analysis import EventCorrelationAnalyzer
from app.core.patterns_models import (
    CorrelationSummary,
    InterestingMoment,
    PatternStatistics,
    SignalOutcome,
)
from app.core.patterns_moments import InterestingMomentsFinder
from app.core.history_store import _HISTORY_DB_PATH
from app.core.logger import _DB_PATH


def create_analyzer(
    history_db_path: str = _HISTORY_DB_PATH,
    labels_db_path: str = _DB_PATH,
    resolution_window_minutes: int = 60,
    price_stability_threshold: float = 0.01,
    profitable_threshold: float = 0.02,
    stability_consecutive_ticks: int = 3,
) -> EventCorrelationAnalyzer:
    """
    Convenience function to create an event correlation analyzer.

    Args:
        history_db_path: Path to market history database
        labels_db_path: Path to labels database
        resolution_window_minutes: Time window for tracking outcomes
        price_stability_threshold: Price change threshold for resolution
        profitable_threshold: Minimum price move to consider profitable
        stability_consecutive_ticks: Number of stable ticks needed for resolution

    Returns:
        Configured EventCorrelationAnalyzer instance

    Example:
        >>> analyzer = create_analyzer()
        >>> summary = analyzer.analyze_patterns(market_id="market_123")
        >>> print(f"Analyzed {summary.total_labels} labels")
    """
    return EventCorrelationAnalyzer(
        history_db_path=history_db_path,
        labels_db_path=labels_db_path,
        resolution_window_minutes=resolution_window_minutes,
        price_stability_threshold=price_stability_threshold,
        profitable_threshold=profitable_threshold,
        stability_consecutive_ticks=stability_consecutive_ticks,
    )


def create_moments_finder(
    history_db_path: str = _HISTORY_DB_PATH,
    labels_db_path: str = _DB_PATH,
    price_acceleration_threshold: float = 0.05,
    volume_spike_multiplier: float = 3.0,
    imbalance_threshold: float = 0.15,
    alert_clustering_window_minutes: int = 5,
    min_alert_cluster_size: int = 3,
) -> InterestingMomentsFinder:
    """
    Convenience function to create an interesting moments finder.

    Args:
        history_db_path: Path to market history database
        labels_db_path: Path to labels database
        price_acceleration_threshold: Minimum price change to consider acceleration
        volume_spike_multiplier: Volume multiplier over baseline to flag spike
        imbalance_threshold: Distance from 0.5 to consider imbalanced
        alert_clustering_window_minutes: Time window for clustering alerts
        min_alert_cluster_size: Minimum alerts in window to flag cluster

    Returns:
        Configured InterestingMomentsFinder instance

    Example:
        >>> finder = create_moments_finder()
        >>> moments = finder.find_interesting_moments(market_id="market_123")
        >>> print(f"Found {len(moments)} interesting moments")
        >>> for moment in moments[:5]:
        ...     print(
        ...         f"{moment.moment_type}: {moment.reason} "
        ...         f"(severity: {moment.severity:.2f})"
        ...     )
    """
    return InterestingMomentsFinder(
        history_db_path=history_db_path,
        labels_db_path=labels_db_path,
        price_acceleration_threshold=price_acceleration_threshold,
        volume_spike_multiplier=volume_spike_multiplier,
        imbalance_threshold=imbalance_threshold,
        alert_clustering_window_minutes=alert_clustering_window_minutes,
        min_alert_cluster_size=min_alert_cluster_size,
    )


__all__ = [
    "CorrelationSummary",
    "EventCorrelationAnalyzer",
    "InterestingMoment",
    "InterestingMomentsFinder",
    "PatternStatistics",
    "SignalOutcome",
    "create_analyzer",
    "create_moments_finder",
]
