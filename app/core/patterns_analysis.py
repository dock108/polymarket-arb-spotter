"""Pattern correlation analysis logic."""

from collections import defaultdict
from datetime import datetime, timedelta
import statistics
from typing import Any, Dict, List, Optional, Tuple

from app.core.history_store import _HISTORY_DB_PATH, get_ticks
from app.core.logger import _DB_PATH, fetch_history_labels, logger
from app.core.patterns_models import CorrelationSummary, PatternStatistics, SignalOutcome
from app.core.patterns_utils import parse_timestamp


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
            "EventCorrelationAnalyzer initialized: "
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
            "Starting pattern analysis: "
            f"market={market_id}, start={start}, end={end}, label_types={label_types}"
        )

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

        if label_types:
            labels = [label for label in labels if label.get("label_type") in label_types]

        logger.info(f"Analyzing {len(labels)} labels")

        signal_outcomes = []
        markets_seen = set()

        for label in labels:
            outcome = self._compute_signal_outcome(label)
            if outcome:
                signal_outcomes.append(outcome)
                markets_seen.add(label["market_id"])

        logger.info(f"Computed outcomes for {len(signal_outcomes)} signals")

        pattern_stats = self._aggregate_pattern_statistics(signal_outcomes, labels)

        false_signals = [
            label for label in labels if label.get("label_type") == "false signal"
        ]
        overall_fp_rate = len(false_signals) / len(labels) if labels else 0.0

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
            "Analysis complete: "
            f"{summary.markets_analyzed} markets, {summary.total_labels} labels, "
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
            signal_time = parse_timestamp(label["timestamp"])
            if signal_time is None:
                logger.warning(
                    f"Invalid timestamp for label {label.get('id')}: {label.get('timestamp')}"
                )
                return None

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

            signal_tick = self._find_closest_tick(ticks, signal_time)
            if not signal_tick:
                return None

            initial_price = signal_tick["yes_price"]
            initial_volume = signal_tick.get("volume", 0.0)

            price_5m = self._find_price_at_offset(ticks, signal_time, 5)
            price_15m = self._find_price_at_offset(ticks, signal_time, 15)
            price_60m = self._find_price_at_offset(ticks, signal_time, 60)

            max_move, time_to_resolution = self._compute_resolution_metrics(
                ticks, signal_time, initial_price
            )

            after_ticks = []
            for tick in ticks:
                tick_time = parse_timestamp(tick["timestamp"])
                if tick_time and tick_time > signal_time:
                    after_ticks.append(tick)
            avg_volume_after = (
                statistics.mean([t.get("volume", 0.0) for t in after_ticks])
                if after_ticks
                else initial_volume
            )

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

        except Exception as exc:
            logger.error(
                f"Error computing signal outcome for label {label.get('id')}: {exc}",
                exc_info=True,
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
            tick_time = parse_timestamp(tick["timestamp"])
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
            tick_time = parse_timestamp(tick["timestamp"])
            if not tick_time or tick_time <= signal_time:
                continue

            price = tick["yes_price"]
            move = price - initial_price

            if abs(move) > abs(max_move):
                max_move = move

            if time_to_resolution is None:
                if abs(price - prev_price) < self.price_stability_threshold:
                    stability_count += 1
                    if stability_count >= self.stability_consecutive_ticks:
                        time_to_resolution = (
                            tick_time - signal_time
                        ).total_seconds() / 60
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
        outcomes_by_type = defaultdict(list)
        for outcome in outcomes:
            outcomes_by_type[outcome.signal_type].append(outcome)

        labels_by_type = defaultdict(list)
        for label in labels:
            label_type = label.get("label_type", "unknown")
            labels_by_type[label_type].append(label)

        pattern_stats = {}

        for pattern_type, pattern_outcomes in outcomes_by_type.items():
            if pattern_type == "false signal":
                continue

            price_moves = [o.max_price_move for o in pattern_outcomes]
            avg_price_move = statistics.mean(price_moves) if price_moves else 0.0

            resolution_times = [
                o.time_to_resolution_minutes
                for o in pattern_outcomes
                if o.time_to_resolution_minutes is not None
            ]
            avg_resolution = (
                statistics.mean(resolution_times) if resolution_times else 0.0
            )

            positive_outcomes = sum(1 for o in pattern_outcomes if o.max_price_move > 0)
            positive_rate = (
                positive_outcomes / len(pattern_outcomes) if pattern_outcomes else 0.0
            )

            total_pattern_labels = len(labels_by_type.get(pattern_type, []))
            false_positives = sum(
                1
                for label in labels
                if label.get("label_type") == "false signal"
                and pattern_type.lower() in label.get("notes", "").lower()
            )
            fp_rate = (
                false_positives / total_pattern_labels
                if total_pattern_labels > 0
                else 0.0
            )

            volume_changes = [o.volume_after - o.volume_before for o in pattern_outcomes]
            avg_volume_change = (
                statistics.mean(volume_changes) if volume_changes else 0.0
            )

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

    def _compute_resolution_curve(
        self, outcomes: List[SignalOutcome]
    ) -> List[Tuple[int, float]]:
        """
        Compute time-to-resolution cumulative curve.

        Args:
            outcomes: List of signal outcomes

        Returns:
            List of (time_minutes, cumulative_resolved_percentage) tuples
        """
        resolution_times = [
            o.time_to_resolution_minutes
            for o in outcomes
            if o.time_to_resolution_minutes is not None
        ]

        if not resolution_times:
            return []

        sorted_times = sorted(resolution_times)
        total = len(sorted_times)

        curve = []
        if self.resolution_window_minutes <= 15:
            time_points = [1, 5, 10, 15]
        elif self.resolution_window_minutes <= 30:
            time_points = [1, 5, 10, 15, 30]
        elif self.resolution_window_minutes <= 60:
            time_points = [1, 5, 10, 15, 30, 45, 60]
        else:
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
