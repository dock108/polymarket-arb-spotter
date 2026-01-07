"""Interesting moment detection logic for pattern analysis."""

from datetime import timedelta
import statistics
from typing import List, Optional

from app.core.history_store import _HISTORY_DB_PATH, get_ticks
from app.core.logger import _DB_PATH, fetch_history_labels, logger
from app.core.patterns_models import InterestingMoment
from app.core.patterns_utils import parse_timestamp


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

    PRICE_SEVERITY_MULTIPLIER = 2
    IMBALANCE_SWING_NORMALIZER = 0.3
    ALERT_CLUSTER_SEVERITY_MULTIPLIER = 2

    def __init__(
        self,
        history_db_path: str = _HISTORY_DB_PATH,
        labels_db_path: str = _DB_PATH,
        price_acceleration_threshold: float = 0.05,
        volume_spike_multiplier: float = 3.0,
        imbalance_threshold: float = 0.15,
        alert_clustering_window_minutes: int = 5,
        min_alert_cluster_size: int = 3,
    ):
        """
        Initialize the interesting moments finder.

        Args:
            history_db_path: Path to market history database
            labels_db_path: Path to labels database
            price_acceleration_threshold: Minimum price change to consider
                acceleration (default: 0.05 = 5%)
            volume_spike_multiplier: Volume multiplier over baseline to flag
                spike (default: 3.0)
            imbalance_threshold: Distance from 0.5 to consider imbalanced
                (default: 0.15)
            alert_clustering_window_minutes: Time window for clustering alerts
                (default: 5)
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
            "InterestingMomentsFinder initialized: "
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
            "Finding interesting moments: market=%s, start=%s, end=%s",
            market_id,
            start,
            end,
        )

        all_moments = []

        if market_id:
            markets = [market_id]
        else:
            labels = fetch_history_labels(
                start=start, end=end, limit=10000, db_path=self.labels_db_path
            )
            markets = list({label["market_id"] for label in labels}) if labels else []

        for mkt_id in markets:
            all_moments.extend(self._detect_price_accelerations(mkt_id, start, end))
            all_moments.extend(self._detect_volume_spikes(mkt_id, start, end))
            all_moments.extend(self._detect_imbalance_reversals(mkt_id, start, end))

        all_moments.extend(self._detect_alert_clusters(market_id, start, end))

        interesting = [m for m in all_moments if m.severity >= min_severity]
        interesting.sort(key=lambda m: m.severity, reverse=True)

        logger.info(
            "Found %s interesting moments (out of %s total candidates)",
            len(interesting),
            len(all_moments),
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

            window_size = 5
            for i in range(len(ticks) - window_size):
                window_start = ticks[i]
                window_end = ticks[i + window_size]

                price_change = abs(window_end["yes_price"] - window_start["yes_price"])

                if price_change >= self.price_acceleration_threshold:
                    severity = min(
                        1.0,
                        price_change
                        / (
                            self.price_acceleration_threshold
                            * self.PRICE_SEVERITY_MULTIPLIER
                        ),
                    )

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

        except Exception as exc:
            logger.error(
                "Error detecting price accelerations for %s: %s",
                market_id,
                exc,
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

            volumes = [tick.get("volume", 0.0) for tick in ticks]
            baseline_volume = statistics.median(volumes) if volumes else 0.0

            if baseline_volume == 0:
                return moments

            for tick in ticks:
                volume = tick.get("volume", 0.0)
                if volume >= baseline_volume * self.volume_spike_multiplier:
                    volume_ratio = volume / baseline_volume
                    severity = min(
                        1.0,
                        (volume_ratio - self.volume_spike_multiplier)
                        / self.volume_spike_multiplier,
                    )

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

        except Exception as exc:
            logger.error(
                "Error detecting volume spikes for %s: %s",
                market_id,
                exc,
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

            last_imbalanced_yes = None

            for tick in ticks:
                price = tick["yes_price"]

                if price >= 0.5 + self.imbalance_threshold:
                    current_imbalanced_yes = True
                elif price <= 0.5 - self.imbalance_threshold:
                    current_imbalanced_yes = False
                else:
                    current_imbalanced_yes = None

                if current_imbalanced_yes is not None:
                    if (
                        last_imbalanced_yes is not None
                        and last_imbalanced_yes != current_imbalanced_yes
                    ):
                        swing_magnitude = abs(price - 0.5) + self.imbalance_threshold
                        severity = min(
                            1.0, swing_magnitude / self.IMBALANCE_SWING_NORMALIZER
                        )

                        moments.append(
                            InterestingMoment(
                                timestamp=tick["timestamp"],
                                market_id=market_id,
                                moment_type="imbalance_reversal",
                                reason=(
                                    "Market imbalance reversed "
                                    f"(price: {price:.2%})"
                                ),
                                severity=severity,
                                metrics={
                                    "price": price,
                                    "distance_from_middle": abs(price - 0.5),
                                },
                            )
                        )

                    last_imbalanced_yes = current_imbalanced_yes

        except Exception as exc:
            logger.error(
                "Error detecting imbalance reversals for %s: %s",
                market_id,
                exc,
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
            labels = fetch_history_labels(
                market_id=market_id,
                start=start,
                end=end,
                limit=10000,
                db_path=self.labels_db_path,
            )

            if len(labels) < self.min_alert_cluster_size:
                return moments

            labeled_events = []
            for label in labels:
                ts = parse_timestamp(label["timestamp"])
                if ts:
                    labeled_events.append((ts, label))

            labeled_events.sort(key=lambda x: x[0])

            window = timedelta(minutes=self.alert_clustering_window_minutes)

            for i in range(len(labeled_events)):
                window_start_time, start_label = labeled_events[i]
                window_end_time = window_start_time + window

                events_in_window = []
                for j in range(i, len(labeled_events)):
                    event_time, event_label = labeled_events[j]
                    if event_time <= window_end_time:
                        events_in_window.append(event_label)
                    else:
                        break

                if len(events_in_window) >= self.min_alert_cluster_size:
                    severity = min(
                        1.0,
                        len(events_in_window)
                        / (
                            self.min_alert_cluster_size
                            * self.ALERT_CLUSTER_SEVERITY_MULTIPLIER
                        ),
                    )

                    label_types = {e["label_type"] for e in events_in_window}

                    reason = (
                        f"{len(events_in_window)} alerts fired within "
                        f"{self.alert_clustering_window_minutes}m"
                    )

                    moments.append(
                        InterestingMoment(
                            timestamp=start_label["timestamp"],
                            market_id=start_label["market_id"],
                            moment_type="alert_cluster",
                            reason=reason,
                            severity=severity,
                            metrics={
                                "alert_count": len(events_in_window),
                                "unique_alert_types": len(label_types),
                            },
                        )
                    )

        except Exception as exc:
            logger.error("Error detecting alert clusters: %s", exc, exc_info=True)

        return moments
