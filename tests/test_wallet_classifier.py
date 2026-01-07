"""
Unit tests for the wallet classifier module.

Tests wallet classification logic including fresh wallets, whales,
high-confidence wallets, and suspicious cluster detection.
"""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta

from app.core.wallet_feed import WalletFeed, WalletTrade
from app.core.wallet_classifier import (
    WalletTag,
    classify_fresh_wallet,
    classify_whale,
    classify_high_confidence,
    detect_suspicious_cluster,
    classify_wallet,
    store_wallet_tag,
    store_wallet_tags,
    get_wallet_tags,
    _ensure_wallet_tags_table,
    _get_db,
)


class TestWalletClassifier(unittest.TestCase):
    """Base test class for wallet classifier."""

    def setUp(self):
        """Set up test database for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_wallet_trades.db")
        self.feed = WalletFeed(db_path=self.test_db_path)

    def tearDown(self):
        """Clean up test database after each test."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _store_sample_trades(self):
        """Store sample trades for testing."""
        trades = [
            # Wallet with history before today - not fresh
            WalletTrade(
                wallet="0x1111111111111111",
                market_id="market_1",
                side="yes",
                price=0.65,
                size=100.0,
                timestamp=datetime.now() - timedelta(days=2),
                tx_hash="0xhash1",
            ),
            WalletTrade(
                wallet="0x1111111111111111",
                market_id="market_1",
                side="yes",
                price=0.70,
                size=50.0,
                timestamp=datetime.now() - timedelta(hours=1),
                tx_hash="0xhash2",
            ),
            # Fresh wallet - only trades today
            WalletTrade(
                wallet="0x2222222222222222",
                market_id="market_1",
                side="no",
                price=0.40,
                size=200.0,
                timestamp=datetime.now() - timedelta(hours=2),
                tx_hash="0xhash3",
            ),
            # Whale wallet - large trade
            WalletTrade(
                wallet="0x3333333333333333",
                market_id="market_2",
                side="yes",
                price=0.55,
                size=15000.0,
                timestamp=datetime.now() - timedelta(hours=3),
                tx_hash="0xhash4",
            ),
        ]
        self.feed.store_trades(trades)


class TestWalletTagDataclass(unittest.TestCase):
    """Test WalletTag dataclass."""

    def test_wallet_tag_creation(self):
        """Test creating a WalletTag object."""
        tag = WalletTag(
            wallet="0x1234567890abcdef",
            tag="fresh",
            confidence=1.0,
            metadata={"reference_date": "2024-01-05T00:00:00"},
        )

        self.assertEqual(tag.wallet, "0x1234567890abcdef")
        self.assertEqual(tag.tag, "fresh")
        self.assertEqual(tag.confidence, 1.0)
        self.assertIn("reference_date", tag.metadata)

    def test_wallet_tag_to_dict(self):
        """Test converting WalletTag to dictionary."""
        timestamp = datetime(2024, 1, 5, 12, 0, 0)
        tag = WalletTag(
            wallet="0x1234567890abcdef",
            tag="whale",
            confidence=1.0,
            metadata={"threshold": 10000.0},
            timestamp=timestamp,
        )

        tag_dict = tag.to_dict()

        self.assertEqual(tag_dict["wallet"], "0x1234567890abcdef")
        self.assertEqual(tag_dict["tag"], "whale")
        self.assertEqual(tag_dict["confidence"], 1.0)
        self.assertIn("threshold", tag_dict["metadata"])
        self.assertEqual(tag_dict["timestamp"], "2024-01-05T12:00:00")


class TestFreshWalletClassification(TestWalletClassifier):
    """Test fresh wallet classification."""

    def test_classify_fresh_wallet_with_only_recent_trades(self):
        """Test classifying a wallet with only recent trades as fresh."""
        # Store a wallet with only recent trades
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        trades = [
            WalletTrade(
                wallet="0xfresh123",
                market_id="market_1",
                side="yes",
                price=0.65,
                size=100.0,
                timestamp=today_start + timedelta(hours=2),
                tx_hash="0xhash_fresh1",
            ),
        ]
        self.feed.store_trades(trades)

        # Classify
        tag = classify_fresh_wallet("0xfresh123", db_path=self.test_db_path)

        # Verify
        self.assertIsNotNone(tag)
        self.assertEqual(tag.wallet, "0xfresh123")
        self.assertEqual(tag.tag, "fresh")
        self.assertEqual(tag.confidence, 1.0)

    def test_classify_fresh_wallet_with_historical_trades(self):
        """Test that wallet with historical trades is not classified as fresh."""
        # Store wallet with historical trades
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        trades = [
            WalletTrade(
                wallet="0xold123",
                market_id="market_1",
                side="yes",
                price=0.65,
                size=100.0,
                timestamp=today_start - timedelta(days=1),
                tx_hash="0xhash_old1",
            ),
            WalletTrade(
                wallet="0xold123",
                market_id="market_1",
                side="no",
                price=0.40,
                size=50.0,
                timestamp=today_start + timedelta(hours=1),
                tx_hash="0xhash_old2",
            ),
        ]
        self.feed.store_trades(trades)

        # Classify
        tag = classify_fresh_wallet("0xold123", db_path=self.test_db_path)

        # Verify
        self.assertIsNone(tag)

    def test_classify_fresh_wallet_no_trades(self):
        """Test classifying a wallet with no trades."""
        tag = classify_fresh_wallet("0xnonexistent", db_path=self.test_db_path)
        self.assertIsNone(tag)

    def test_classify_fresh_wallet_custom_reference_date(self):
        """Test fresh wallet classification with custom reference date."""
        # Store trades around a specific date
        ref_date = datetime(2024, 1, 1, 0, 0, 0)
        trades = [
            WalletTrade(
                wallet="0xcustom123",
                market_id="market_1",
                side="yes",
                price=0.65,
                size=100.0,
                timestamp=ref_date + timedelta(hours=2),
                tx_hash="0xhash_custom1",
            ),
        ]
        self.feed.store_trades(trades)

        # Classify with custom reference date
        tag = classify_fresh_wallet(
            "0xcustom123", reference_date=ref_date, db_path=self.test_db_path
        )

        self.assertIsNotNone(tag)
        self.assertEqual(tag.tag, "fresh")


class TestWhaleClassification(TestWalletClassifier):
    """Test whale classification."""

    def test_classify_whale_with_large_trade(self):
        """Test classifying a wallet with large trades as whale."""
        # Store large trade
        trades = [
            WalletTrade(
                wallet="0xwhale123",
                market_id="market_1",
                side="yes",
                price=0.65,
                size=15000.0,
                timestamp=datetime.now(),
                tx_hash="0xhash_whale1",
            ),
        ]
        self.feed.store_trades(trades)

        # Classify with default threshold (10000.0)
        tag = classify_whale("0xwhale123", db_path=self.test_db_path)

        # Verify
        self.assertIsNotNone(tag)
        self.assertEqual(tag.wallet, "0xwhale123")
        self.assertEqual(tag.tag, "whale")
        self.assertEqual(tag.confidence, 1.0)
        self.assertEqual(tag.metadata["max_trade_size"], 15000.0)

    def test_classify_whale_with_multiple_large_trades(self):
        """Test whale classification with multiple large trades."""
        trades = [
            WalletTrade(
                wallet="0xbigwhale",
                market_id="market_1",
                side="yes",
                price=0.65,
                size=12000.0,
                timestamp=datetime.now() - timedelta(hours=2),
                tx_hash="0xhash_bigwhale1",
            ),
            WalletTrade(
                wallet="0xbigwhale",
                market_id="market_2",
                side="no",
                price=0.40,
                size=20000.0,
                timestamp=datetime.now() - timedelta(hours=1),
                tx_hash="0xhash_bigwhale2",
            ),
        ]
        self.feed.store_trades(trades)

        tag = classify_whale("0xbigwhale", db_path=self.test_db_path)

        self.assertIsNotNone(tag)
        self.assertEqual(tag.metadata["large_trades_count"], 2)
        self.assertEqual(tag.metadata["max_trade_size"], 20000.0)

    def test_classify_whale_below_threshold(self):
        """Test that small trades don't trigger whale classification."""
        trades = [
            WalletTrade(
                wallet="0xsmall123",
                market_id="market_1",
                side="yes",
                price=0.65,
                size=500.0,
                timestamp=datetime.now(),
                tx_hash="0xhash_small1",
            ),
        ]
        self.feed.store_trades(trades)

        tag = classify_whale("0xsmall123", db_path=self.test_db_path)
        self.assertIsNone(tag)

    def test_classify_whale_custom_threshold(self):
        """Test whale classification with custom threshold."""
        trades = [
            WalletTrade(
                wallet="0xcustomwhale",
                market_id="market_1",
                side="yes",
                price=0.65,
                size=5000.0,
                timestamp=datetime.now(),
                tx_hash="0xhash_customwhale1",
            ),
        ]
        self.feed.store_trades(trades)

        # Should be whale with 3000 threshold
        tag = classify_whale(
            "0xcustomwhale", trade_size_threshold=3000.0, db_path=self.test_db_path
        )
        self.assertIsNotNone(tag)

        # Should not be whale with 6000 threshold
        tag = classify_whale(
            "0xcustomwhale", trade_size_threshold=6000.0, db_path=self.test_db_path
        )
        self.assertIsNone(tag)


class TestHighConfidenceClassification(TestWalletClassifier):
    """Test high-confidence wallet classification."""

    def test_classify_high_confidence_without_outcomes(self):
        """Test that high-confidence classification returns None without market outcomes."""
        # Store multiple trades
        trades = [
            WalletTrade(
                wallet="0xtrader123",
                market_id="market_1",
                side="yes",
                price=0.65,
                size=100.0,
                timestamp=datetime.now() - timedelta(days=i),
                tx_hash=f"0xhash_trader{i}",
            )
            for i in range(6)
        ]
        self.feed.store_trades(trades)

        # Without market outcomes, should return None
        tag = classify_high_confidence("0xtrader123", db_path=self.test_db_path)
        self.assertIsNone(tag)

    def test_classify_high_confidence_insufficient_trades(self):
        """Test that insufficient trades don't trigger high-confidence."""
        # Store only a few trades
        trades = [
            WalletTrade(
                wallet="0xfewtrader",
                market_id="market_1",
                side="yes",
                price=0.65,
                size=100.0,
                timestamp=datetime.now() - timedelta(days=i),
                tx_hash=f"0xhash_few{i}",
            )
            for i in range(2)
        ]
        self.feed.store_trades(trades)

        # Should return None with min_trades=5 (default)
        tag = classify_high_confidence("0xfewtrader", db_path=self.test_db_path)
        self.assertIsNone(tag)

    def test_classify_high_confidence_nonexistent_wallet(self):
        """Test high-confidence classification for nonexistent wallet."""
        tag = classify_high_confidence("0xnonexistent", db_path=self.test_db_path)
        self.assertIsNone(tag)


class TestSuspiciousClusterDetection(TestWalletClassifier):
    """Test suspicious cluster detection."""

    def test_detect_suspicious_cluster_multiple_fresh_wallets(self):
        """Test detecting suspicious cluster with multiple fresh wallets."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Create multiple fresh wallets trading in same market
        trades = []
        for i in range(5):
            trades.append(
                WalletTrade(
                    wallet=f"0xfresh{i}",
                    market_id="market_suspicious",
                    side="yes",
                    price=0.65,
                    size=100.0,
                    timestamp=today_start + timedelta(hours=i),
                    tx_hash=f"0xhash_cluster{i}",
                )
            )
        self.feed.store_trades(trades)

        # Detect cluster
        tags = detect_suspicious_cluster(
            "market_suspicious",
            min_fresh_wallets=3,
            db_path=self.test_db_path,
        )

        # Verify
        self.assertEqual(len(tags), 5)
        for tag in tags:
            self.assertEqual(tag.tag, "suspicious_cluster")
            self.assertEqual(tag.metadata["market_id"], "market_suspicious")
            self.assertEqual(tag.metadata["cluster_size"], 5)

    def test_detect_suspicious_cluster_below_threshold(self):
        """Test that cluster below threshold is not detected."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Create only 2 fresh wallets
        trades = []
        for i in range(2):
            trades.append(
                WalletTrade(
                    wallet=f"0xsmallcluster{i}",
                    market_id="market_small",
                    side="yes",
                    price=0.65,
                    size=100.0,
                    timestamp=today_start + timedelta(hours=i),
                    tx_hash=f"0xhash_small{i}",
                )
            )
        self.feed.store_trades(trades)

        # Should not detect with min_fresh_wallets=3
        tags = detect_suspicious_cluster(
            "market_small",
            min_fresh_wallets=3,
            db_path=self.test_db_path,
        )
        self.assertEqual(len(tags), 0)

    def test_detect_suspicious_cluster_mixed_wallets(self):
        """Test cluster detection with mix of fresh and old wallets."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        trades = []
        # Add fresh wallets
        for i in range(3):
            trades.append(
                WalletTrade(
                    wallet=f"0xfreshmix{i}",
                    market_id="market_mixed",
                    side="yes",
                    price=0.65,
                    size=100.0,
                    timestamp=today_start + timedelta(hours=i),
                    tx_hash=f"0xhash_freshmix{i}",
                )
            )

        # Add old wallet with history
        trades.append(
            WalletTrade(
                wallet="0xoldmix",
                market_id="market_mixed",
                side="yes",
                price=0.60,
                size=100.0,
                timestamp=today_start - timedelta(days=2),
                tx_hash="0xhash_oldmix1",
            )
        )
        trades.append(
            WalletTrade(
                wallet="0xoldmix",
                market_id="market_mixed",
                side="no",
                price=0.40,
                size=50.0,
                timestamp=today_start + timedelta(hours=1),
                tx_hash="0xhash_oldmix2",
            )
        )

        self.feed.store_trades(trades)

        # Detect cluster - should only include fresh wallets
        tags = detect_suspicious_cluster(
            "market_mixed",
            min_fresh_wallets=3,
            db_path=self.test_db_path,
        )

        self.assertEqual(len(tags), 3)
        wallet_addresses = [tag.wallet for tag in tags]
        self.assertNotIn("0xoldmix", wallet_addresses)

    def test_detect_suspicious_cluster_outside_time_window(self):
        """Test that trades outside time window are not included."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        trades = []
        # Recent fresh wallets (within 30 minutes)
        for i in range(2):
            trades.append(
                WalletTrade(
                    wallet=f"0xrecentfresh{i}",
                    market_id="market_timewindow",
                    side="yes",
                    price=0.65,
                    size=100.0,
                    timestamp=datetime.now() - timedelta(minutes=20),
                    tx_hash=f"0xhash_recent{i}",
                )
            )

        # Old fresh wallet (outside 1h window - 3 hours ago)
        trades.append(
            WalletTrade(
                wallet="0xoldfresh",
                market_id="market_timewindow",
                side="yes",
                price=0.65,
                size=100.0,
                timestamp=datetime.now() - timedelta(hours=3),
                tx_hash="0xhash_oldfresh",
            )
        )

        self.feed.store_trades(trades)

        # Detect with 1 hour window - should only get recent ones
        tags = detect_suspicious_cluster(
            "market_timewindow",
            min_fresh_wallets=2,
            time_window_hours=1.0,
            db_path=self.test_db_path,
        )

        # Should detect the 2 recent wallets (within 1 hour)
        self.assertEqual(len(tags), 2)


class TestClassifyWallet(TestWalletClassifier):
    """Test comprehensive wallet classification."""

    def test_classify_wallet_multiple_tags(self):
        """Test that a wallet can have multiple classifications."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Create a fresh whale
        trades = [
            WalletTrade(
                wallet="0xfreshwhale",
                market_id="market_1",
                side="yes",
                price=0.65,
                size=20000.0,  # Large trade
                timestamp=today_start + timedelta(hours=1),
                tx_hash="0xhash_freshwhale1",
            ),
        ]
        self.feed.store_trades(trades)

        # Classify
        tags = classify_wallet("0xfreshwhale", db_path=self.test_db_path)

        # Should have both fresh and whale tags
        self.assertEqual(len(tags), 2)
        tag_types = [tag.tag for tag in tags]
        self.assertIn("fresh", tag_types)
        self.assertIn("whale", tag_types)

    def test_classify_wallet_no_tags(self):
        """Test wallet with no special classifications."""
        # Regular wallet with normal trades
        trades = [
            WalletTrade(
                wallet="0xregular",
                market_id="market_1",
                side="yes",
                price=0.65,
                size=100.0,
                timestamp=datetime.now() - timedelta(days=5),
                tx_hash="0xhash_regular1",
            ),
        ]
        self.feed.store_trades(trades)

        tags = classify_wallet("0xregular", db_path=self.test_db_path)
        # Should only have no high-confidence tag (no outcomes data)
        self.assertEqual(len(tags), 0)


class TestDatabaseOperations(TestWalletClassifier):
    """Test database operations for wallet tags."""

    def test_ensure_wallet_tags_table_creates_table(self):
        """Test that _ensure_wallet_tags_table creates the table."""
        db = _get_db(self.test_db_path)
        _ensure_wallet_tags_table(db)

        self.assertIn("wallet_tags", db.table_names())

    def test_store_wallet_tag(self):
        """Test storing a single wallet tag."""
        tag = WalletTag(
            wallet="0xtest123",
            tag="whale",
            confidence=1.0,
            metadata={"threshold": 10000.0},
        )

        result = store_wallet_tag(tag, db_path=self.test_db_path)
        self.assertTrue(result)

        # Verify it was stored
        tags = get_wallet_tags(wallet="0xtest123", db_path=self.test_db_path)
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0]["tag"], "whale")

    def test_store_wallet_tags_batch(self):
        """Test batch storing wallet tags."""
        tags = [
            WalletTag(
                wallet=f"0xbatch{i}",
                tag="fresh",
                confidence=1.0,
                metadata={},
            )
            for i in range(5)
        ]

        count = store_wallet_tags(tags, db_path=self.test_db_path)
        self.assertEqual(count, 5)

        # Verify all were stored
        all_tags = get_wallet_tags(tag="fresh", db_path=self.test_db_path)
        self.assertEqual(len(all_tags), 5)

    def test_get_wallet_tags_filter_by_wallet(self):
        """Test retrieving tags filtered by wallet."""
        tags = [
            WalletTag(wallet="0xfilter1", tag="fresh", confidence=1.0, metadata={}),
            WalletTag(wallet="0xfilter1", tag="whale", confidence=1.0, metadata={}),
            WalletTag(wallet="0xfilter2", tag="fresh", confidence=1.0, metadata={}),
        ]
        store_wallet_tags(tags, db_path=self.test_db_path)

        # Get tags for specific wallet
        wallet_tags = get_wallet_tags(wallet="0xfilter1", db_path=self.test_db_path)
        self.assertEqual(len(wallet_tags), 2)

    def test_get_wallet_tags_filter_by_tag(self):
        """Test retrieving tags filtered by tag type."""
        tags = [
            WalletTag(wallet="0xtag1", tag="fresh", confidence=1.0, metadata={}),
            WalletTag(wallet="0xtag2", tag="whale", confidence=1.0, metadata={}),
            WalletTag(wallet="0xtag3", tag="fresh", confidence=1.0, metadata={}),
        ]
        store_wallet_tags(tags, db_path=self.test_db_path)

        # Get fresh tags
        fresh_tags = get_wallet_tags(tag="fresh", db_path=self.test_db_path)
        self.assertEqual(len(fresh_tags), 2)

    def test_get_wallet_tags_filter_by_confidence(self):
        """Test retrieving tags filtered by minimum confidence."""
        tags = [
            WalletTag(wallet="0xconf1", tag="fresh", confidence=1.0, metadata={}),
            WalletTag(
                wallet="0xconf2", tag="high_confidence", confidence=0.5, metadata={}
            ),
            WalletTag(
                wallet="0xconf3", tag="high_confidence", confidence=0.8, metadata={}
            ),
        ]
        store_wallet_tags(tags, db_path=self.test_db_path)

        # Get tags with confidence >= 0.7
        high_conf_tags = get_wallet_tags(
            min_confidence=0.7, db_path=self.test_db_path
        )
        self.assertEqual(len(high_conf_tags), 2)

    def test_get_wallet_tags_empty_database(self):
        """Test retrieving tags from empty database."""
        tags = get_wallet_tags(db_path=self.test_db_path)
        self.assertEqual(len(tags), 0)


if __name__ == "__main__":
    unittest.main()
