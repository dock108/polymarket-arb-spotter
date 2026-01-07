"""
Unit tests for the wallet feed module.

Tests wallet trade ingestion, normalization, storage, and duplication protection.
"""

import os
import shutil
import tempfile
import unittest
from datetime import datetime
from unittest.mock import Mock, patch

from app.core.wallet_feed import (
    WalletFeed,
    WalletTrade,
    get_wallet_trades,
    _get_db,
    _ensure_table,
)


class TestWalletFeed(unittest.TestCase):
    """Test wallet feed functionality."""

    def setUp(self):
        """Set up test database for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_wallet_trades.db")
        self.feed = WalletFeed(db_path=self.test_db_path)

    def tearDown(self):
        """Clean up test database after each test."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)


class TestWalletTradeDataclass(unittest.TestCase):
    """Test WalletTrade dataclass."""

    def test_wallet_trade_creation(self):
        """Test creating a WalletTrade object."""
        trade = WalletTrade(
            wallet="0x1234567890abcdef",
            market_id="market_123",
            side="yes",
            price=0.65,
            size=100.0,
            timestamp=datetime(2024, 1, 5, 12, 0, 0),
            tx_hash="0xabcdef1234567890",
        )

        self.assertEqual(trade.wallet, "0x1234567890abcdef")
        self.assertEqual(trade.market_id, "market_123")
        self.assertEqual(trade.side, "yes")
        self.assertEqual(trade.price, 0.65)
        self.assertEqual(trade.size, 100.0)
        self.assertEqual(trade.tx_hash, "0xabcdef1234567890")

    def test_wallet_trade_to_dict(self):
        """Test converting WalletTrade to dictionary."""
        trade = WalletTrade(
            wallet="0x1234567890abcdef",
            market_id="market_123",
            side="no",
            price=0.35,
            size=50.0,
            timestamp=datetime(2024, 1, 5, 12, 0, 0),
            tx_hash="0xabcdef1234567890",
        )

        trade_dict = trade.to_dict()

        self.assertEqual(trade_dict["wallet"], "0x1234567890abcdef")
        self.assertEqual(trade_dict["market_id"], "market_123")
        self.assertEqual(trade_dict["side"], "no")
        self.assertEqual(trade_dict["price"], 0.35)
        self.assertEqual(trade_dict["size"], 50.0)
        self.assertEqual(trade_dict["timestamp"], "2024-01-05T12:00:00")
        self.assertEqual(trade_dict["tx_hash"], "0xabcdef1234567890")


class TestDatabaseOperations(TestWalletFeed):
    """Test database operations."""

    def test_ensure_table_creates_table(self):
        """Test that _ensure_table creates the wallet_trades table."""
        db = _get_db(self.test_db_path)
        _ensure_table(db)

        self.assertIn("wallet_trades", db.table_names())

    def test_ensure_table_creates_indexes(self):
        """Test that _ensure_table creates proper indexes."""
        db = _get_db(self.test_db_path)
        _ensure_table(db)

        # Check that indexes exist
        table = db["wallet_trades"]
        index_names = [idx.name for idx in table.indexes]
        
        self.assertIn("idx_tx_hash", index_names)
        self.assertIn("idx_wallet_timestamp", index_names)
        self.assertIn("idx_market_timestamp", index_names)

    def test_store_trade_basic(self):
        """Test storing a single trade."""
        trade = WalletTrade(
            wallet="0x1234567890abcdef",
            market_id="market_123",
            side="yes",
            price=0.65,
            size=100.0,
            timestamp=datetime(2024, 1, 5, 12, 0, 0),
            tx_hash="0xabcdef1234567890",
        )

        result = self.feed.store_trade(trade)
        self.assertTrue(result)

        # Verify trade was stored
        trades = get_wallet_trades(db_path=self.test_db_path)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["wallet"], "0x1234567890abcdef")
        self.assertEqual(trades[0]["market_id"], "market_123")
        self.assertEqual(trades[0]["side"], "yes")

    def test_store_trade_duplicate_protection(self):
        """Test that duplicate trades are not stored."""
        trade = WalletTrade(
            wallet="0x1234567890abcdef",
            market_id="market_123",
            side="yes",
            price=0.65,
            size=100.0,
            timestamp=datetime(2024, 1, 5, 12, 0, 0),
            tx_hash="0xabcdef1234567890",
        )

        # Store first time - should succeed
        result1 = self.feed.store_trade(trade)
        self.assertTrue(result1)

        # Store again with same tx_hash - should be rejected
        result2 = self.feed.store_trade(trade)
        self.assertFalse(result2)

        # Verify only one trade was stored
        trades = get_wallet_trades(db_path=self.test_db_path)
        self.assertEqual(len(trades), 1)

    def test_store_trades_batch(self):
        """Test storing multiple trades in batch."""
        trades = [
            WalletTrade(
                wallet="0x1234567890abcdef",
                market_id="market_123",
                side="yes",
                price=0.65,
                size=100.0,
                timestamp=datetime(2024, 1, 5, 12, 0, 0),
                tx_hash="0xabcdef1234567890",
            ),
            WalletTrade(
                wallet="0x1234567890abcdef",
                market_id="market_456",
                side="no",
                price=0.35,
                size=50.0,
                timestamp=datetime(2024, 1, 5, 12, 1, 0),
                tx_hash="0xabcdef1234567891",
            ),
            WalletTrade(
                wallet="0xfedcba0987654321",
                market_id="market_123",
                side="yes",
                price=0.70,
                size=200.0,
                timestamp=datetime(2024, 1, 5, 12, 2, 0),
                tx_hash="0xabcdef1234567892",
            ),
        ]

        count = self.feed.store_trades(trades)
        self.assertEqual(count, 3)

        # Verify all trades were stored
        stored_trades = get_wallet_trades(db_path=self.test_db_path)
        self.assertEqual(len(stored_trades), 3)

    def test_store_trades_with_duplicates(self):
        """Test batch storage with some duplicates."""
        trades1 = [
            WalletTrade(
                wallet="0x1234567890abcdef",
                market_id="market_123",
                side="yes",
                price=0.65,
                size=100.0,
                timestamp=datetime(2024, 1, 5, 12, 0, 0),
                tx_hash="0xabcdef1234567890",
            ),
            WalletTrade(
                wallet="0x1234567890abcdef",
                market_id="market_456",
                side="no",
                price=0.35,
                size=50.0,
                timestamp=datetime(2024, 1, 5, 12, 1, 0),
                tx_hash="0xabcdef1234567891",
            ),
        ]

        # Store first batch
        count1 = self.feed.store_trades(trades1)
        self.assertEqual(count1, 2)

        # Store second batch with one duplicate and one new
        trades2 = [
            WalletTrade(
                wallet="0x1234567890abcdef",
                market_id="market_123",
                side="yes",
                price=0.65,
                size=100.0,
                timestamp=datetime(2024, 1, 5, 12, 0, 0),
                tx_hash="0xabcdef1234567890",  # Duplicate
            ),
            WalletTrade(
                wallet="0xfedcba0987654321",
                market_id="market_789",
                side="yes",
                price=0.70,
                size=200.0,
                timestamp=datetime(2024, 1, 5, 12, 2, 0),
                tx_hash="0xabcdef1234567892",  # New
            ),
        ]

        count2 = self.feed.store_trades(trades2)
        self.assertEqual(count2, 1)  # Only one new trade

        # Verify total count
        stored_trades = get_wallet_trades(db_path=self.test_db_path)
        self.assertEqual(len(stored_trades), 3)


class TestNormalization(TestWalletFeed):
    """Test trade normalization."""

    def test_normalize_trade_basic(self):
        """Test normalizing a basic trade."""
        raw_trade = {
            "maker_address": "0x1234567890abcdef",
            "asset_id": "market_123",
            "outcome": "1",  # Yes
            "price": "0.65",
            "size": "100.0",
            "timestamp": "2024-01-05T12:00:00",
            "transaction_hash": "0xabcdef1234567890",
        }

        trade = self.feed._normalize_trade(raw_trade)

        self.assertIsNotNone(trade)
        self.assertEqual(trade.wallet, "0x1234567890abcdef")
        self.assertEqual(trade.market_id, "market_123")
        self.assertEqual(trade.side, "yes")
        self.assertEqual(trade.price, 0.65)
        self.assertEqual(trade.size, 100.0)
        self.assertEqual(trade.tx_hash, "0xabcdef1234567890")

    def test_normalize_trade_with_taker(self):
        """Test normalizing a trade with taker_address."""
        raw_trade = {
            "taker_address": "0xfedcba0987654321",
            "market": "market_456",
            "outcome": 0,  # No
            "price": 0.35,
            "size": 50.0,
            "created_at": 1704456000,  # Unix timestamp
            "id": "trade_12345",
        }

        trade = self.feed._normalize_trade(raw_trade)

        self.assertIsNotNone(trade)
        self.assertEqual(trade.wallet, "0xfedcba0987654321")
        self.assertEqual(trade.market_id, "market_456")
        self.assertEqual(trade.side, "no")
        self.assertEqual(trade.tx_hash, "trade_12345")

    def test_normalize_trade_missing_fields(self):
        """Test that normalization fails gracefully with missing fields."""
        raw_trade = {
            "price": "0.65",
            "size": "100.0",
        }

        trade = self.feed._normalize_trade(raw_trade)
        self.assertIsNone(trade)


class TestRetryLogic(TestWalletFeed):
    """Test retry logic for API requests."""

    @patch("requests.Session.request")
    def test_request_with_retry_success(self, mock_request):
        """Test successful request on first try."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_request.return_value = mock_response

        response = self.feed._request_with_retry("GET", "http://example.com")

        self.assertIsNotNone(response)
        self.assertEqual(mock_request.call_count, 1)

    @patch("requests.Session.request")
    @patch("time.sleep")  # Mock sleep to speed up test
    def test_request_with_retry_eventual_success(self, mock_sleep, mock_request):
        """Test successful request after retries."""
        import requests
        
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"data": []}
        
        # Fail twice with RequestException, then succeed
        mock_request.side_effect = [
            requests.exceptions.RequestException("Connection error"),
            requests.exceptions.RequestException("Connection error"),
            mock_response_success,
        ]

        response = self.feed._request_with_retry("GET", "http://example.com")

        self.assertIsNotNone(response)
        self.assertEqual(mock_request.call_count, 3)

    @patch("requests.Session.request")
    @patch("time.sleep")  # Mock sleep to speed up test
    def test_request_with_retry_all_fail(self, mock_sleep, mock_request):
        """Test that request fails after max retries."""
        # Make the request itself raise a RequestException
        import requests
        mock_request.side_effect = requests.exceptions.RequestException("Connection error")

        response = self.feed._request_with_retry("GET", "http://example.com")

        self.assertIsNone(response)
        self.assertEqual(mock_request.call_count, self.feed.max_retries)


class TestFetchTrades(TestWalletFeed):
    """Test fetching trades from API."""

    @patch("requests.Session.request")
    def test_fetch_trades_success(self, mock_request):
        """Test successful trade fetching."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "maker_address": "0x1234567890abcdef",
                "asset_id": "market_123",
                "outcome": "1",
                "price": "0.65",
                "size": "100.0",
                "timestamp": "2024-01-05T12:00:00",
                "transaction_hash": "0xabcdef1234567890",
            },
            {
                "maker_address": "0xfedcba0987654321",
                "asset_id": "market_456",
                "outcome": "0",
                "price": "0.35",
                "size": "50.0",
                "timestamp": "2024-01-05T12:01:00",
                "transaction_hash": "0xabcdef1234567891",
            },
        ]
        mock_request.return_value = mock_response

        trades = self.feed.fetch_trades()

        self.assertEqual(len(trades), 2)
        self.assertEqual(trades[0].wallet, "0x1234567890abcdef")
        self.assertEqual(trades[1].side, "no")

    @patch("requests.Session.request")
    def test_fetch_trades_with_filters(self, mock_request):
        """Test fetching trades with market_id filter."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_request.return_value = mock_response

        self.feed.fetch_trades(market_id="market_123", wallet="0x1234")

        # Verify request was made with correct parameters
        call_args = mock_request.call_args
        params = call_args[1]["params"]
        self.assertEqual(params["asset_id"], "market_123")
        self.assertEqual(params["maker"], "0x1234")


class TestGetWalletTrades(TestWalletFeed):
    """Test retrieving trades from database."""

    def test_get_wallet_trades_all(self):
        """Test retrieving all trades."""
        trades = [
            WalletTrade(
                wallet="0x1234567890abcdef",
                market_id="market_123",
                side="yes",
                price=0.65,
                size=100.0,
                timestamp=datetime(2024, 1, 5, 12, 0, 0),
                tx_hash="0xabcdef1234567890",
            ),
            WalletTrade(
                wallet="0xfedcba0987654321",
                market_id="market_456",
                side="no",
                price=0.35,
                size=50.0,
                timestamp=datetime(2024, 1, 5, 12, 1, 0),
                tx_hash="0xabcdef1234567891",
            ),
        ]

        self.feed.store_trades(trades)

        retrieved = get_wallet_trades(db_path=self.test_db_path)
        self.assertEqual(len(retrieved), 2)

    def test_get_wallet_trades_filter_by_wallet(self):
        """Test retrieving trades filtered by wallet."""
        trades = [
            WalletTrade(
                wallet="0x1234567890abcdef",
                market_id="market_123",
                side="yes",
                price=0.65,
                size=100.0,
                timestamp=datetime(2024, 1, 5, 12, 0, 0),
                tx_hash="0xabcdef1234567890",
            ),
            WalletTrade(
                wallet="0xfedcba0987654321",
                market_id="market_456",
                side="no",
                price=0.35,
                size=50.0,
                timestamp=datetime(2024, 1, 5, 12, 1, 0),
                tx_hash="0xabcdef1234567891",
            ),
        ]

        self.feed.store_trades(trades)

        retrieved = get_wallet_trades(
            wallet="0x1234567890abcdef",
            db_path=self.test_db_path,
        )
        self.assertEqual(len(retrieved), 1)
        self.assertEqual(retrieved[0]["wallet"], "0x1234567890abcdef")

    def test_get_wallet_trades_filter_by_market(self):
        """Test retrieving trades filtered by market_id."""
        trades = [
            WalletTrade(
                wallet="0x1234567890abcdef",
                market_id="market_123",
                side="yes",
                price=0.65,
                size=100.0,
                timestamp=datetime(2024, 1, 5, 12, 0, 0),
                tx_hash="0xabcdef1234567890",
            ),
            WalletTrade(
                wallet="0x1234567890abcdef",
                market_id="market_456",
                side="no",
                price=0.35,
                size=50.0,
                timestamp=datetime(2024, 1, 5, 12, 1, 0),
                tx_hash="0xabcdef1234567891",
            ),
        ]

        self.feed.store_trades(trades)

        retrieved = get_wallet_trades(
            market_id="market_123",
            db_path=self.test_db_path,
        )
        self.assertEqual(len(retrieved), 1)
        self.assertEqual(retrieved[0]["market_id"], "market_123")


if __name__ == "__main__":
    unittest.main()
