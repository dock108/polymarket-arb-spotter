"""
Event correlation analyzer for Polymarket markets.

Takes historical market data + user labels to compute descriptive statistics:
- Average price moves after similar setups
- Frequency of signal→profit outcomes
- False-positive rates
- Time-to-resolution curves

No ML - just descriptive stats to help understand pattern performance.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
import statistics

from app.core.history_store import get_ticks, _HISTORY_DB_PATH
from app.core.logger import fetch_history_labels, _DB_PATH
from app.core.logger import logger


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


class EventCorrelationAnalyzer:
    """
    Analyze correlations between labeled events and market outcomes.

    Computes descriptive statistics from historical market data and user labels
    to understand pattern performance and characteristics.
    """

    def __init__(
        self,
        history_db_path: str = _HISTORY_DB_PATH,
        labels_db_path: str = _DB_PATH,
        resolution_window_minutes: int = 60,
        price_stability_threshold: float = 0.01,
        profitable_threshold: float = 0.02,
        stability_consecutive_ticks: int = 3,
    ):
        """
        Initialize the event correlation analyzer.

        Args:
            history_db_path: Path to market history database
            labels_db_path: Path to labels database
            resolution_window_minutes: Time window for tracking outcomes (default: 60 minutes)
            price_stability_threshold: Price change threshold for "resolution" (default: 0.01 = 1%)
            profitable_threshold: Minimum price move to consider profitable (default: 0.02 = 2%)
            stability_consecutive_ticks: Number of stable ticks needed for resolution (default: 3)
        """
        self.history_db_path = history_db_path
        self.labels_db_path = labels_db_path
        self.resolution_window_minutes = resolution_window_minutes
        self.price_stability_threshold = price_stability_threshold
        self.profitable_threshold = profitable_threshold
        self.stability_consecutive_ticks = stability_consecutive_ticks

        logger.info(
            f"EventCorrelationAnalyzer initialized: "
            f"resolution_window={resolution_window_minutes}m, "
            f"stability_threshold={price_stability_threshold}, "
            f"profitable_threshold={profitable_threshold}"
        )

    def analyze_patterns(
        self,
        market_id: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        label_types: Optional[List[str]] = None,
    ) -> CorrelationSummary:
        """
        Analyze patterns and compute correlation statistics.

        Args:
            market_id: Optional market ID to filter analysis
            start: Optional start timestamp (ISO format)
            end: Optional end timestamp (ISO format)
            label_types: Optional list of label types to analyze

        Returns:
            CorrelationSummary with complete analysis results
        """
        logger.info(
            f"Starting pattern analysis: market={market_id}, "
            f"start={start}, end={end}, label_types={label_types}"
        )

        # Fetch all relevant labels
        labels = fetch_history_labels(
            market_id=market_id,
            start=start,
            end=end,
            limit=10000,
            db_path=self.labels_db_path,
        )

        if not labels:
            logger.warning("No labels found for analysis")
            return self._create_empty_summary()

        # Filter by label type if specified
        if label_types:
            labels = [label for label in labels if label.get("label_type") in label_types]

        logger.info(f"Analyzing {len(labels)} labels")

        # Compute signal outcomes for each label
        signal_outcomes = []
        markets_seen = set()

        for label in labels:
            outcome = self._compute_signal_outcome(label)
            if outcome:
                signal_outcomes.append(outcome)
                markets_seen.add(label["market_id"])

        logger.info(f"Computed outcomes for {len(signal_outcomes)} signals")

        # Aggregate statistics by pattern type
        pattern_stats = self._aggregate_pattern_statistics(signal_outcomes, labels)

        # Compute overall false positive rate
        false_signals = [label for label in labels if label.get("label_type") == "false signal"]
        overall_fp_rate = len(false_signals) / len(labels) if labels else 0.0

        # Compute time-to-resolution curve
        resolution_curve = self._compute_resolution_curve(signal_outcomes)

        summary = CorrelationSummary(
            analysis_timestamp=datetime.now().isoformat(),
            markets_analyzed=len(markets_seen),
            total_labels=len(labels),
            pattern_stats=pattern_stats,
            overall_false_positive_rate=overall_fp_rate,
            time_to_resolution_curve=resolution_curve,
            signal_outcomes=signal_outcomes,
        )

        logger.info(
            f"Analysis complete: {summary.markets_analyzed} markets, "
            f"{summary.total_labels} labels, "
            f"{len(pattern_stats)} pattern types"
        )

        return summary

    def _compute_signal_outcome(self, label: Dict[str, Any]) -> Optional[SignalOutcome]:
        """
        Compute outcome metrics for a single labeled signal.

        Args:
            label: Label dictionary with timestamp, market_id, label_type

        Returns:
            SignalOutcome or None if insufficient data
        """
        try:
            market_id = label["market_id"]
            signal_time = datetime.fromisoformat(label["timestamp"])

            # Fetch ticks around the signal time
            start_time = signal_time - timedelta(minutes=5)
            end_time = signal_time + timedelta(minutes=self.resolution_window_minutes)

            ticks = get_ticks(
                market_id=market_id,
                start=start_time.isoformat(),
                end=end_time.isoformat(),
                limit=1000,
                db_path=self.history_db_path,
            )

            if not ticks:
                return None

            # Find tick closest to signal time
            signal_tick = self._find_closest_tick(ticks, signal_time)
            if not signal_tick:
                return None

            initial_price = signal_tick["yes_price"]
            initial_volume = signal_tick.get("volume", 0.0)

            # Find prices at specific intervals after signal
            price_5m = self._find_price_at_offset(ticks, signal_time, 5)
            price_15m = self._find_price_at_offset(ticks, signal_time, 15)
            price_60m = self._find_price_at_offset(ticks, signal_time, 60)

            # Compute max price move and time to resolution
            max_move, time_to_resolution = self._compute_resolution_metrics(
                ticks, signal_time, initial_price
            )

            # Compute average volume after signal
            after_ticks = [t for t in ticks if self._parse_timestamp(t["timestamp"]) > signal_time]
            avg_volume_after = (
                statistics.mean([t.get("volume", 0.0) for t in after_ticks])
                if after_ticks
                else initial_volume
            )

            # Determine if signal was profitable (using configured threshold)
            was_profitable = abs(max_move) > self.profitable_threshold

            return SignalOutcome(
                signal_timestamp=label["timestamp"],
                signal_type=label["label_type"],
                market_id=market_id,
                initial_price=initial_price,
                price_after_5m=price_5m,
                price_after_15m=price_15m,
                price_after_60m=price_60m,
                max_price_move=max_move,
                time_to_resolution_minutes=time_to_resolution,
                volume_before=initial_volume,
                volume_after=avg_volume_after,
                was_profitable=was_profitable,
            )

        except Exception as e:
            logger.error(
                f"Error computing signal outcome for label {label.get('id')}: {e}", exc_info=True
            )
            return None

    def _find_closest_tick(
        self, ticks: List[Dict[str, Any]], target_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Find the tick closest to the target timestamp."""
        if not ticks:
            return None

        closest_tick = None
        min_diff = float("inf")

        for tick in ticks:
            tick_time = self._parse_timestamp(tick["timestamp"])
            if tick_time:
                diff = abs((tick_time - target_time).total_seconds())
                if diff < min_diff:
                    min_diff = diff
                    closest_tick = tick

        return closest_tick

    def _find_price_at_offset(
        self, ticks: List[Dict[str, Any]], signal_time: datetime, offset_minutes: int
    ) -> Optional[float]:
        """Find price at a specific time offset from signal."""
        target_time = signal_time + timedelta(minutes=offset_minutes)
        tick = self._find_closest_tick(ticks, target_time)
        return tick["yes_price"] if tick else None

    def _compute_resolution_metrics(
        self, ticks: List[Dict[str, Any]], signal_time: datetime, initial_price: float
    ) -> Tuple[float, Optional[float]]:
        """
        Compute max price move and time to resolution.

        Returns:
            Tuple of (max_price_move, time_to_resolution_minutes)
        """
        max_move = 0.0
        time_to_resolution = None
        prev_price = initial_price
        stability_count = 0

        for tick in ticks:
            tick_time = self._parse_timestamp(tick["timestamp"])
            if not tick_time or tick_time <= signal_time:
                continue

            price = tick["yes_price"]
            move = price - initial_price

            if abs(move) > abs(max_move):
                max_move = move  # Keep sign for direction

            # Check if price has stabilized (small change from previous tick)
            if time_to_resolution is None:
                if abs(price - prev_price) < self.price_stability_threshold:
                    stability_count += 1
                    if stability_count >= self.stability_consecutive_ticks:
                        time_to_resolution = (tick_time - signal_time).total_seconds() / 60
                else:
                    stability_count = 0

            prev_price = price

        return max_move, time_to_resolution

    def _aggregate_pattern_statistics(
        self, outcomes: List[SignalOutcome], labels: List[Dict[str, Any]]
    ) -> Dict[str, PatternStatistics]:
        """
        Aggregate outcomes into pattern-level statistics.

        Args:
            outcomes: List of signal outcomes
            labels: List of all labels (for false positive rate)

        Returns:
            Dictionary mapping pattern type to PatternStatistics
        """
        # Group outcomes by pattern type
        outcomes_by_type = defaultdict(list)
        for outcome in outcomes:
            outcomes_by_type[outcome.signal_type].append(outcome)

        # Group labels by type for counting
        labels_by_type = defaultdict(list)
        for label in labels:
            label_type = label.get("label_type", "unknown")
            labels_by_type[label_type].append(label)

        pattern_stats = {}

        for pattern_type, pattern_outcomes in outcomes_by_type.items():
            # Skip false signal type for statistics (it's meta)
            if pattern_type == "false signal":
                continue

            # Compute average price move
            price_moves = [o.max_price_move for o in pattern_outcomes]
            avg_price_move = statistics.mean(price_moves) if price_moves else 0.0

            # Compute average time to resolution
            resolution_times = [
                o.time_to_resolution_minutes
                for o in pattern_outcomes
                if o.time_to_resolution_minutes is not None
            ]
            avg_resolution = statistics.mean(resolution_times) if resolution_times else 0.0

            # Compute positive outcome rate (price went up)
            positive_outcomes = sum(1 for o in pattern_outcomes if o.max_price_move > 0)
            positive_rate = positive_outcomes / len(pattern_outcomes) if pattern_outcomes else 0.0

            # Compute false positive rate for this pattern
            # (based on labels marked as "false signal" with notes mentioning this pattern)
            total_pattern_labels = len(labels_by_type.get(pattern_type, []))
            false_positives = sum(
                1
                for label in labels
                if label.get("label_type") == "false signal"
                and pattern_type.lower() in label.get("notes", "").lower()
            )
            fp_rate = false_positives / total_pattern_labels if total_pattern_labels > 0 else 0.0

            # Compute average volume change
            volume_changes = [o.volume_after - o.volume_before for o in pattern_outcomes]
            avg_volume_change = statistics.mean(volume_changes) if volume_changes else 0.0

            # Get sample timestamps
            sample_timestamps = [o.signal_timestamp for o in pattern_outcomes[:5]]

            pattern_stats[pattern_type] = PatternStatistics(
                pattern_type=pattern_type,
                total_occurrences=total_pattern_labels,
                avg_price_move=avg_price_move,
                avg_time_to_resolution_minutes=avg_resolution,
                positive_outcome_rate=positive_rate,
                false_positive_rate=fp_rate,
                avg_volume_change=avg_volume_change,
                sample_timestamps=sample_timestamps,
            )

        return pattern_stats

    def _compute_resolution_curve(self, outcomes: List[SignalOutcome]) -> List[Tuple[int, float]]:
        """
        Compute time-to-resolution cumulative curve.

        Args:
            outcomes: List of signal outcomes

        Returns:
            List of (time_minutes, cumulative_resolved_percentage) tuples
        """
        # Filter outcomes with resolution times
        resolution_times = [
            o.time_to_resolution_minutes
            for o in outcomes
            if o.time_to_resolution_minutes is not None
        ]

        if not resolution_times:
            return []

        # Sort resolution times
        sorted_times = sorted(resolution_times)
        total = len(sorted_times)

        # Create curve at time intervals based on resolution window
        # Use standard intervals up to the resolution window
        curve = []
        if self.resolution_window_minutes <= 15:
            time_points = [1, 5, 10, 15]
        elif self.resolution_window_minutes <= 30:
            time_points = [1, 5, 10, 15, 30]
        elif self.resolution_window_minutes <= 60:
            time_points = [1, 5, 10, 15, 30, 45, 60]
        else:
            # For longer windows, add intervals every 30 minutes
            time_points = [1, 5, 10, 15, 30]
            current = 60
            while current <= self.resolution_window_minutes:
                time_points.append(current)
                current += 30

        for time_point in time_points:
            if time_point > self.resolution_window_minutes:
                break
            resolved_count = sum(1 for t in sorted_times if t <= time_point)
            resolved_pct = (resolved_count / total) * 100
            curve.append((time_point, resolved_pct))

        return curve

    def _create_empty_summary(self) -> CorrelationSummary:
        """Create an empty summary when no data is available."""
        return CorrelationSummary(
            analysis_timestamp=datetime.now().isoformat(),
            markets_analyzed=0,
            total_labels=0,
            pattern_stats={},
            overall_false_positive_rate=0.0,
            time_to_resolution_curve=[],
            signal_outcomes=[],
        )

    @staticmethod
    def _parse_timestamp(timestamp: str) -> Optional[datetime]:
        """Parse ISO format timestamp string to datetime."""
        try:
            # Handle UTC 'Z' suffix by replacing only at the end
            if timestamp.endswith("Z"):
                timestamp = timestamp[:-1] + "+00:00"
            return datetime.fromisoformat(timestamp)
        except (ValueError, AttributeError):
            return None


class InterestingMomentsFinder:
    """
    Automated detector for timestamps likely worth review.

    Identifies interesting moments in market data:
    - Sudden price acceleration
    - Abnormal volume clusters
    - Imbalance reversals
    - Repeated alert firing

    This saves time during analysis by highlighting key review candidates.
    """

    def __init__(
        self,
        history_db_path: str = _HISTORY_DB_PATH,
        labels_db_path: str = _DB_PATH,
        price_acceleration_threshold: float = 0.05,  # 5% price change in short window
        volume_spike_multiplier: float = 3.0,  # 3x normal volume
        imbalance_threshold: float = 0.15,  # 15% from 0.5 midpoint
        alert_clustering_window_minutes: int = 5,  # Alerts within 5 minutes
        min_alert_cluster_size: int = 3,  # At least 3 alerts
    ):
        """
        Initialize the interesting moments finder.

        Args:
            history_db_path: Path to market history database
            labels_db_path: Path to labels database
            price_acceleration_threshold: Minimum price change to consider acceleration (default: 0.05 = 5%)
            volume_spike_multiplier: Volume multiplier over baseline to flag spike (default: 3.0)
            imbalance_threshold: Distance from 0.5 to consider imbalanced (default: 0.15)
            alert_clustering_window_minutes: Time window for clustering alerts (default: 5)
            min_alert_cluster_size: Minimum alerts in window to flag cluster (default: 3)
        """
        self.history_db_path = history_db_path
        self.labels_db_path = labels_db_path
        self.price_acceleration_threshold = price_acceleration_threshold
        self.volume_spike_multiplier = volume_spike_multiplier
        self.imbalance_threshold = imbalance_threshold
        self.alert_clustering_window_minutes = alert_clustering_window_minutes
        self.min_alert_cluster_size = min_alert_cluster_size

        logger.info(
            f"InterestingMomentsFinder initialized: "
            f"price_threshold={price_acceleration_threshold}, "
            f"volume_multiplier={volume_spike_multiplier}, "
            f"imbalance_threshold={imbalance_threshold}"
        )

    def find_interesting_moments(
        self,
        market_id: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        min_severity: float = 0.5,
    ) -> List[InterestingMoment]:
        """
        Find all interesting moments in the specified time range.

        Args:
            market_id: Optional market ID to filter analysis
            start: Optional start timestamp (ISO format)
            end: Optional end timestamp (ISO format)
            min_severity: Minimum severity to include in results (0.0-1.0, default: 0.5)

        Returns:
            List of InterestingMoment objects sorted by severity (highest first)
        """
        logger.info(
            f"Finding interesting moments: market={market_id}, start={start}, end={end}"
        )

        all_moments = []

        # Get markets to analyze
        if market_id:
            markets = [market_id]
        else:
            # Fetch labels to discover markets
            labels = fetch_history_labels(
                start=start, end=end, limit=10000, db_path=self.labels_db_path
            )
            markets = list(set(label["market_id"] for label in labels)) if labels else []

        for mkt_id in markets:
            # Detect price accelerations
            all_moments.extend(
                self._detect_price_accelerations(mkt_id, start, end)
            )

            # Detect volume spikes
            all_moments.extend(
                self._detect_volume_spikes(mkt_id, start, end)
            )

            # Detect imbalance reversals
            all_moments.extend(
                self._detect_imbalance_reversals(mkt_id, start, end)
            )

        # Detect repeated alert firing across all markets
        all_moments.extend(
            self._detect_alert_clusters(market_id, start, end)
        )

        # Filter by severity and sort
        interesting = [m for m in all_moments if m.severity >= min_severity]
        interesting.sort(key=lambda m: m.severity, reverse=True)

        logger.info(
            f"Found {len(interesting)} interesting moments "
            f"(out of {len(all_moments)} total candidates)"
        )

        return interesting

    def _detect_price_accelerations(
        self,
        market_id: str,
        start: Optional[str],
        end: Optional[str],
    ) -> List[InterestingMoment]:
        """
        Detect sudden price accelerations.

        Looks for rapid price changes over short time windows that exceed threshold.
        """
        moments = []

        try:
            ticks = get_ticks(
                market_id=market_id,
                start=start,
                end=end,
                limit=10000,
                db_path=self.history_db_path,
            )

            if len(ticks) < 2:
                return moments

            # Use a sliding window to detect acceleration
            window_size = 5  # Compare over 5-tick windows
            for i in range(len(ticks) - window_size):
                window_start = ticks[i]
                window_end = ticks[i + window_size]

                price_change = abs(window_end["yes_price"] - window_start["yes_price"])

                if price_change >= self.price_acceleration_threshold:
                    # Calculate severity based on how much it exceeds threshold
                    severity = min(1.0, price_change / (self.price_acceleration_threshold * 2))

                    moments.append(
                        InterestingMoment(
                            timestamp=window_end["timestamp"],
                            market_id=market_id,
                            moment_type="price_acceleration",
                            reason=f"Price moved {price_change:.2%} in short window",
                            severity=severity,
                            metrics={
                                "price_change": price_change,
                                "start_price": window_start["yes_price"],
                                "end_price": window_end["yes_price"],
                            },
                        )
                    )

        except Exception as e:
            logger.error(
                f"Error detecting price accelerations for {market_id}: {e}",
                exc_info=True,
            )

        return moments

    def _detect_volume_spikes(
        self,
        market_id: str,
        start: Optional[str],
        end: Optional[str],
    ) -> List[InterestingMoment]:
        """
        Detect abnormal volume clusters.

        Identifies periods where volume significantly exceeds baseline.
        """
        moments = []

        try:
            ticks = get_ticks(
                market_id=market_id,
                start=start,
                end=end,
                limit=10000,
                db_path=self.history_db_path,
            )

            if len(ticks) < 10:
                return moments

            # Calculate baseline volume (median of all volumes)
            volumes = [tick.get("volume", 0.0) for tick in ticks]
            baseline_volume = statistics.median(volumes) if volumes else 0.0

            if baseline_volume == 0:
                return moments

            # Look for spikes
            for tick in ticks:
                volume = tick.get("volume", 0.0)
                if volume >= baseline_volume * self.volume_spike_multiplier:
                    volume_ratio = volume / baseline_volume
                    # Calculate severity based on how much it exceeds threshold
                    severity = min(1.0, (volume_ratio - self.volume_spike_multiplier) / self.volume_spike_multiplier)

                    moments.append(
                        InterestingMoment(
                            timestamp=tick["timestamp"],
                            market_id=market_id,
                            moment_type="volume_spike",
                            reason=f"Volume spike {volume_ratio:.1f}x baseline",
                            severity=severity,
                            metrics={
                                "volume": volume,
                                "baseline_volume": baseline_volume,
                                "volume_ratio": volume_ratio,
                            },
                        )
                    )

        except Exception as e:
            logger.error(
                f"Error detecting volume spikes for {market_id}: {e}",
                exc_info=True,
            )

        return moments

    def _detect_imbalance_reversals(
        self,
        market_id: str,
        start: Optional[str],
        end: Optional[str],
    ) -> List[InterestingMoment]:
        """
        Detect imbalance reversals.

        Identifies when markets transition from one side being heavily favored
        to the other side being heavily favored (crosses through 0.5).
        """
        moments = []

        try:
            ticks = get_ticks(
                market_id=market_id,
                start=start,
                end=end,
                limit=10000,
                db_path=self.history_db_path,
            )

            if len(ticks) < 2:
                return moments

            # Track last known imbalance state (ignoring neutral periods)
            last_imbalanced_yes = None

            for i, tick in enumerate(ticks):
                price = tick["yes_price"]

                # Check if currently imbalanced
                if price >= 0.5 + self.imbalance_threshold:
                    current_imbalanced_yes = True
                elif price <= 0.5 - self.imbalance_threshold:
                    current_imbalanced_yes = False
                else:
                    current_imbalanced_yes = None

                # Detect reversal (from one side to the other)
                # Only compare when we have a new imbalanced state
                if current_imbalanced_yes is not None:
                    if (
                        last_imbalanced_yes is not None
                        and last_imbalanced_yes != current_imbalanced_yes
                    ):
                        # Calculate how far it swung
                        swing_magnitude = abs(price - 0.5) + self.imbalance_threshold
                        severity = min(1.0, swing_magnitude / 0.3)  # Normalize to 30% swing

                        moments.append(
                            InterestingMoment(
                                timestamp=tick["timestamp"],
                                market_id=market_id,
                                moment_type="imbalance_reversal",
                                reason=f"Market imbalance reversed (price: {price:.2%})",
                                severity=severity,
                                metrics={
                                    "price": price,
                                    "distance_from_middle": abs(price - 0.5),
                                },
                            )
                        )

                    # Update last known imbalanced state
                    last_imbalanced_yes = current_imbalanced_yes

        except Exception as e:
            logger.error(
                f"Error detecting imbalance reversals for {market_id}: {e}",
                exc_info=True,
            )

        return moments

    def _detect_alert_clusters(
        self,
        market_id: Optional[str],
        start: Optional[str],
        end: Optional[str],
    ) -> List[InterestingMoment]:
        """
        Detect repeated alert firing.

        Identifies time windows where multiple alerts fire in quick succession,
        suggesting significant market activity.
        """
        moments = []

        try:
            # Fetch all labels in the time range
            labels = fetch_history_labels(
                market_id=market_id,
                start=start,
                end=end,
                limit=10000,
                db_path=self.labels_db_path,
            )

            if len(labels) < self.min_alert_cluster_size:
                return moments

            # Parse timestamps and sort
            labeled_events = []
            for label in labels:
                ts = self._parse_timestamp(label["timestamp"])
                if ts:
                    labeled_events.append((ts, label))

            labeled_events.sort(key=lambda x: x[0])

            # Use sliding window to find clusters
            window = timedelta(minutes=self.alert_clustering_window_minutes)

            for i in range(len(labeled_events)):
                window_start_time, start_label = labeled_events[i]
                window_end_time = window_start_time + window

                # Count events in window
                events_in_window = []
                for j in range(i, len(labeled_events)):
                    event_time, event_label = labeled_events[j]
                    if event_time <= window_end_time:
                        events_in_window.append(event_label)
                    else:
                        break

                # Check if cluster size meets threshold
                if len(events_in_window) >= self.min_alert_cluster_size:
                    # Calculate severity based on cluster size
                    severity = min(1.0, len(events_in_window) / (self.min_alert_cluster_size * 2))

                    # Get unique label types in cluster
                    label_types = set(e["label_type"] for e in events_in_window)

                    moments.append(
                        InterestingMoment(
                            timestamp=start_label["timestamp"],
                            market_id=start_label["market_id"],
                            moment_type="alert_cluster",
                            reason=f"{len(events_in_window)} alerts fired within {self.alert_clustering_window_minutes}m",
                            severity=severity,
                            metrics={
                                "alert_count": len(events_in_window),
                                "unique_alert_types": len(label_types),
                            },
                        )
                    )

        except Exception as e:
            logger.error(
                f"Error detecting alert clusters: {e}",
                exc_info=True,
            )

        return moments

    @staticmethod
    def _parse_timestamp(timestamp: str) -> Optional[datetime]:
        """Parse ISO format timestamp string to datetime."""
        try:
            # Handle UTC 'Z' suffix by replacing only at the end
            if timestamp.endswith("Z"):
                timestamp = timestamp[:-1] + "+00:00"
            return datetime.fromisoformat(timestamp)
        except (ValueError, AttributeError):
            return None


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
        ...     print(f"{moment.moment_type}: {moment.reason} (severity: {moment.severity:.2f})")
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
