"""
Data models for pattern analysis and interesting moment detection.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PatternStatistics:
    """
    Statistical summary for a specific pattern type.

    Attributes:
        pattern_type: Type of pattern (e.g., "whale entry", "arb collapse")
        total_occurrences: Total number of times this pattern was labeled
        avg_price_move: Average price change after pattern (absolute)
        avg_time_to_resolution_minutes: Average time until price stabilizes
        positive_outcome_rate: Fraction of times pattern led to price increase
        false_positive_rate: Fraction of times pattern was labeled as "false signal"
        avg_volume_change: Average volume change after pattern
        sample_timestamps: List of example timestamps where pattern occurred
    """

    pattern_type: str
    total_occurrences: int
    avg_price_move: float
    avg_time_to_resolution_minutes: float
    positive_outcome_rate: float
    false_positive_rate: float
    avg_volume_change: float
    sample_timestamps: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert statistics to dictionary."""
        return {
            "pattern_type": self.pattern_type,
            "total_occurrences": self.total_occurrences,
            "avg_price_move": self.avg_price_move,
            "avg_time_to_resolution_minutes": self.avg_time_to_resolution_minutes,
            "positive_outcome_rate": self.positive_outcome_rate,
            "false_positive_rate": self.false_positive_rate,
            "avg_volume_change": self.avg_volume_change,
            "sample_timestamps": self.sample_timestamps,
        }


@dataclass
class SignalOutcome:
    """
    Outcome data for a single signal/pattern instance.

    Attributes:
        signal_timestamp: When the signal occurred
        signal_type: Type of signal/pattern
        market_id: Market identifier
        initial_price: Price at signal time
        price_after_5m: Price 5 minutes after signal
        price_after_15m: Price 15 minutes after signal
        price_after_60m: Price 60 minutes after signal
        max_price_move: Maximum price move within resolution window
        time_to_resolution_minutes: Minutes until price stabilized
        volume_before: Volume before signal
        volume_after: Volume after signal
        was_profitable: Whether the signal led to profitable opportunity
    """

    signal_timestamp: str
    signal_type: str
    market_id: str
    initial_price: float
    price_after_5m: Optional[float]
    price_after_15m: Optional[float]
    price_after_60m: Optional[float]
    max_price_move: float
    time_to_resolution_minutes: Optional[float]
    volume_before: float
    volume_after: float
    was_profitable: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert outcome to dictionary."""
        return {
            "signal_timestamp": self.signal_timestamp,
            "signal_type": self.signal_type,
            "market_id": self.market_id,
            "initial_price": self.initial_price,
            "price_after_5m": self.price_after_5m,
            "price_after_15m": self.price_after_15m,
            "price_after_60m": self.price_after_60m,
            "max_price_move": self.max_price_move,
            "time_to_resolution_minutes": self.time_to_resolution_minutes,
            "volume_before": self.volume_before,
            "volume_after": self.volume_after,
            "was_profitable": self.was_profitable,
        }


@dataclass
class InterestingMoment:
    """
    Represents a timestamp that is potentially interesting for review.

    Attributes:
        timestamp: When the interesting moment occurred
        market_id: Market identifier
        moment_type: Type of interesting moment (e.g., "price_acceleration", "volume_spike")
        reason: Human-readable explanation of why this moment is interesting
        severity: Severity score (0.0-1.0, higher = more interesting)
        metrics: Dictionary of relevant metrics (e.g., price_change, volume_ratio)
    """

    timestamp: str
    market_id: str
    moment_type: str
    reason: str
    severity: float
    metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert interesting moment to dictionary."""
        return {
            "timestamp": self.timestamp,
            "market_id": self.market_id,
            "moment_type": self.moment_type,
            "reason": self.reason,
            "severity": self.severity,
            "metrics": self.metrics,
        }


@dataclass
class CorrelationSummary:
    """
    Complete correlation analysis summary.

    Attributes:
        analysis_timestamp: When the analysis was performed
        markets_analyzed: Number of markets included in analysis
        total_labels: Total number of labels analyzed
        pattern_stats: Dictionary mapping pattern type to PatternStatistics
        overall_false_positive_rate: Overall false positive rate across all patterns
        time_to_resolution_curve: List of (time_minutes, cumulative_resolved_pct) tuples
        signal_outcomes: List of individual signal outcomes
    """

    analysis_timestamp: str
    markets_analyzed: int
    total_labels: int
    pattern_stats: Dict[str, PatternStatistics]
    overall_false_positive_rate: float
    time_to_resolution_curve: List[Tuple[int, float]]
    signal_outcomes: List[SignalOutcome]

    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to dictionary."""
        return {
            "analysis_timestamp": self.analysis_timestamp,
            "markets_analyzed": self.markets_analyzed,
            "total_labels": self.total_labels,
            "pattern_stats": {k: v.to_dict() for k, v in self.pattern_stats.items()},
            "overall_false_positive_rate": self.overall_false_positive_rate,
            "time_to_resolution_curve": self.time_to_resolution_curve,
            "signal_outcomes": [outcome.to_dict() for outcome in self.signal_outcomes],
        }
