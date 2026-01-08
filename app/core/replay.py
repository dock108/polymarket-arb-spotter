"""
Historical replay engine for Polymarket markets.
Plays back historical tick data from the history store.
"""

import time
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union

from app.core.history_store import get_ticks, get_market_ids
from app.core.logger import logger

class PlaybackSpeed(Enum):
    """Predefined playback speeds for historical replay."""
    REAL_TIME = 1.0  # 1× speed
    FAST_10X = 10.0  # 10× speed
    JUMP_TO_EVENTS = 0.0  # Skip delays

class HistoricalReplayEngine:
    """
    Replay historical market ticks at configurable speeds.
    """

    def __init__(
        self,
        db_path: str = "data/market_history.db",
        speed: Union[PlaybackSpeed, float] = PlaybackSpeed.REAL_TIME,
    ):
        self.db_path = db_path
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

        self._is_playing = False
        self._callbacks: List[Callable[[Dict[str, Any]], None]] = []

    def register_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a function to receive replayed ticks."""
        self._callbacks.append(callback)

    def run(
        self,
        market_id: Optional[str] = None,
        start: Optional[Union[datetime, str]] = None,
        end: Optional[Union[datetime, str]] = None,
        limit: int = 10000,
    ) -> None:
        """Execute the replay."""
        logger.info(f"Starting replay for market={market_id}")
        self._is_playing = True
        
        ticks = get_ticks(market_id=market_id, start=start, end=end, limit=limit, db_path=self.db_path)
        if not ticks:
            logger.warning("No ticks found for replay")
            return

        last_tick_time = None
        for tick in ticks:
            if not self._is_playing: break
            
            curr_time = datetime.fromisoformat(tick["timestamp"].replace("Z", "+00:00"))
            
            if last_tick_time and not self.jump_to_events:
                delay = (curr_time - last_tick_time).total_seconds() / self.speed_multiplier
                if delay > 0: time.sleep(min(delay, 5.0)) # Cap delay at 5s for usability
            
            for cb in self._callbacks:
                try: cb(tick)
                except Exception as e: logger.error(f"Callback error: {e}")
            
            last_tick_time = curr_time
            
        self._is_playing = False
        logger.info("Replay complete")

    def stop(self) -> None:
        """Stop the replay playback."""
        self._is_playing = False
