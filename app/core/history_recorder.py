"""
History recorder for non-blocking market data recording.

Provides a queue-based async worker that records market ticks to the history
store without blocking the main loop. Implements sampling/throttling to avoid
over-recording.
"""

import threading
import time
from datetime import datetime
from queue import Queue, Empty
from typing import Any, Dict, Optional

from app.core.config import get_config
from app.core.history_store import append_tick
from app.core.logger import logger


class HistoryRecorder:
    """
    Non-blocking history recorder with sampling/throttling.

    Uses a background thread and queue to record market data without
    blocking the main loop. Implements sampling to avoid over-recording.

    Attributes:
        enabled: Whether history recording is enabled
        sampling_ms: Minimum interval between recordings per market (milliseconds)
    """

    def __init__(
        self,
        enabled: Optional[bool] = None,
        sampling_ms: Optional[int] = None,
    ):
        """
        Initialize the history recorder.

        Args:
            enabled: Whether to enable recording. If None, uses config value.
            sampling_ms: Sampling interval in ms. If None, uses config value.
        """
        config = get_config()

        self.enabled = enabled if enabled is not None else config.enable_history
        self.sampling_ms = (
            sampling_ms if sampling_ms is not None else config.history_sampling_ms
        )

        # Queue for pending tick writes
        self._queue: Queue[Dict[str, Any]] = Queue()

        # Track last recording time per market for sampling
        self._last_recorded: Dict[str, float] = {}

        # Worker thread and shutdown flag
        self._worker_thread: Optional[threading.Thread] = None
        self._shutdown = threading.Event()

        # Stats tracking
        self.stats = {
            "queued": 0,
            "recorded": 0,
            "skipped_sampling": 0,
            "errors": 0,
        }

    def start(self) -> None:
        """
        Start the background worker thread.

        Does nothing if history recording is disabled.
        """
        if not self.enabled:
            logger.debug("History recording is disabled")
            return

        if self._worker_thread is not None and self._worker_thread.is_alive():
            logger.warning("History recorder worker is already running")
            return

        self._shutdown.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="HistoryRecorderWorker",
            daemon=True,
        )
        self._worker_thread.start()
        logger.info(f"History recorder started (sampling: {self.sampling_ms}ms)")

    def stop(self) -> None:
        """
        Stop the background worker thread.

        Waits for the queue to drain before stopping.
        """
        if self._worker_thread is None or not self._worker_thread.is_alive():
            return

        logger.info("Stopping history recorder...")
        self._shutdown.set()

        # Wait for worker to finish (with timeout)
        self._worker_thread.join(timeout=5.0)

        if self._worker_thread.is_alive():
            logger.warning("History recorder worker did not stop cleanly")
        else:
            logger.info(
                f"History recorder stopped. Stats: "
                f"queued={self.stats['queued']}, "
                f"recorded={self.stats['recorded']}, "
                f"skipped={self.stats['skipped_sampling']}, "
                f"errors={self.stats['errors']}"
            )

    def record_tick(
        self,
        market_id: str,
        yes_price: float,
        no_price: float,
        volume: float = 0.0,
        depth_summary: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """
        Queue a market tick for recording.

        This method is non-blocking. It checks sampling constraints and
        queues the tick for the background worker to write.

        Args:
            market_id: Unique identifier for the market
            yes_price: Price of the 'Yes' outcome (0-1)
            no_price: Price of the 'No' outcome (0-1)
            volume: Trading volume at this tick
            depth_summary: Optional dictionary with order book depth info
            timestamp: Tick timestamp. If None, uses current time.

        Returns:
            True if tick was queued, False if skipped (disabled or sampling)
        """
        if not self.enabled:
            return False

        # Check sampling constraint
        current_time_ms = time.time() * 1000
        last_time_ms = self._last_recorded.get(market_id, 0)

        if current_time_ms - last_time_ms < self.sampling_ms:
            self.stats["skipped_sampling"] += 1
            return False

        # Update last recorded time
        self._last_recorded[market_id] = current_time_ms

        # Create tick data
        tick_data = {
            "market_id": market_id,
            "timestamp": timestamp or datetime.now(),
            "yes_price": yes_price,
            "no_price": no_price,
            "volume": volume,
            "depth_summary": depth_summary,
        }

        # Queue for background processing
        self._queue.put(tick_data)
        self.stats["queued"] += 1

        return True

    def _worker_loop(self) -> None:
        """
        Background worker loop that processes queued ticks.

        Runs until shutdown is signaled. Drains remaining queue items
        before exiting.
        """
        logger.debug("History recorder worker started")

        while not self._shutdown.is_set():
            try:
                # Wait for items with timeout to allow shutdown checks
                tick_data = self._queue.get(timeout=0.5)
                self._write_tick(tick_data)
            except Empty:
                continue

        # Drain remaining items on shutdown
        while not self._queue.empty():
            try:
                tick_data = self._queue.get_nowait()
                self._write_tick(tick_data)
            except Empty:
                break

        logger.debug("History recorder worker stopped")

    def _write_tick(self, tick_data: Dict[str, Any]) -> None:
        """
        Write a tick to the history store.

        Args:
            tick_data: Dictionary containing tick data
        """
        try:
            append_tick(
                market_id=tick_data["market_id"],
                timestamp=tick_data["timestamp"],
                yes_price=tick_data["yes_price"],
                no_price=tick_data["no_price"],
                volume=tick_data["volume"],
                depth_summary=tick_data.get("depth_summary"),
            )
            self.stats["recorded"] += 1
        except Exception as e:
            logger.error(f"Error writing tick to history store: {e}")
            self.stats["errors"] += 1


# Global singleton instance for convenience
_recorder: Optional[HistoryRecorder] = None


def get_history_recorder() -> HistoryRecorder:
    """
    Get the global history recorder singleton.

    Creates the recorder on first access if it doesn't exist.

    Returns:
        The global HistoryRecorder instance
    """
    global _recorder
    if _recorder is None:
        _recorder = HistoryRecorder()
    return _recorder


def start_history_recorder() -> HistoryRecorder:
    """
    Start the global history recorder.

    Convenience function that gets the singleton and starts it.

    Returns:
        The started HistoryRecorder instance
    """
    recorder = get_history_recorder()
    recorder.start()
    return recorder


def stop_history_recorder() -> None:
    """
    Stop the global history recorder.

    Convenience function that stops the singleton if it exists.
    """
    global _recorder
    if _recorder is not None:
        _recorder.stop()


def record_market_tick(
    market_id: str,
    yes_price: float,
    no_price: float,
    volume: float = 0.0,
    depth_summary: Optional[Dict[str, Any]] = None,
    timestamp: Optional[datetime] = None,
) -> bool:
    """
    Record a market tick using the global recorder.

    Convenience function that queues a tick on the global recorder.

    Args:
        market_id: Unique identifier for the market
        yes_price: Price of the 'Yes' outcome (0-1)
        no_price: Price of the 'No' outcome (0-1)
        volume: Trading volume at this tick
        depth_summary: Optional dictionary with order book depth info
        timestamp: Tick timestamp. If None, uses current time.

    Returns:
        True if tick was queued, False if skipped (disabled or sampling)
    """
    recorder = get_history_recorder()
    return recorder.record_tick(
        market_id=market_id,
        yes_price=yes_price,
        no_price=no_price,
        volume=volume,
        depth_summary=depth_summary,
        timestamp=timestamp,
    )
