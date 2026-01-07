"""
Historical replay engine for Polymarket markets.

This module provides a replay engine that loads historical tick data from the
history store and plays them back at configurable speeds. Ticks are emitted
as if they were live WebSocket data, allowing all existing modules to run
against past markets safely.

Features:
- Load historical ticks from the history store
- Playback at different speeds: 1× (real-time), 10×, or custom multipliers
- Jump to specific events (skip time between ticks)
- Emit ticks as if they were live WebSocket data
- Support for callbacks to process replayed ticks
"""

import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union

from app.core.history_store import (
    get_ticks,
    get_market_ids,
    append_backtest_result,
)
from app.core.logger import logger, init_db, log_wallet_alert, _DB_PATH as _ALERTS_DB_PATH
from app.core.wallet_classifier import (
    classify_fresh_wallet,
    classify_high_confidence,
    classify_whale,
)
from app.core.wallet_feed import _WALLET_TRADES_DB_PATH, get_wallet_trades_in_range
from app.core.wallet_performance import evaluate_resolved_market, load_market_outcomes
from app.core.wallet_signals import WalletSignal, WalletSignalConfig, detect_wallet_signals
from app.core.privacy import format_wallet_profile_url

# Import depth scanner at module level for better performance
try:
    from app.core.depth_scanner import analyze_depth, detect_depth_signals
except ImportError:
    # Gracefully handle if depth_scanner is not available
    analyze_depth = None
    detect_depth_signals = None


class PlaybackSpeed(Enum):
    """Predefined playback speeds for historical replay."""

    REAL_TIME = 1.0  # 1× speed (real-time)
    FAST_10X = 10.0  # 10× speed
    JUMP_TO_EVENTS = 0.0  # No delay between events (instant playback)


class HistoricalReplayEngine:
    """
    Replay historical market ticks at configurable speeds.

    This engine loads tick data from the history store and plays them back
    as if they were arriving via live WebSocket. This allows testing and
    analysis of arbitrage detection algorithms against historical data.

    Attributes:
        db_path: Path to the history database
        speed_multiplier: Playback speed multiplier (e.g., 10.0 for 10× speed)
        jump_to_events: If True, skip time between ticks (instant playback)
    """

    def __init__(
        self,
        db_path: str = "data/market_history.db",
        speed: Union[PlaybackSpeed, float] = PlaybackSpeed.REAL_TIME,
    ):
        """
        Initialize the replay engine.

        Args:
            db_path: Path to the history database file
            speed: Playback speed (PlaybackSpeed enum or float multiplier)
                  - PlaybackSpeed.REAL_TIME: Play at 1× speed
                  - PlaybackSpeed.FAST_10X: Play at 10× speed
                  - PlaybackSpeed.JUMP_TO_EVENTS: Skip delays, instant playback
                  - Custom float: e.g., 5.0 for 5× speed
        """
        self.db_path = db_path

        # Set speed multiplier
        if isinstance(speed, PlaybackSpeed):
            if speed == PlaybackSpeed.JUMP_TO_EVENTS:
                self.speed_multiplier = 0.0
                self.jump_to_events = True
            else:
                self.speed_multiplier = speed.value
                self.jump_to_events = False
        else:
            self.speed_multiplier = max(0.0, float(speed))
            self.jump_to_events = self.speed_multiplier == 0.0

        # State tracking
        self._is_playing = False
        self._paused = False
        self._user_stopped = False  # Tracks if user explicitly called stop()

        logger.info(
            f"HistoricalReplayEngine initialized: "
            f"speed={self.speed_multiplier}×, "
            f"jump_to_events={self.jump_to_events}, "
            f"db_path={db_path}"
        )

    def set_speed(self, speed: Union[PlaybackSpeed, float]) -> None:
        """
        Change the playback speed.

        Args:
            speed: New playback speed (PlaybackSpeed enum or float multiplier)
        """
        if isinstance(speed, PlaybackSpeed):
            if speed == PlaybackSpeed.JUMP_TO_EVENTS:
                self.speed_multiplier = 0.0
                self.jump_to_events = True
            else:
                self.speed_multiplier = speed.value
                self.jump_to_events = False
        else:
            self.speed_multiplier = max(0.0, float(speed))
            self.jump_to_events = self.speed_multiplier == 0.0

        logger.info(
            f"Playback speed changed: {self.speed_multiplier}×, "
            f"jump_to_events={self.jump_to_events}"
        )

    def get_available_markets(self) -> List[str]:
        """
        Get a list of market IDs available in the history store.

        Returns:
            List of market IDs that have historical tick data
        """
        try:
            market_ids = get_market_ids(db_path=self.db_path)
            logger.debug(f"Found {len(market_ids)} markets in history store")
            return market_ids
        except Exception as e:
            logger.error(f"Error getting available markets: {e}", exc_info=True)
            return []

    def replay_market(
        self,
        market_id: str,
        start: Optional[Union[datetime, str]] = None,
        end: Optional[Union[datetime, str]] = None,
        on_tick: Optional[Callable[[Dict[str, Any]], None]] = None,
        limit: int = 10000,
    ) -> int:
        """
        Replay historical ticks for a single market.

        Loads ticks from the history store and emits them with timing
        that respects the configured playback speed. Calls the on_tick
        callback for each tick, simulating live WebSocket data.

        Args:
            market_id: Market ID to replay
            start: Start timestamp (datetime or ISO string). If None, starts from beginning.
            end: End timestamp (datetime or ISO string). If None, plays to end.
            on_tick: Callback function called for each tick with tick data dict
            limit: Maximum number of ticks to replay (default: 10000)

        Returns:
            Number of ticks replayed

        Example:
            >>> def handle_tick(tick):
            ...     print(f"Tick: {tick['timestamp']} - Yes: {tick['yes_price']}")
            >>> engine = HistoricalReplayEngine(speed=PlaybackSpeed.FAST_10X)
            >>> count = engine.replay_market("market_123", on_tick=handle_tick)
            >>> print(f"Replayed {count} ticks")
        """
        logger.info(
            f"Starting replay for market {market_id} "
            f"(start={start}, end={end}, limit={limit})"
        )

        try:
            # Load ticks from history store
            ticks = get_ticks(
                market_id=market_id,
                start=start,
                end=end,
                limit=limit,
                db_path=self.db_path,
            )

            if not ticks:
                logger.warning(f"No ticks found for market {market_id}")
                return 0

            logger.info(f"Loaded {len(ticks)} ticks for replay")

            # Track state
            self._is_playing = True
            self._paused = False
            self._user_stopped = False  # Reset user stop flag
            replayed_count = 0
            previous_timestamp = None

            for i, tick in enumerate(ticks):
                # Check if user stopped replay
                if self._user_stopped:
                    logger.info("Replay stopped by user")
                    break

                # Handle pause
                while self._paused and self._is_playing:
                    time.sleep(0.1)
                    continue

                # Calculate delay based on timestamp difference
                if previous_timestamp is not None and not self.jump_to_events:
                    current_time = self._parse_timestamp(tick["timestamp"])
                    prev_time = self._parse_timestamp(previous_timestamp)

                    if current_time and prev_time:
                        real_delay_seconds = (current_time - prev_time).total_seconds()

                        # Apply speed multiplier
                        if self.speed_multiplier > 0:
                            adjusted_delay = real_delay_seconds / self.speed_multiplier
                            if adjusted_delay > 0:
                                time.sleep(adjusted_delay)

                # Emit the tick via callback
                if on_tick:
                    try:
                        on_tick(tick)
                    except Exception as e:
                        logger.error(f"Error in on_tick callback: {e}", exc_info=True)

                previous_timestamp = tick["timestamp"]
                replayed_count += 1

                # Periodic logging
                if replayed_count % 100 == 0:
                    logger.debug(
                        f"Replayed {replayed_count}/{len(ticks)} ticks "
                        f"({replayed_count/len(ticks)*100:.1f}%)"
                    )

            self._is_playing = False
            logger.info(
                f"Replay complete for market {market_id}: "
                f"replayed {replayed_count} ticks"
            )
            return replayed_count

        except Exception as e:
            logger.error(f"Error during replay: {e}", exc_info=True)
            self._is_playing = False
            return 0

    def replay_markets(
        self,
        market_ids: List[str],
        start: Optional[Union[datetime, str]] = None,
        end: Optional[Union[datetime, str]] = None,
        on_tick: Optional[Callable[[Dict[str, Any]], None]] = None,
        limit_per_market: int = 10000,
    ) -> Dict[str, int]:
        """
        Replay historical ticks for multiple markets sequentially.

        Args:
            market_ids: List of market IDs to replay
            start: Start timestamp for all markets
            end: End timestamp for all markets
            on_tick: Callback function called for each tick
            limit_per_market: Maximum ticks per market (default: 10000)

        Returns:
            Dictionary mapping market_id to number of ticks replayed

        Example:
            >>> engine = HistoricalReplayEngine(speed=PlaybackSpeed.JUMP_TO_EVENTS)
            >>> results = engine.replay_markets(["market_1", "market_2"], on_tick=handler)
            >>> print(f"Total ticks: {sum(results.values())}")
        """
        logger.info(f"Starting multi-market replay for {len(market_ids)} markets")

        results = {}
        for market_id in market_ids:
            # Check if user stopped replay
            if self._user_stopped:
                logger.info("Multi-market replay stopped by user")
                break

            count = self.replay_market(
                market_id=market_id,
                start=start,
                end=end,
                on_tick=on_tick,
                limit=limit_per_market,
            )
            results[market_id] = count

        total_ticks = sum(results.values())
        logger.info(
            f"Multi-market replay complete: {len(results)} markets, "
            f"{total_ticks} total ticks"
        )
        return results

    def replay_all_markets(
        self,
        start: Optional[Union[datetime, str]] = None,
        end: Optional[Union[datetime, str]] = None,
        on_tick: Optional[Callable[[Dict[str, Any]], None]] = None,
        limit_per_market: int = 10000,
    ) -> Dict[str, int]:
        """
        Replay all markets available in the history store.

        Args:
            start: Start timestamp for all markets
            end: End timestamp for all markets
            on_tick: Callback function called for each tick
            limit_per_market: Maximum ticks per market (default: 10000)

        Returns:
            Dictionary mapping market_id to number of ticks replayed
        """
        market_ids = self.get_available_markets()
        if not market_ids:
            logger.warning("No markets found in history store")
            return {}

        logger.info(f"Replaying all {len(market_ids)} markets from history store")
        return self.replay_markets(
            market_ids=market_ids,
            start=start,
            end=end,
            on_tick=on_tick,
            limit_per_market=limit_per_market,
        )

    def stop(self) -> None:
        """
        Stop the current replay.

        This will cause replay_market() to exit early on the next tick.
        """
        if self._is_playing:
            logger.info("Stopping replay...")
            self._user_stopped = True
            self._is_playing = False

    def pause(self) -> None:
        """
        Pause the current replay.

        Call resume() to continue playback.
        """
        if self._is_playing and not self._paused:
            logger.info("Pausing replay")
            self._paused = True

    def resume(self) -> None:
        """
        Resume a paused replay.
        """
        if self._is_playing and self._paused:
            logger.info("Resuming replay")
            self._paused = False

    def is_playing(self) -> bool:
        """
        Check if replay is currently active.

        Returns:
            True if replay is in progress, False otherwise
        """
        return self._is_playing

    def is_paused(self) -> bool:
        """
        Check if replay is currently paused.

        Returns:
            True if replay is paused, False otherwise
        """
        return self._paused

    @staticmethod
    def _parse_timestamp(timestamp: Union[str, datetime]) -> Optional[datetime]:
        """
        Parse a timestamp string to a datetime object.

        Args:
            timestamp: ISO format timestamp string or datetime object

        Returns:
            datetime object or None if parsing fails
        """
        if isinstance(timestamp, datetime):
            return timestamp

        try:
            # Try parsing ISO format
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse timestamp '{timestamp}': {e}")
            return None


def create_replay_engine(
    db_path: str = "data/market_history.db",
    speed: Union[PlaybackSpeed, float] = PlaybackSpeed.REAL_TIME,
) -> HistoricalReplayEngine:
    """
    Convenience function to create a replay engine.

    Args:
        db_path: Path to the history database file
        speed: Playback speed (PlaybackSpeed enum or float multiplier)

    Returns:
        Configured HistoricalReplayEngine instance

    Example:
        >>> engine = create_replay_engine(speed=PlaybackSpeed.FAST_10X)
        >>> engine.replay_market("market_123", on_tick=my_handler)
    """
    return HistoricalReplayEngine(db_path=db_path, speed=speed)


class BacktestEngine:
    """
    Backtest engine for simulating alerts on historical data.

    This class pipes replay events through various detection strategies
    (arbitrage detector, price alerts, depth scanner) and records
    simulated outcomes to evaluate tool performance on historical data.

    Attributes:
        replay_engine: HistoricalReplayEngine for loading historical data
        db_path: Path to database for storing backtest results
        arb_detector: Optional ArbitrageDetector instance
        price_alerts: Optional list of PriceAlert configurations
        depth_config: Optional depth scanner configuration
    """

    def __init__(
        self,
        db_path: str = "data/market_history.db",
        speed: Union[PlaybackSpeed, float] = PlaybackSpeed.JUMP_TO_EVENTS,
        wallet_db_path: str = _WALLET_TRADES_DB_PATH,
        alerts_db_path: str = _ALERTS_DB_PATH,
    ):
        """
        Initialize the backtest engine.

        Args:
            db_path: Path to the history database file
            speed: Playback speed for replay (default: JUMP_TO_EVENTS for fast backtesting)
        """
        self.replay_engine = HistoricalReplayEngine(db_path=db_path, speed=speed)
        self.db_path = db_path
        self.wallet_db_path = wallet_db_path
        self.alerts_db_path = alerts_db_path
        self.arb_detector = None
        self.price_alerts = []
        self.depth_config = None
        self.wallet_signal_config: Optional[WalletSignalConfig] = None
        self.wallet_market_metadata: Dict[str, Dict[str, Any]] = {}
        self.wallet_replay_enabled = False
        self._market_outcomes: Dict[str, Dict[str, Any]] = {}
        self._wallet_markets_evaluated: Set[str] = set()

        # Statistics
        self.stats = {
            "ticks_processed": 0,
            "arb_signals": 0,
            "price_alerts_triggered": 0,
            "depth_signals": 0,
            "markets_analyzed": set(),
            "wallet_trades_processed": 0,
            "wallet_signals_detected": 0,
            "wallet_alerts_logged": 0,
            "wallet_markets_scored": 0,
            "wallet_signals_scored": 0,
        }

        logger.info("BacktestEngine initialized")

    def set_arb_detector(self, detector) -> None:
        """
        Set the arbitrage detector for backtesting.

        Args:
            detector: ArbitrageDetector instance
        """
        self.arb_detector = detector
        logger.info("Arbitrage detector configured for backtest")

    def add_price_alert(
        self, market_id: str, direction: str, target_price: float
    ) -> None:
        """
        Add a price alert to backtest.

        Args:
            market_id: Market ID to monitor
            direction: Alert direction ("above" or "below")
            target_price: Price threshold
        """
        self.price_alerts.append(
            {
                "market_id": market_id,
                "direction": direction,
                "target_price": target_price,
                "triggered": False,
            }
        )
        logger.info(f"Added price alert: {market_id} {direction} {target_price}")

    def set_depth_config(self, config: Dict[str, Any]) -> None:
        """
        Set depth scanner configuration for backtesting.

        Args:
            config: Depth configuration dictionary
        """
        self.depth_config = config
        logger.info("Depth scanner configured for backtest")

    def enable_wallet_replay(
        self,
        config: Optional[WalletSignalConfig] = None,
        market_metadata_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        """
        Enable wallet activity replay during backtests.

        Args:
            config: Optional wallet signal configuration overrides.
            market_metadata_by_id: Optional market metadata for signal heuristics.
        """
        self.wallet_signal_config = config or WalletSignalConfig()
        self.wallet_market_metadata = market_metadata_by_id or {}
        self.wallet_replay_enabled = True
        logger.info("Wallet replay enabled for backtest")

    def disable_wallet_replay(self) -> None:
        """Disable wallet activity replay during backtests."""
        self.wallet_replay_enabled = False
        logger.info("Wallet replay disabled for backtest")

    def _simulate_wallet_activity(
        self,
        market_id: str,
        start: Optional[Union[datetime, str]] = None,
        end: Optional[Union[datetime, str]] = None,
        limit: Optional[int] = None,
    ) -> None:
        """Simulate wallet activity and generate wallet alerts."""
        trades = get_wallet_trades_in_range(
            market_id=market_id,
            start=start,
            end=end,
            limit=limit,
            db_path=self.wallet_db_path,
        )

        if not trades:
            return

        self.stats["wallet_trades_processed"] += len(trades)
        signals = detect_wallet_signals(
            trades,
            db_path=self.wallet_db_path,
            config=self.wallet_signal_config,
            market_metadata_by_id=self.wallet_market_metadata,
        )
        if not signals:
            return

        init_db(self.alerts_db_path)

        self.stats["wallet_signals_detected"] += len(signals)
        for signal in signals:
            log_wallet_alert(
                self._build_wallet_alert_payload(signal),
                db_path=self.alerts_db_path,
            )
            self.stats["wallet_alerts_logged"] += 1

        self._evaluate_wallet_signals(market_id)

    def _build_wallet_alert_payload(self, signal: WalletSignal) -> Dict[str, Any]:
        """Build wallet alert payload for storage."""
        return {
            "timestamp": signal.timestamp,
            "wallet": signal.wallet,
            "market_id": signal.market_id,
            "bet_size": self._extract_bet_size(signal.evidence),
            "classification": self._classify_wallet_label(signal.wallet),
            "signal_type": signal.signal_type,
            "profile_url": format_wallet_profile_url(signal.wallet),
            "evidence": signal.evidence,
        }

    def _evaluate_wallet_signals(self, market_id: str) -> None:
        """Evaluate wallet signal outcomes if market resolution is known."""
        if market_id in self._wallet_markets_evaluated:
            return

        outcome_info = self._market_outcomes.get(market_id)
        if not outcome_info:
            return

        outcome = outcome_info.get("outcome")
        if not outcome:
            return

        resolved_at = outcome_info.get("resolved_at")
        resolved_timestamp = (
            HistoricalReplayEngine._parse_timestamp(resolved_at)
            if resolved_at
            else None
        )

        summary = evaluate_resolved_market(
            market_id=market_id,
            outcome=outcome,
            resolved_at=resolved_timestamp,
            wallet_db_path=self.wallet_db_path,
            alerts_db_path=self.alerts_db_path,
        )
        self.stats["wallet_markets_scored"] += 1
        self.stats["wallet_signals_scored"] += summary.get("signals_scored", 0)
        self._wallet_markets_evaluated.add(market_id)

    @staticmethod
    def _extract_bet_size(evidence: Dict[str, Any]) -> Optional[float]:
        """Extract a bet size from wallet signal evidence."""
        for key in ("size", "total_size", "bet_size"):
            value = evidence.get(key)
            if isinstance(value, (int, float)):
                return float(value)
        return None

    def _classify_wallet_label(self, wallet: str) -> str:
        """Classify wallet for backtest alert logging."""
        if not wallet:
            return "unknown"
        if classify_fresh_wallet(wallet, db_path=self.wallet_db_path):
            return "fresh"
        if classify_whale(wallet, db_path=self.wallet_db_path):
            return "whale"
        if classify_high_confidence(wallet, db_path=self.wallet_db_path):
            return "pro"
        return "unknown"

    def _process_tick_arb_detector(self, tick: Dict[str, Any]) -> None:
        """
        Process tick through arbitrage detector and record results.

        Args:
            tick: Tick data dictionary
        """
        if not self.arb_detector:
            return

        try:
            # Convert tick to market snapshot format
            snapshot = {
                "id": tick["market_id"],
                "outcomes": [
                    {
                        "name": "Yes",
                        "price": tick["yes_price"],
                        "volume": tick.get("volume", 0) / 2,
                    },
                    {
                        "name": "No",
                        "price": tick["no_price"],
                        "volume": tick.get("volume", 0) / 2,
                    },
                ],
            }

            # Detect opportunities
            opportunities = self.arb_detector.detect_opportunities([snapshot])

            if opportunities:
                for opp in opportunities:
                    self.stats["arb_signals"] += 1

                    # Record backtest result
                    signal_data = {
                        "opportunity_type": opp.opportunity_type,
                        "expected_profit": opp.expected_profit,
                        "expected_return_pct": opp.expected_return_pct,
                        "yes_price": tick["yes_price"],
                        "no_price": tick["no_price"],
                        "price_sum": tick["yes_price"] + tick["no_price"],
                    }

                    append_backtest_result(
                        strategy="arb_detector",
                        market_id=tick["market_id"],
                        timestamp=tick["timestamp"],
                        signal=signal_data,
                        simulated_outcome="would_trigger",
                        notes=f"Arbitrage opportunity: {opp.expected_return_pct:.2f}% return",
                        db_path=self.db_path,
                    )

        except Exception as e:
            logger.error(f"Error processing tick for arb detector: {e}", exc_info=True)

    def _process_tick_price_alerts(self, tick: Dict[str, Any]) -> None:
        """
        Process tick through price alerts and record results.

        Args:
            tick: Tick data dictionary
        """
        if not self.price_alerts:
            return

        try:
            # Check each configured price alert
            for alert_config in self.price_alerts:
                # Only check alerts for this market
                if alert_config["market_id"] != tick["market_id"]:
                    continue

                # Use yes_price as current price
                current_price = tick["yes_price"]
                target_price = alert_config["target_price"]
                direction = alert_config["direction"]

                # Check if alert would trigger
                triggered = False
                if direction == "above" and current_price > target_price:
                    triggered = True
                elif direction == "below" and current_price < target_price:
                    triggered = True

                if triggered and not alert_config["triggered"]:
                    # Mark as triggered to avoid duplicate signals
                    alert_config["triggered"] = True
                    self.stats["price_alerts_triggered"] += 1

                    # Record backtest result
                    signal_data = {
                        "direction": direction,
                        "target_price": target_price,
                        "current_price": current_price,
                        "alert_type": "price_alert",
                    }

                    outcome = "would_trigger"
                    notes = f"Price alert triggered: {current_price:.4f} {direction} {target_price:.4f}"

                    append_backtest_result(
                        strategy="price_alert",
                        market_id=tick["market_id"],
                        timestamp=tick["timestamp"],
                        signal=signal_data,
                        simulated_outcome=outcome,
                        notes=notes,
                        db_path=self.db_path,
                    )

        except Exception as e:
            logger.error(f"Error processing tick for price alerts: {e}", exc_info=True)

    def _process_tick_depth_scanner(self, tick: Dict[str, Any]) -> None:
        """
        Process tick through depth scanner and record results.

        Args:
            tick: Tick data dictionary
        """
        if not self.depth_config:
            return

        # Check if depth scanner functions are available
        if analyze_depth is None or detect_depth_signals is None:
            logger.warning(
                "Depth scanner functions not available, skipping depth analysis"
            )
            return

        try:
            # Check if tick has depth summary
            depth_summary = tick.get("depth_summary")
            if not depth_summary:
                return

            # Analyze depth if we have orderbook data
            if "bids" in depth_summary and "asks" in depth_summary:
                metrics = analyze_depth(depth_summary)
                signals = detect_depth_signals(metrics, self.depth_config)

                for signal in signals:
                    if signal.triggered:
                        self.stats["depth_signals"] += 1

                        # Record backtest result
                        signal_data = {
                            "signal_type": signal.signal_type,
                            "metrics": signal.metrics,
                            "reason": signal.reason,
                        }

                        append_backtest_result(
                            strategy="depth_scanner",
                            market_id=tick["market_id"],
                            timestamp=tick["timestamp"],
                            signal=signal_data,
                            simulated_outcome="would_trigger",
                            notes=signal.reason,
                            db_path=self.db_path,
                        )

        except Exception as e:
            logger.error(f"Error processing tick for depth scanner: {e}", exc_info=True)

    def _process_tick(self, tick: Dict[str, Any]) -> None:
        """
        Process a single tick through all configured strategies.

        Args:
            tick: Tick data dictionary
        """
        self.stats["ticks_processed"] += 1
        self.stats["markets_analyzed"].add(tick["market_id"])

        # Process through each strategy
        self._process_tick_arb_detector(tick)
        self._process_tick_price_alerts(tick)
        self._process_tick_depth_scanner(tick)

    def run_backtest(
        self,
        market_ids: Optional[List[str]] = None,
        start: Optional[Union[datetime, str]] = None,
        end: Optional[Union[datetime, str]] = None,
        limit_per_market: int = 10000,
    ) -> Dict[str, Any]:
        """
        Run backtest on historical data.

        This method replays historical ticks through all configured strategies
        and records simulated outcomes to the backtest_results table.

        Args:
            market_ids: List of market IDs to backtest. If None, tests all available markets.
            start: Start timestamp for backtest
            end: End timestamp for backtest
            limit_per_market: Maximum ticks per market

        Returns:
            Dictionary containing backtest statistics

        Example:
            >>> engine = BacktestEngine()
            >>> engine.set_arb_detector(ArbitrageDetector())
            >>> engine.add_price_alert("market_123", "above", 0.70)
            >>> results = engine.run_backtest(market_ids=["market_123"])
            >>> print(f"Processed {results['ticks_processed']} ticks")
        """
        logger.info("Starting backtest...")

        # Reset statistics
        self.stats = {
            "ticks_processed": 0,
            "arb_signals": 0,
            "price_alerts_triggered": 0,
            "depth_signals": 0,
            "markets_analyzed": set(),
            "wallet_trades_processed": 0,
            "wallet_signals_detected": 0,
            "wallet_alerts_logged": 0,
            "wallet_markets_scored": 0,
            "wallet_signals_scored": 0,
        }

        # Reset price alert triggered states for fresh backtest
        for alert in self.price_alerts:
            alert["triggered"] = False

        if self.wallet_replay_enabled:
            self._market_outcomes = load_market_outcomes(self.wallet_db_path)
            self._wallet_markets_evaluated = set()
            init_db(self.alerts_db_path)

        try:
            if market_ids:
                markets_to_replay = market_ids
            else:
                markets_to_replay = self.replay_engine.get_available_markets()

            for market_id in markets_to_replay:
                self.replay_engine.replay_market(
                    market_id=market_id,
                    start=start,
                    end=end,
                    on_tick=self._process_tick,
                    limit=limit_per_market,
                )

                if self.wallet_replay_enabled:
                    self._simulate_wallet_activity(
                        market_id=market_id,
                        start=start,
                        end=end,
                        limit=limit_per_market,
                    )

            # Convert set to count for return value
            markets_count = len(self.stats["markets_analyzed"])
            return_stats = dict(self.stats)
            return_stats["markets_analyzed"] = markets_count

            logger.info(
                f"Backtest complete: {self.stats['ticks_processed']} ticks, "
                f"{self.stats['arb_signals']} arb signals, "
                f"{self.stats['price_alerts_triggered']} price alerts, "
                f"{self.stats['depth_signals']} depth signals, "
                f"{self.stats['wallet_signals_detected']} wallet signals"
            )

            return return_stats

        except Exception as e:
            logger.error(f"Error during backtest: {e}", exc_info=True)
            markets_count = len(self.stats["markets_analyzed"])
            return_stats = dict(self.stats)
            return_stats["markets_analyzed"] = markets_count
            return return_stats

    def get_summary(self) -> Dict[str, Any]:
        """
        Get backtest summary statistics.

        Returns:
            Dictionary with backtest statistics
        """
        return {
            "ticks_processed": self.stats["ticks_processed"],
            "arb_signals": self.stats["arb_signals"],
            "price_alerts_triggered": self.stats["price_alerts_triggered"],
            "depth_signals": self.stats["depth_signals"],
            "markets_analyzed": len(self.stats["markets_analyzed"]),
            "wallet_trades_processed": self.stats["wallet_trades_processed"],
            "wallet_signals_detected": self.stats["wallet_signals_detected"],
            "wallet_alerts_logged": self.stats["wallet_alerts_logged"],
            "wallet_markets_scored": self.stats["wallet_markets_scored"],
            "wallet_signals_scored": self.stats["wallet_signals_scored"],
        }


def create_backtest_engine(
    db_path: str = "data/market_history.db",
    speed: Union[PlaybackSpeed, float] = PlaybackSpeed.JUMP_TO_EVENTS,
    wallet_db_path: str = _WALLET_TRADES_DB_PATH,
    alerts_db_path: str = _ALERTS_DB_PATH,
) -> BacktestEngine:
    """
    Convenience function to create a backtest engine.

    Args:
        db_path: Path to the history database file
        speed: Playback speed (default: JUMP_TO_EVENTS for fast backtesting)
        wallet_db_path: Path to wallet trades database (for wallet replay)
        alerts_db_path: Path to alerts database for wallet alerts

    Returns:
        Configured BacktestEngine instance

    Example:
        >>> engine = create_backtest_engine()
        >>> engine.set_arb_detector(ArbitrageDetector())
        >>> results = engine.run_backtest()
    """
    return BacktestEngine(
        db_path=db_path,
        speed=speed,
        wallet_db_path=wallet_db_path,
        alerts_db_path=alerts_db_path,
    )
