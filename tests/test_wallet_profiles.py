"""
Unit tests for the wallet profiles module.

Tests wallet profile calculation, ranking, and statistics aggregation.
"""

import os
import shutil
import tempfile
import unittest
from datetime import datetime

from app.core.wallet_feed import WalletFeed, WalletTrade
from app.core.wallet_profiles import (
    WalletProfile,
    get_wallet_profile,
    rank_wallets,
    get_all_wallet_profiles,
    _calculate_wallet_stats,
)


class TestWalletProfiles(unittest.TestCase):
    """Base test class for wallet profiles."""

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
            WalletTrade(
                wallet="0x1111111111111111",
                market_id="market_1",
                side="yes",
                price=0.65,
                size=100.0,
                timestamp=datetime(2024, 1, 1, 12, 0, 0),
                tx_hash="0xhash1",
            ),
            WalletTrade(
                wallet="0x1111111111111111",
                market_id="market_1",
                side="yes",
                price=0.70,
                size=50.0,
                timestamp=datetime(2024, 1, 2, 12, 0, 0),
                tx_hash="0xhash2",
            ),
            WalletTrade(
                wallet="0x1111111111111111",
                market_id="market_2",
                side="no",
                price=0.40,
                size=200.0,
                timestamp=datetime(2024, 1, 3, 12, 0, 0),
                tx_hash="0xhash3",
            ),
            WalletTrade(
                wallet="0x2222222222222222",
                market_id="market_1",
                side="no",
                price=0.35,
                size=150.0,
                timestamp=datetime(2024, 1, 4, 12, 0, 0),
                tx_hash="0xhash4",
            ),
            WalletTrade(
                wallet="0x2222222222222222",
                market_id="market_3",
                side="yes",
                price=0.55,
                size=100.0,
                timestamp=datetime(2024, 1, 5, 12, 0, 0),
                tx_hash="0xhash5",
            ),
        ]
        self.feed.store_trades(trades)


class TestWalletProfileDataclass(TestWalletProfiles):
    """Test WalletProfile dataclass."""

    def test_wallet_profile_creation(self):
        """Test creating a WalletProfile object."""
        profile = WalletProfile(
            wallet="0x1234567890abcdef",
            total_trades=10,
            avg_entry_price=0.55,
            realized_outcomes=5,
            win_rate=60.0,
            avg_roi=15.5,
            markets_traded=["market_1", "market_2"],
            categories={"politics", "crypto"},
            total_volume=1000.0,
            total_profit=150.0,
        )

        self.assertEqual(profile.wallet, "0x1234567890abcdef")
        self.assertEqual(profile.total_trades, 10)
        self.assertEqual(profile.avg_entry_price, 0.55)
        self.assertEqual(profile.realized_outcomes, 5)
        self.assertEqual(profile.win_rate, 60.0)
        self.assertEqual(profile.avg_roi, 15.5)
        self.assertEqual(len(profile.markets_traded), 2)
        self.assertEqual(len(profile.categories), 2)

    def test_wallet_profile_to_dict(self):
        """Test converting WalletProfile to dictionary."""
        profile = WalletProfile(
            wallet="0x1234567890abcdef",
            total_trades=10,
            avg_entry_price=0.55,
            realized_outcomes=5,
            win_rate=60.0,
            avg_roi=15.5,
            markets_traded=["market_1", "market_2"],
            categories={"politics"},
            total_volume=1000.0,
            total_profit=150.0,
        )

        profile_dict = profile.to_dict()

        self.assertEqual(profile_dict["wallet"], "0x1234567890abcdef")
        self.assertEqual(profile_dict["total_trades"], 10)
        self.assertEqual(profile_dict["avg_entry_price"], 0.55)
        self.assertEqual(profile_dict["win_rate"], 60.0)
        self.assertIn("politics", profile_dict["categories"])


class TestCalculateWalletStats(unittest.TestCase):
    """Test wallet statistics calculation."""

    def test_calculate_stats_empty_trades(self):
        """Test calculation with no trades."""
        stats = _calculate_wallet_stats([])

        self.assertEqual(stats["total_trades"], 0)
        self.assertEqual(stats["avg_entry_price"], 0.0)
        self.assertEqual(stats["win_rate"], 0.0)
        self.assertEqual(stats["total_volume"], 0.0)

    def test_calculate_stats_basic(self):
        """Test basic statistics calculation."""
        trades = [
            {
                "wallet": "0x1111",
                "market_id": "market_1",
                "side": "yes",
                "price": 0.60,
                "size": 100.0,
                "timestamp": "2024-01-01T12:00:00",
                "tx_hash": "0xhash1",
            },
            {
                "wallet": "0x1111",
                "market_id": "market_2",
                "side": "no",
                "price": 0.40,
                "size": 200.0,
                "timestamp": "2024-01-02T12:00:00",
                "tx_hash": "0xhash2",
            },
        ]

        stats = _calculate_wallet_stats(trades)

        self.assertEqual(stats["total_trades"], 2)
        # Volume-weighted avg: (0.60*100 + 0.40*200) / 300 = 0.4666...
        self.assertAlmostEqual(stats["avg_entry_price"], 0.4667, places=3)
        self.assertEqual(stats["total_volume"], 300.0)  # 100 + 200
        self.assertEqual(len(stats["markets_traded"]), 2)

    def test_calculate_stats_with_outcomes_winning(self):
        """Test calculation with market outcomes - winning trades."""
        trades = [
            {
                "wallet": "0x1111",
                "market_id": "market_1",
                "side": "yes",
                "price": 0.60,
                "size": 100.0,
                "timestamp": "2024-01-01T12:00:00",
                "tx_hash": "0xhash1",
            },
        ]

        market_outcomes = {"market_1": {"outcome": "yes", "resolved": True}}

        stats = _calculate_wallet_stats(trades, market_outcomes)

        self.assertEqual(stats["realized_outcomes"], 1)
        self.assertEqual(stats["win_rate"], 100.0)  # 1 winning trade out of 1
        # Profit = size * (1 - price) = 100 * (1 - 0.60) = 40
        self.assertAlmostEqual(stats["total_profit"], 40.0, places=2)
        # ROI = (total_profit / total_volume) * 100 = (40 / 100) * 100 = 40%
        self.assertAlmostEqual(stats["avg_roi"], 40.0, places=2)

    def test_calculate_stats_with_outcomes_losing(self):
        """Test calculation with market outcomes - losing trades."""
        trades = [
            {
                "wallet": "0x1111",
                "market_id": "market_1",
                "side": "yes",
                "price": 0.60,
                "size": 100.0,
                "timestamp": "2024-01-01T12:00:00",
                "tx_hash": "0xhash1",
            },
        ]

        market_outcomes = {
            "market_1": {"outcome": "no", "resolved": True}  # Trade was YES but NO won
        }

        stats = _calculate_wallet_stats(trades, market_outcomes)

        self.assertEqual(stats["realized_outcomes"], 1)
        self.assertEqual(stats["win_rate"], 0.0)  # 0 winning trades
        # Loss = size * price = 100 * 0.60 = -60
        self.assertAlmostEqual(stats["total_profit"], -60.0, places=2)
        # ROI = (-60 / 100) * 100 = -60%
        self.assertAlmostEqual(stats["avg_roi"], -60.0, places=2)

    def test_calculate_stats_mixed_outcomes(self):
        """Test calculation with mixed winning and losing trades."""
        trades = [
            {
                "wallet": "0x1111",
                "market_id": "market_1",
                "side": "yes",
                "price": 0.60,
                "size": 100.0,
                "timestamp": "2024-01-01T12:00:00",
                "tx_hash": "0xhash1",
            },
            {
                "wallet": "0x1111",
                "market_id": "market_2",
                "side": "no",
                "price": 0.40,
                "size": 100.0,
                "timestamp": "2024-01-02T12:00:00",
                "tx_hash": "0xhash2",
            },
        ]

        market_outcomes = {
            "market_1": {"outcome": "yes", "resolved": True},  # Win
            "market_2": {"outcome": "yes", "resolved": True},  # Loss (traded NO)
        }

        stats = _calculate_wallet_stats(trades, market_outcomes)

        self.assertEqual(stats["realized_outcomes"], 2)
        self.assertEqual(stats["win_rate"], 50.0)  # 1 win out of 2
        # Profit from market_1: 100 * (1 - 0.60) = 40
        # Loss from market_2: -100 * 0.40 = -40
        # Total profit: 0
        self.assertAlmostEqual(stats["total_profit"], 0.0, places=2)


class TestGetWalletProfile(TestWalletProfiles):
    """Test getting individual wallet profiles."""

    def test_get_profile_no_trades(self):
        """Test getting profile for wallet with no trades."""
        profile = get_wallet_profile("0xnonexistent", db_path=self.test_db_path)
        self.assertIsNone(profile)

    def test_get_profile_basic(self):
        """Test getting profile for wallet with trades."""
        self._store_sample_trades()

        profile = get_wallet_profile("0x1111111111111111", db_path=self.test_db_path)

        self.assertIsNotNone(profile)
        self.assertEqual(profile.wallet, "0x1111111111111111")
        self.assertEqual(profile.total_trades, 3)
        # Volume-weighted avg: (0.65*100 + 0.70*50 + 0.40*200) / 350 = 0.5143
        self.assertAlmostEqual(profile.avg_entry_price, 0.5143, places=3)
        self.assertEqual(len(profile.markets_traded), 2)  # market_1 and market_2
        self.assertIn("market_1", profile.markets_traded)
        self.assertIn("market_2", profile.markets_traded)

    def test_get_profile_with_outcomes(self):
        """Test getting profile with market outcomes."""
        self._store_sample_trades()

        market_outcomes = {
            "market_1": {"outcome": "yes", "resolved": True},
            "market_2": {"outcome": "no", "resolved": True},
        }

        profile = get_wallet_profile(
            "0x1111111111111111",
            market_outcomes=market_outcomes,
            db_path=self.test_db_path,
        )

        self.assertIsNotNone(profile)
        self.assertEqual(profile.realized_outcomes, 2)
        # Win rate: 3 trades across 2 resolved markets, all on winning side = 100%
        self.assertEqual(profile.win_rate, 100.0)
        self.assertGreater(profile.total_profit, 0)

    def test_get_profile_to_dict(self):
        """Test converting profile to dictionary."""
        self._store_sample_trades()

        profile = get_wallet_profile("0x1111111111111111", db_path=self.test_db_path)
        profile_dict = profile.to_dict()

        self.assertIn("wallet", profile_dict)
        self.assertIn("total_trades", profile_dict)
        self.assertIn("win_rate", profile_dict)
        self.assertEqual(profile_dict["wallet"], "0x1111111111111111")


class TestRankWallets(TestWalletProfiles):
    """Test wallet ranking functionality."""

    def test_rank_wallets_no_trades(self):
        """Test ranking with no trades in database."""
        result = rank_wallets(db_path=self.test_db_path)
        self.assertEqual(len(result), 0)

    def test_rank_wallets_min_trades_filter(self):
        """Test that min_trades filter works."""
        self._store_sample_trades()

        # Wallet 0x1111 has 3 trades, wallet 0x2222 has 2 trades
        result = rank_wallets(min_trades=3, db_path=self.test_db_path)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].wallet, "0x1111111111111111")

        result = rank_wallets(min_trades=2, db_path=self.test_db_path)
        self.assertEqual(len(result), 2)

    def test_rank_wallets_by_volume(self):
        """Test ranking by trading volume."""
        self._store_sample_trades()

        result = rank_wallets(by="volume", min_trades=1, db_path=self.test_db_path)

        self.assertGreater(len(result), 0)
        # Wallet 0x1111 has volume 350 (100+50+200)
        # Wallet 0x2222 has volume 250 (150+100)
        self.assertEqual(result[0].wallet, "0x1111111111111111")
        self.assertAlmostEqual(result[0].total_volume, 350.0, places=1)

    def test_rank_wallets_by_win_rate(self):
        """Test ranking by win rate."""
        self._store_sample_trades()

        market_outcomes = {
            "market_1": {"outcome": "yes", "resolved": True},
            "market_2": {"outcome": "no", "resolved": True},
            "market_3": {"outcome": "no", "resolved": True},
        }

        result = rank_wallets(
            by="win_rate",
            market_outcomes=market_outcomes,
            min_trades=1,
            db_path=self.test_db_path,
        )

        self.assertGreater(len(result), 0)
        # Both wallets should have calculated win rates
        for profile in result:
            self.assertGreaterEqual(profile.win_rate, 0.0)
            self.assertLessEqual(profile.win_rate, 100.0)

    def test_rank_wallets_by_profit(self):
        """Test ranking by total profit."""
        self._store_sample_trades()

        market_outcomes = {
            "market_1": {"outcome": "yes", "resolved": True},
            "market_2": {"outcome": "no", "resolved": True},
        }

        result = rank_wallets(
            by="profit",
            market_outcomes=market_outcomes,
            min_trades=1,
            db_path=self.test_db_path,
        )

        self.assertGreater(len(result), 0)
        # Results should be sorted by profit descending
        if len(result) > 1:
            self.assertGreaterEqual(result[0].total_profit, result[1].total_profit)

    def test_rank_wallets_by_roi(self):
        """Test ranking by ROI."""
        self._store_sample_trades()

        market_outcomes = {
            "market_1": {"outcome": "yes", "resolved": True},
        }

        result = rank_wallets(
            by="roi",
            market_outcomes=market_outcomes,
            min_trades=1,
            db_path=self.test_db_path,
        )

        self.assertGreater(len(result), 0)

    def test_rank_wallets_limit(self):
        """Test that limit parameter works."""
        self._store_sample_trades()

        result = rank_wallets(
            by="volume", min_trades=1, limit=1, db_path=self.test_db_path
        )
        self.assertEqual(len(result), 1)

    def test_rank_wallets_invalid_metric(self):
        """Test that invalid metric returns empty list."""
        self._store_sample_trades()

        result = rank_wallets(by="invalid_metric", db_path=self.test_db_path)
        self.assertEqual(len(result), 0)


class TestGetAllWalletProfiles(TestWalletProfiles):
    """Test getting all wallet profiles."""

    def test_get_all_profiles_empty(self):
        """Test getting all profiles with no trades."""
        result = get_all_wallet_profiles(db_path=self.test_db_path)
        self.assertEqual(len(result), 0)

    def test_get_all_profiles(self):
        """Test getting all profiles."""
        self._store_sample_trades()

        result = get_all_wallet_profiles(db_path=self.test_db_path)
        self.assertEqual(len(result), 2)

        wallets = [p.wallet for p in result]
        self.assertIn("0x1111111111111111", wallets)
        self.assertIn("0x2222222222222222", wallets)

    def test_get_all_profiles_min_trades(self):
        """Test getting all profiles with min_trades filter."""
        self._store_sample_trades()

        result = get_all_wallet_profiles(min_trades=3, db_path=self.test_db_path)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].wallet, "0x1111111111111111")


class TestEdgeCases(TestWalletProfiles):
    """Test edge cases and error handling."""

    def test_single_trade(self):
        """Test profile with single trade."""
        trade = WalletTrade(
            wallet="0x9999999999999999",
            market_id="market_1",
            side="yes",
            price=0.50,
            size=100.0,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            tx_hash="0xhash_single",
        )
        self.feed.store_trade(trade)

        profile = get_wallet_profile("0x9999999999999999", db_path=self.test_db_path)

        self.assertIsNotNone(profile)
        self.assertEqual(profile.total_trades, 1)
        self.assertEqual(profile.avg_entry_price, 0.50)
        self.assertEqual(len(profile.markets_traded), 1)

    def test_zero_size_trades(self):
        """Test handling of trades with zero size."""
        trades = [
            WalletTrade(
                wallet="0x8888888888888888",
                market_id="market_1",
                side="yes",
                price=0.60,
                size=0.0,
                timestamp=datetime(2024, 1, 1, 12, 0, 0),
                tx_hash="0xhash_zero",
            ),
        ]
        self.feed.store_trades(trades)

        profile = get_wallet_profile("0x8888888888888888", db_path=self.test_db_path)

        self.assertIsNotNone(profile)
        self.assertEqual(profile.total_volume, 0.0)

    def test_multiple_trades_same_market(self):
        """Test wallet with multiple trades in same market."""
        trades = [
            WalletTrade(
                wallet="0x7777777777777777",
                market_id="market_1",
                side="yes",
                price=0.50,
                size=100.0,
                timestamp=datetime(2024, 1, 1, 12, 0, 0),
                tx_hash="0xhash_a",
            ),
            WalletTrade(
                wallet="0x7777777777777777",
                market_id="market_1",
                side="yes",
                price=0.60,
                size=50.0,
                timestamp=datetime(2024, 1, 2, 12, 0, 0),
                tx_hash="0xhash_b",
            ),
            WalletTrade(
                wallet="0x7777777777777777",
                market_id="market_1",
                side="no",
                price=0.40,
                size=75.0,
                timestamp=datetime(2024, 1, 3, 12, 0, 0),
                tx_hash="0xhash_c",
            ),
        ]
        self.feed.store_trades(trades)

        profile = get_wallet_profile("0x7777777777777777", db_path=self.test_db_path)

        self.assertIsNotNone(profile)
        self.assertEqual(profile.total_trades, 3)
        self.assertEqual(len(profile.markets_traded), 1)
        self.assertEqual(profile.markets_traded[0], "market_1")


if __name__ == "__main__":
    unittest.main()
