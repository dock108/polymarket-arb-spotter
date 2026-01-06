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
from typing import Any, Callable, Dict, List, Optional, Union

from app.core.history_store import get_ticks, get_market_ids
from app.core.logger import logger


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
                        logger.error(
                            f"Error in on_tick callback: {e}", exc_info=True
                        )

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
