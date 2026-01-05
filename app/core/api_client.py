"""
API client for Polymarket data fetching.

This module provides a read-only API client for Polymarket that fetches
market data, order books, and supports real-time price streaming via WebSocket.

NOTE: This client is designed for data fetching only and does NOT place orders.
"""

import json
import requests
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Generator, List, Optional

from app.core.logger import logger


@dataclass
class NormalizedOrderBook:
    """Normalized order book with best bid/ask for yes and no outcomes."""

    yes_best_bid: Optional[float] = None
    yes_best_ask: Optional[float] = None
    no_best_bid: Optional[float] = None
    no_best_ask: Optional[float] = None
    market_id: str = ""
    timestamp: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "yes_best_bid": self.yes_best_bid,
            "yes_best_ask": self.yes_best_ask,
            "no_best_bid": self.no_best_bid,
            "no_best_ask": self.no_best_ask,
            "market_id": self.market_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class PolymarketAPIClient:
    """
    Client for interacting with Polymarket API.

    This is a read-only client that fetches market data and order books.
    It does NOT support order placement.
    """

    # Polymarket public API endpoints
    DEFAULT_GAMMA_URL = "https://gamma-api.polymarket.com"
    DEFAULT_CLOB_URL = "https://clob.polymarket.com"
    DEFAULT_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

    # Retry configuration
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1.0  # seconds
    DEFAULT_TIMEOUT = 30  # seconds

    def __init__(
        self,
        base_url: str = DEFAULT_GAMMA_URL,
        clob_url: str = DEFAULT_CLOB_URL,
        ws_url: str = DEFAULT_WS_URL,
        api_key: Optional[str] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """
        Initialize API client.

        Args:
            base_url: Base URL for Polymarket Gamma API (markets data)
            clob_url: Base URL for Polymarket CLOB API (order books)
            ws_url: WebSocket URL for real-time price streaming
            api_key: Optional API key for authentication (not required for public data)
            max_retries: Maximum number of retry attempts for failed requests
            retry_delay: Base delay between retries (exponential backoff is applied)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.clob_url = clob_url.rstrip("/")
        self.ws_url = ws_url
        self.api_key = api_key
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.session = requests.Session()

        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})

        # WebSocket state
        self._ws = None
        self._ws_thread = None
        self._ws_running = False
        self._ws_callbacks: List[Callable[[Dict[str, Any]], None]] = []

        logger.info(f"PolymarketAPIClient initialized with base_url: {base_url}")

    def _request_with_retry(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional[requests.Response]:
        """
        Make an HTTP request with retry logic and exponential backoff.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            params: Query parameters
            **kwargs: Additional arguments passed to requests

        Returns:
            Response object if successful, None otherwise
        """
        kwargs.setdefault("timeout", self.timeout)

        for attempt in range(self.max_retries):
            try:
                response = self.session.request(method, url, params=params, **kwargs)
                response.raise_for_status()
                return response
            except requests.exceptions.Timeout:
                logger.warning(
                    f"Request timeout (attempt {attempt + 1}/{self.max_retries}): {url}"
                )
            except requests.exceptions.ConnectionError as e:
                logger.warning(
                    f"Connection error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
            except requests.exceptions.HTTPError as e:
                # Don't retry on 4xx errors (client errors)
                if e.response is not None and 400 <= e.response.status_code < 500:
                    logger.error(f"Client error {e.response.status_code}: {url}")
                    return None
                logger.warning(
                    f"HTTP error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
            except requests.RequestException as e:
                logger.warning(
                    f"Request error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )

            # Exponential backoff
            if attempt < self.max_retries - 1:
                delay = self.retry_delay * (2**attempt)
                logger.info(f"Retrying in {delay:.1f} seconds...")
                time.sleep(delay)

        logger.error(f"All {self.max_retries} retry attempts failed for: {url}")
        return None

    def fetch_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Fetch markets from Polymarket.

        Args:
            limit: Maximum number of markets to fetch (max 100)
            offset: Offset for pagination
            active_only: Only fetch active/open markets

        Returns:
            List of market data dictionaries
        """
        logger.info(f"Fetching markets: limit={limit}, offset={offset}")

        params: Dict[str, Any] = {
            "limit": min(limit, 100),
            "offset": offset,
        }

        if active_only:
            params["active"] = "true"
            params["closed"] = "false"

        url = f"{self.base_url}/markets"
        response = self._request_with_retry("GET", url, params=params)

        if response is None:
            return []

        try:
            data = response.json()
            # Handle both list and paginated response formats
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "data" in data:
                return data.get("data", [])
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode markets response: {e}")
            return []

    def fetch_orderbook(self, market_id: str) -> Optional[NormalizedOrderBook]:
        """
        Fetch and normalize orderbook data for a market.

        The order book is normalized to provide best bid/ask prices for
        both YES and NO outcomes.

        Args:
            market_id: Market token ID (condition_id or token_id)

        Returns:
            NormalizedOrderBook with best prices, or None if unavailable
        """
        logger.info(f"Fetching orderbook for: {market_id}")

        url = f"{self.clob_url}/book"
        params = {"token_id": market_id}

        response = self._request_with_retry("GET", url, params=params)

        if response is None:
            return None

        try:
            data = response.json()
            return self._normalize_orderbook(data, market_id)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode orderbook response: {e}")
            return None

    def _normalize_orderbook(
        self, raw_orderbook: Dict[str, Any], market_id: str
    ) -> NormalizedOrderBook:
        """
        Normalize raw orderbook data into standardized format.

        Polymarket order books have "bids" (buy orders) and "asks" (sell orders).
        For a YES token:
        - Best bid = highest price someone is willing to pay for YES
        - Best ask = lowest price someone is willing to sell YES for

        The NO price can be derived as (1 - YES price) for binary markets.

        Args:
            raw_orderbook: Raw orderbook data from API
            market_id: Market identifier

        Returns:
            NormalizedOrderBook with best prices
        """
        normalized = NormalizedOrderBook(
            market_id=market_id,
            timestamp=datetime.now(),
        )

        # Extract bids (buy orders) - sorted by price descending
        bids = raw_orderbook.get("bids", [])
        if bids:
            # Find the highest bid (best bid)
            sorted_bids = sorted(
                bids, key=lambda x: float(x.get("price", 0)), reverse=True
            )
            if sorted_bids:
                normalized.yes_best_bid = float(sorted_bids[0].get("price", 0))

        # Extract asks (sell orders) - sorted by price ascending
        asks = raw_orderbook.get("asks", [])
        if asks:
            # Find the lowest ask (best ask)
            sorted_asks = sorted(asks, key=lambda x: float(x.get("price", 0)))
            if sorted_asks:
                normalized.yes_best_ask = float(sorted_asks[0].get("price", 0))

        # Derive NO prices from YES prices (binary market: YES + NO = 1)
        if normalized.yes_best_ask is not None:
            # If I can buy YES at yes_best_ask, that implies I can sell NO at (1 - yes_best_ask)
            # So no_best_bid = 1 - yes_best_ask
            normalized.no_best_bid = round(1.0 - normalized.yes_best_ask, 4)

        if normalized.yes_best_bid is not None:
            # If I can sell YES at yes_best_bid, that implies I can buy NO at (1 - yes_best_bid)
            # So no_best_ask = 1 - yes_best_bid
            normalized.no_best_ask = round(1.0 - normalized.yes_best_bid, 4)

        return normalized

    def websocket_stream_prices(
        self,
        market_ids: List[str],
        on_message: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
        auto_reconnect: bool = True,
        reconnect_delay: float = 5.0,
        max_reconnect_attempts: int = 10,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Stream real-time price updates via WebSocket.

        This method supports two usage patterns:
        1. Generator pattern: Iterate over the returned generator to receive messages
        2. Callback pattern: Provide an on_message callback to handle messages

        Args:
            market_ids: List of market/token IDs to subscribe to
            on_message: Optional callback for each price update message
            on_error: Optional callback for errors
            on_close: Optional callback when connection closes
            auto_reconnect: Whether to automatically reconnect on disconnect
            reconnect_delay: Base delay between reconnection attempts (seconds)
            max_reconnect_attempts: Maximum number of reconnection attempts

        Yields:
            Price update messages as dictionaries
        """
        try:
            import websocket
        except ImportError:
            logger.error(
                "websocket-client package is required for WebSocket streaming. "
                "Install it with: pip install websocket-client"
            )
            return

        if not market_ids:
            logger.warning("No market IDs provided for WebSocket streaming")
            return

        message_queue: List[Dict[str, Any]] = []
        reconnect_attempts = 0
        should_reconnect = True

        def _on_message(ws: Any, message: str) -> None:
            """Handle incoming WebSocket message."""
            nonlocal reconnect_attempts
            reconnect_attempts = 0  # Reset on successful message

            try:
                data = json.loads(message)
                if on_message:
                    on_message(data)
                message_queue.append(data)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode WebSocket message: {e}")

        def _on_error(ws: Any, error: Exception) -> None:
            """Handle WebSocket error."""
            logger.error(f"WebSocket error: {error}")
            if on_error:
                on_error(error)

        def _on_close(ws: Any, close_status_code: Any, close_msg: Any) -> None:
            """Handle WebSocket connection close."""
            logger.info(
                f"WebSocket closed: code={close_status_code}, msg={close_msg}"
            )
            if on_close:
                on_close()

        def _on_open(ws: Any) -> None:
            """Handle WebSocket connection open."""
            logger.info(f"WebSocket connected, subscribing to {len(market_ids)} markets")

            # Subscribe to markets
            for market_id in market_ids:
                subscribe_msg = {
                    "type": "subscribe",
                    "channel": "market",
                    "asset_ids": [market_id],
                }
                ws.send(json.dumps(subscribe_msg))

        while should_reconnect and reconnect_attempts < max_reconnect_attempts:
            try:
                logger.info(
                    f"Connecting to WebSocket (attempt {reconnect_attempts + 1})"
                )

                ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_open=_on_open,
                    on_message=_on_message,
                    on_error=_on_error,
                    on_close=_on_close,
                )

                self._ws = ws
                self._ws_running = True

                # Run WebSocket in a separate thread
                ws_thread = threading.Thread(target=ws.run_forever, daemon=True)
                ws_thread.start()

                # Yield messages from the queue
                while self._ws_running:
                    while message_queue:
                        yield message_queue.pop(0)
                    time.sleep(0.01)  # Small sleep to prevent busy waiting

                    # Check if thread is still alive
                    if not ws_thread.is_alive():
                        break

            except Exception as e:
                logger.error(f"WebSocket connection error: {e}")
                if on_error:
                    on_error(e)

            # Handle reconnection
            if auto_reconnect and should_reconnect:
                reconnect_attempts += 1
                if reconnect_attempts < max_reconnect_attempts:
                    delay = reconnect_delay * (2 ** min(reconnect_attempts - 1, 4))
                    logger.info(
                        f"Reconnecting in {delay:.1f} seconds "
                        f"(attempt {reconnect_attempts}/{max_reconnect_attempts})"
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Max reconnection attempts ({max_reconnect_attempts}) reached"
                    )
                    should_reconnect = False
            else:
                should_reconnect = False

    def stop_websocket(self) -> None:
        """Stop the WebSocket connection."""
        self._ws_running = False
        if self._ws:
            try:
                self._ws.close()
            except Exception as e:
                logger.warning(f"Error closing WebSocket: {e}")
            self._ws = None

    # Legacy method aliases for backward compatibility
    def get_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Fetch markets from Polymarket.

        Deprecated: Use fetch_markets() instead.
        """
        return self.fetch_markets(limit=limit, offset=offset, active_only=active_only)

    def get_market_details(self, market_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed information for a specific market.

        Args:
            market_id: Market identifier

        Returns:
            Market data dictionary or None if not found
        """
        logger.info(f"Fetching market details for: {market_id}")

        url = f"{self.base_url}/markets/{market_id}"
        response = self._request_with_retry("GET", url)

        if response is None:
            return None

        try:
            return response.json()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode market details response: {e}")
            return None

    def get_orderbook(self, market_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch orderbook data for a market.

        Deprecated: Use fetch_orderbook() for normalized data.

        Args:
            market_id: Market identifier

        Returns:
            NormalizedOrderBook as dictionary or None if not available
        """
        normalized = self.fetch_orderbook(market_id)
        if normalized is None:
            return None
        return normalized.to_dict()

    def get_price_history(
        self,
        market_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical price data for a market.

        Args:
            market_id: Market identifier
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of price data points
        """
        logger.info(f"Fetching price history for: {market_id}")

        params: Dict[str, Any] = {}
        if start_time:
            params["startTs"] = int(start_time.timestamp())
        if end_time:
            params["endTs"] = int(end_time.timestamp())

        url = f"{self.base_url}/markets/{market_id}/prices"
        response = self._request_with_retry("GET", url, params=params)

        if response is None:
            return []

        try:
            data = response.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "history" in data:
                return data.get("history", [])
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode price history response: {e}")
            return []

    def health_check(self) -> bool:
        """
        Check if API is accessible.

        Returns:
            True if API is healthy, False otherwise
        """
        try:
            logger.info("Checking API health")
            # Try to fetch one market to verify connectivity
            response = self._request_with_retry(
                "GET", f"{self.base_url}/markets", params={"limit": 1}
            )
            return response is not None
        except Exception as e:
            logger.error(f"API health check failed: {e}")
            return False


def normalize_orderbook_from_json(
    raw_data: Dict[str, Any], market_id: str = ""
) -> NormalizedOrderBook:
    """
    Utility function to normalize raw orderbook JSON data.

    This is a standalone function for parsing sample JSON without
    needing a full API client instance.

    Args:
        raw_data: Raw orderbook data (e.g., from a JSON file)
        market_id: Optional market identifier

    Returns:
        NormalizedOrderBook with best prices
    """
    normalized = NormalizedOrderBook(
        market_id=market_id,
        timestamp=datetime.now(),
    )

    # Extract bids (buy orders)
    bids = raw_data.get("bids", [])
    if bids:
        sorted_bids = sorted(
            bids, key=lambda x: float(x.get("price", 0)), reverse=True
        )
        if sorted_bids:
            normalized.yes_best_bid = float(sorted_bids[0].get("price", 0))

    # Extract asks (sell orders)
    asks = raw_data.get("asks", [])
    if asks:
        sorted_asks = sorted(asks, key=lambda x: float(x.get("price", 0)))
        if sorted_asks:
            normalized.yes_best_ask = float(sorted_asks[0].get("price", 0))

    # Derive NO prices from YES prices
    if normalized.yes_best_ask is not None:
        normalized.no_best_bid = round(1.0 - normalized.yes_best_ask, 4)

    if normalized.yes_best_bid is not None:
        normalized.no_best_ask = round(1.0 - normalized.yes_best_bid, 4)

    return normalized
