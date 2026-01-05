"""
Unit tests for API client module.

Tests JSON parsing and normalization logic using sample data.
"""

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.core.api_client import (
    NormalizedOrderBook,
    PolymarketAPIClient,
    normalize_orderbook_from_json,
)


class TestNormalizedOrderBook(unittest.TestCase):
    """Test NormalizedOrderBook dataclass."""

    def test_default_values(self):
        """Test that default values are None."""
        orderbook = NormalizedOrderBook()
        self.assertIsNone(orderbook.yes_best_bid)
        self.assertIsNone(orderbook.yes_best_ask)
        self.assertIsNone(orderbook.no_best_bid)
        self.assertIsNone(orderbook.no_best_ask)
        self.assertEqual(orderbook.market_id, "")
        self.assertIsNone(orderbook.timestamp)

    def test_to_dict(self):
        """Test conversion to dictionary."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        orderbook = NormalizedOrderBook(
            yes_best_bid=0.45,
            yes_best_ask=0.55,
            no_best_bid=0.45,
            no_best_ask=0.55,
            market_id="test_market",
            timestamp=timestamp,
        )

        result = orderbook.to_dict()

        self.assertEqual(result["yes_best_bid"], 0.45)
        self.assertEqual(result["yes_best_ask"], 0.55)
        self.assertEqual(result["no_best_bid"], 0.45)
        self.assertEqual(result["no_best_ask"], 0.55)
        self.assertEqual(result["market_id"], "test_market")
        self.assertEqual(result["timestamp"], "2024-01-01T12:00:00")

    def test_to_dict_with_none_timestamp(self):
        """Test conversion to dictionary with None timestamp."""
        orderbook = NormalizedOrderBook(yes_best_bid=0.5)
        result = orderbook.to_dict()
        self.assertIsNone(result["timestamp"])


class TestNormalizeOrderbookFromJson(unittest.TestCase):
    """Test the normalize_orderbook_from_json utility function."""

    def test_parse_sample_orderbook_json(self):
        """Test parsing a sample orderbook JSON structure."""
        sample_json = {
            "bids": [
                {"price": "0.45", "size": "100"},
                {"price": "0.44", "size": "200"},
                {"price": "0.43", "size": "300"},
            ],
            "asks": [
                {"price": "0.55", "size": "100"},
                {"price": "0.56", "size": "200"},
                {"price": "0.57", "size": "300"},
            ],
        }

        result = normalize_orderbook_from_json(sample_json, "test_market")

        # Best bid should be highest bid price
        self.assertEqual(result.yes_best_bid, 0.45)
        # Best ask should be lowest ask price
        self.assertEqual(result.yes_best_ask, 0.55)
        # NO prices are derived from YES prices
        self.assertEqual(result.no_best_bid, 0.45)  # 1 - 0.55 = 0.45
        self.assertEqual(result.no_best_ask, 0.55)  # 1 - 0.45 = 0.55
        self.assertEqual(result.market_id, "test_market")

    def test_parse_empty_orderbook(self):
        """Test parsing an empty orderbook."""
        sample_json = {"bids": [], "asks": []}

        result = normalize_orderbook_from_json(sample_json)

        self.assertIsNone(result.yes_best_bid)
        self.assertIsNone(result.yes_best_ask)
        self.assertIsNone(result.no_best_bid)
        self.assertIsNone(result.no_best_ask)

    def test_parse_orderbook_with_only_bids(self):
        """Test parsing orderbook with only bids."""
        sample_json = {
            "bids": [
                {"price": "0.40", "size": "100"},
                {"price": "0.35", "size": "200"},
            ],
            "asks": [],
        }

        result = normalize_orderbook_from_json(sample_json)

        self.assertEqual(result.yes_best_bid, 0.40)
        self.assertIsNone(result.yes_best_ask)
        # no_best_bid requires yes_best_ask
        self.assertIsNone(result.no_best_bid)
        # no_best_ask can be derived from yes_best_bid
        self.assertEqual(result.no_best_ask, 0.60)

    def test_parse_orderbook_with_only_asks(self):
        """Test parsing orderbook with only asks."""
        sample_json = {
            "bids": [],
            "asks": [
                {"price": "0.60", "size": "100"},
                {"price": "0.65", "size": "200"},
            ],
        }

        result = normalize_orderbook_from_json(sample_json)

        self.assertIsNone(result.yes_best_bid)
        self.assertEqual(result.yes_best_ask, 0.60)
        # no_best_bid can be derived from yes_best_ask
        self.assertEqual(result.no_best_bid, 0.40)
        # no_best_ask requires yes_best_bid
        self.assertIsNone(result.no_best_ask)

    def test_parse_single_bid_and_ask(self):
        """Test parsing orderbook with single bid and ask."""
        sample_json = {
            "bids": [{"price": "0.50", "size": "100"}],
            "asks": [{"price": "0.52", "size": "100"}],
        }

        result = normalize_orderbook_from_json(sample_json)

        self.assertEqual(result.yes_best_bid, 0.50)
        self.assertEqual(result.yes_best_ask, 0.52)
        self.assertEqual(result.no_best_bid, 0.48)  # 1 - 0.52
        self.assertEqual(result.no_best_ask, 0.50)  # 1 - 0.50

    def test_parse_unsorted_orders(self):
        """Test that orders are correctly sorted to find best prices."""
        sample_json = {
            "bids": [
                {"price": "0.30", "size": "100"},
                {"price": "0.50", "size": "200"},  # Best bid
                {"price": "0.40", "size": "300"},
            ],
            "asks": [
                {"price": "0.70", "size": "100"},
                {"price": "0.55", "size": "200"},  # Best ask
                {"price": "0.60", "size": "300"},
            ],
        }

        result = normalize_orderbook_from_json(sample_json)

        self.assertEqual(result.yes_best_bid, 0.50)
        self.assertEqual(result.yes_best_ask, 0.55)

    def test_parse_numeric_prices(self):
        """Test parsing orderbook with numeric prices (not strings)."""
        sample_json = {
            "bids": [
                {"price": 0.45, "size": 100},
                {"price": 0.44, "size": 200},
            ],
            "asks": [
                {"price": 0.55, "size": 100},
                {"price": 0.56, "size": 200},
            ],
        }

        result = normalize_orderbook_from_json(sample_json)

        self.assertEqual(result.yes_best_bid, 0.45)
        self.assertEqual(result.yes_best_ask, 0.55)


class TestPolymarketAPIClientInit(unittest.TestCase):
    """Test PolymarketAPIClient initialization."""

    def test_default_initialization(self):
        """Test client initializes with default values."""
        client = PolymarketAPIClient()

        self.assertEqual(client.base_url, PolymarketAPIClient.DEFAULT_GAMMA_URL)
        self.assertEqual(client.clob_url, PolymarketAPIClient.DEFAULT_CLOB_URL)
        self.assertEqual(client.ws_url, PolymarketAPIClient.DEFAULT_WS_URL)
        self.assertIsNone(client.api_key)
        self.assertEqual(client.max_retries, 3)
        self.assertEqual(client.retry_delay, 1.0)
        self.assertEqual(client.timeout, 30)

    def test_custom_initialization(self):
        """Test client initializes with custom values."""
        client = PolymarketAPIClient(
            base_url="https://custom.api.com/",
            clob_url="https://custom.clob.com/",
            ws_url="wss://custom.ws.com/",
            api_key="test_key",
            max_retries=5,
            retry_delay=2.0,
            timeout=60,
        )

        # URL trailing slashes should be stripped
        self.assertEqual(client.base_url, "https://custom.api.com")
        self.assertEqual(client.clob_url, "https://custom.clob.com")
        self.assertEqual(client.ws_url, "wss://custom.ws.com/")
        self.assertEqual(client.api_key, "test_key")
        self.assertEqual(client.max_retries, 5)
        self.assertEqual(client.retry_delay, 2.0)
        self.assertEqual(client.timeout, 60)

    def test_api_key_sets_authorization_header(self):
        """Test that API key sets authorization header."""
        client = PolymarketAPIClient(api_key="my_api_key")

        self.assertIn("Authorization", client.session.headers)
        self.assertEqual(client.session.headers["Authorization"], "Bearer my_api_key")


class TestPolymarketAPIClientNormalization(unittest.TestCase):
    """Test the _normalize_orderbook method."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = PolymarketAPIClient()

    def test_normalize_orderbook_full(self):
        """Test normalizing a full orderbook."""
        raw_orderbook = {
            "bids": [
                {"price": "0.48", "size": "500"},
                {"price": "0.47", "size": "1000"},
            ],
            "asks": [
                {"price": "0.52", "size": "500"},
                {"price": "0.53", "size": "1000"},
            ],
        }

        result = self.client._normalize_orderbook(raw_orderbook, "market123")

        self.assertEqual(result.yes_best_bid, 0.48)
        self.assertEqual(result.yes_best_ask, 0.52)
        self.assertEqual(result.no_best_bid, 0.48)  # 1 - 0.52
        self.assertEqual(result.no_best_ask, 0.52)  # 1 - 0.48
        self.assertEqual(result.market_id, "market123")
        self.assertIsNotNone(result.timestamp)

    def test_normalize_orderbook_preserves_precision(self):
        """Test that normalization preserves reasonable precision."""
        raw_orderbook = {
            "bids": [{"price": "0.4567", "size": "100"}],
            "asks": [{"price": "0.5433", "size": "100"}],
        }

        result = self.client._normalize_orderbook(raw_orderbook, "test")

        self.assertEqual(result.yes_best_bid, 0.4567)
        self.assertEqual(result.yes_best_ask, 0.5433)
        # NO prices are rounded to 4 decimal places
        self.assertEqual(result.no_best_bid, 0.4567)  # 1 - 0.5433 = 0.4567
        self.assertEqual(result.no_best_ask, 0.5433)  # 1 - 0.4567 = 0.5433


class TestPolymarketAPIClientMocked(unittest.TestCase):
    """Test API client methods with mocked HTTP responses."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = PolymarketAPIClient(max_retries=1, retry_delay=0.01)

    @patch.object(PolymarketAPIClient, "_request_with_retry")
    def test_fetch_markets_success(self, mock_request):
        """Test successful market fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "market1", "name": "Test Market 1"},
            {"id": "market2", "name": "Test Market 2"},
        ]
        mock_request.return_value = mock_response

        result = self.client.fetch_markets(limit=10)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "market1")

    @patch.object(PolymarketAPIClient, "_request_with_retry")
    def test_fetch_markets_empty_response(self, mock_request):
        """Test market fetch with empty response."""
        mock_request.return_value = None

        result = self.client.fetch_markets()

        self.assertEqual(result, [])

    @patch.object(PolymarketAPIClient, "_request_with_retry")
    def test_fetch_markets_paginated_response(self, mock_request):
        """Test market fetch with paginated response format."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"id": "market1"}, {"id": "market2"}],
            "next": "page2",
        }
        mock_request.return_value = mock_response

        result = self.client.fetch_markets()

        self.assertEqual(len(result), 2)

    @patch.object(PolymarketAPIClient, "_request_with_retry")
    def test_fetch_orderbook_success(self, mock_request):
        """Test successful orderbook fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "bids": [{"price": "0.45", "size": "100"}],
            "asks": [{"price": "0.55", "size": "100"}],
        }
        mock_request.return_value = mock_response

        result = self.client.fetch_orderbook("token123")

        self.assertIsNotNone(result)
        self.assertEqual(result.yes_best_bid, 0.45)
        self.assertEqual(result.yes_best_ask, 0.55)
        self.assertEqual(result.market_id, "token123")

    @patch.object(PolymarketAPIClient, "_request_with_retry")
    def test_fetch_orderbook_failure(self, mock_request):
        """Test orderbook fetch failure."""
        mock_request.return_value = None

        result = self.client.fetch_orderbook("token123")

        self.assertIsNone(result)

    @patch.object(PolymarketAPIClient, "_request_with_retry")
    def test_get_orderbook_returns_dict(self, mock_request):
        """Test that get_orderbook (legacy) returns dictionary."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "bids": [{"price": "0.45", "size": "100"}],
            "asks": [{"price": "0.55", "size": "100"}],
        }
        mock_request.return_value = mock_response

        result = self.client.get_orderbook("token123")

        self.assertIsInstance(result, dict)
        self.assertEqual(result["yes_best_bid"], 0.45)

    @patch.object(PolymarketAPIClient, "_request_with_retry")
    def test_health_check_success(self, mock_request):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": "market1"}]
        mock_request.return_value = mock_response

        result = self.client.health_check()

        self.assertTrue(result)

    @patch.object(PolymarketAPIClient, "_request_with_retry")
    def test_health_check_failure(self, mock_request):
        """Test failed health check."""
        mock_request.return_value = None

        result = self.client.health_check()

        self.assertFalse(result)


class TestPolymarketAPIClientNoOrderPlacement(unittest.TestCase):
    """Verify that the client does NOT support order placement."""

    def test_no_place_order_method(self):
        """Test that there is no place_order method."""
        client = PolymarketAPIClient()

        self.assertFalse(hasattr(client, "place_order"))
        self.assertFalse(hasattr(client, "submit_order"))
        self.assertFalse(hasattr(client, "create_order"))
        self.assertFalse(hasattr(client, "buy"))
        self.assertFalse(hasattr(client, "sell"))

    def test_client_is_read_only(self):
        """Verify the client docstring indicates read-only functionality."""
        client = PolymarketAPIClient()

        self.assertIn("read-only", client.__class__.__doc__.lower())
        self.assertIn("NOT", client.__class__.__doc__)


class TestRetryLogic(unittest.TestCase):
    """Test the retry logic in _request_with_retry."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = PolymarketAPIClient(max_retries=3, retry_delay=0.01)

    @patch("requests.Session.request")
    def test_retry_on_timeout(self, mock_request):
        """Test that requests are retried on timeout."""
        import requests

        mock_request.side_effect = requests.exceptions.Timeout()

        result = self.client._request_with_retry("GET", "http://test.com")

        self.assertIsNone(result)
        self.assertEqual(mock_request.call_count, 3)

    @patch("requests.Session.request")
    def test_retry_on_connection_error(self, mock_request):
        """Test that requests are retried on connection error."""
        import requests

        mock_request.side_effect = requests.exceptions.ConnectionError()

        result = self.client._request_with_retry("GET", "http://test.com")

        self.assertIsNone(result)
        self.assertEqual(mock_request.call_count, 3)

    @patch("requests.Session.request")
    def test_no_retry_on_4xx_error(self, mock_request):
        """Test that 4xx errors are not retried."""
        import requests

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_request.return_value = mock_response

        result = self.client._request_with_retry("GET", "http://test.com")

        self.assertIsNone(result)
        self.assertEqual(mock_request.call_count, 1)

    @patch("requests.Session.request")
    def test_retry_on_5xx_error(self, mock_request):
        """Test that 5xx errors are retried."""
        import requests

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_request.return_value = mock_response

        result = self.client._request_with_retry("GET", "http://test.com")

        self.assertIsNone(result)
        self.assertEqual(mock_request.call_count, 3)

    @patch("requests.Session.request")
    def test_successful_request_no_retry(self, mock_request):
        """Test that successful requests don't trigger retries."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        result = self.client._request_with_retry("GET", "http://test.com")

        self.assertIsNotNone(result)
        self.assertEqual(mock_request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
