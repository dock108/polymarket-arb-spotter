"""
Unit tests for event filtering functions in logger module.

Tests the new fetch_price_alert_events and fetch_depth_events functions
that support filtering by market_id, start, and end timestamps.
"""

import unittest
import tempfile
import os
import shutil
from datetime import datetime, timedelta

from app.core.logger import (
    init_db,
    log_price_alert_event,
    log_depth_event,
    fetch_price_alert_events,
    fetch_depth_events,
)


class TestPriceAlertEventFiltering(unittest.TestCase):
    """Test price alert event filtering functionality."""

    def setUp(self):
        """Set up test database for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_events.sqlite")
        init_db(self.test_db_path)

    def tearDown(self):
        """Clean up test database after each test."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_fetch_price_alerts_by_market_id(self):
        """Test fetching price alert events filtered by market ID."""
        base_time = datetime.now()
        
        # Create alerts for different markets
        alert1 = {
            "timestamp": base_time,
            "alert_id": "alert1",
            "market_id": "market_A",
            "direction": "above",
            "target_price": 0.75,
            "trigger_price": 0.76,
            "mode": "test",
            "latency_ms": 100,
        }
        alert2 = {
            "timestamp": base_time,
            "alert_id": "alert2",
            "market_id": "market_B",
            "direction": "below",
            "target_price": 0.50,
            "trigger_price": 0.49,
            "mode": "test",
            "latency_ms": 150,
        }
        
        log_price_alert_event(alert1, self.test_db_path)
        log_price_alert_event(alert2, self.test_db_path)
        
        # Fetch only market_A alerts
        alerts = fetch_price_alert_events(
            market_id="market_A", 
            db_path=self.test_db_path
        )
        
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["market_id"], "market_A")

    def test_fetch_price_alerts_by_date_range(self):
        """Test fetching price alert events filtered by date range."""
        base_time = datetime.now()
        
        # Create alerts at different times
        alert1 = {
            "timestamp": base_time - timedelta(days=2),
            "alert_id": "alert_old",
            "market_id": "market_A",
            "direction": "above",
            "target_price": 0.75,
            "trigger_price": 0.76,
            "mode": "test",
            "latency_ms": 100,
        }
        alert2 = {
            "timestamp": base_time,
            "alert_id": "alert_new",
            "market_id": "market_A",
            "direction": "below",
            "target_price": 0.50,
            "trigger_price": 0.49,
            "mode": "test",
            "latency_ms": 150,
        }
        
        log_price_alert_event(alert1, self.test_db_path)
        log_price_alert_event(alert2, self.test_db_path)
        
        # Fetch only recent alerts
        start = (base_time - timedelta(days=1)).isoformat()
        alerts = fetch_price_alert_events(
            market_id="market_A",
            start=start,
            db_path=self.test_db_path
        )
        
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["alert_id"], "alert_new")


class TestDepthEventFiltering(unittest.TestCase):
    """Test depth event filtering functionality."""

    def setUp(self):
        """Set up test database for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.test_dir, "test_events.sqlite")
        init_db(self.test_db_path)

    def tearDown(self):
        """Clean up test database after each test."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_fetch_depth_events_by_market_id(self):
        """Test fetching depth events filtered by market ID."""
        base_time = datetime.now()
        
        # Create depth events for different markets
        event1 = {
            "timestamp": base_time,
            "market_id": "market_A",
            "metrics": {"total_depth": 1000, "gap": 0.05},
            "signal_type": "thin_depth",
            "threshold_hit": "depth < 500",
            "mode": "test",
        }
        event2 = {
            "timestamp": base_time,
            "market_id": "market_B",
            "metrics": {"total_depth": 2000, "gap": 0.10},
            "signal_type": "large_gap",
            "threshold_hit": "gap > 0.08",
            "mode": "test",
        }
        
        log_depth_event(event1, self.test_db_path)
        log_depth_event(event2, self.test_db_path)
        
        # Fetch only market_A events
        events = fetch_depth_events(
            market_id="market_A",
            db_path=self.test_db_path
        )
        
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["market_id"], "market_A")
        # Verify metrics were deserialized
        self.assertIsInstance(events[0]["metrics"], dict)
        self.assertEqual(events[0]["metrics"]["total_depth"], 1000)

    def test_fetch_depth_events_by_date_range(self):
        """Test fetching depth events filtered by date range."""
        base_time = datetime.now()
        
        # Create events at different times
        event1 = {
            "timestamp": base_time - timedelta(days=2),
            "market_id": "market_A",
            "metrics": {"total_depth": 1000},
            "signal_type": "thin_depth",
            "threshold_hit": "depth < 500",
            "mode": "test",
        }
        event2 = {
            "timestamp": base_time,
            "market_id": "market_A",
            "metrics": {"total_depth": 2000},
            "signal_type": "large_gap",
            "threshold_hit": "gap > 0.08",
            "mode": "test",
        }
        
        log_depth_event(event1, self.test_db_path)
        log_depth_event(event2, self.test_db_path)
        
        # Fetch only recent events
        start = (base_time - timedelta(days=1)).isoformat()
        events = fetch_depth_events(
            market_id="market_A",
            start=start,
            db_path=self.test_db_path
        )
        
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["signal_type"], "large_gap")

    def test_fetch_depth_events_combined_filters(self):
        """Test fetching depth events with multiple filters combined."""
        base_time = datetime.now()
        
        # Create various events
        events_to_log = [
            {
                "timestamp": base_time - timedelta(days=3),
                "market_id": "market_A",
                "metrics": {"total_depth": 1000},
                "signal_type": "thin_depth",
                "threshold_hit": "test1",
                "mode": "test",
            },
            {
                "timestamp": base_time - timedelta(hours=12),
                "market_id": "market_A",
                "metrics": {"total_depth": 2000},
                "signal_type": "large_gap",
                "threshold_hit": "test2",
                "mode": "test",
            },
            {
                "timestamp": base_time - timedelta(hours=12),
                "market_id": "market_B",
                "metrics": {"total_depth": 3000},
                "signal_type": "strong_imbalance",
                "threshold_hit": "test3",
                "mode": "test",
            },
        ]
        
        for event in events_to_log:
            log_depth_event(event, self.test_db_path)
        
        # Fetch with market_id and date range
        start = (base_time - timedelta(days=1)).isoformat()
        end = base_time.isoformat()
        
        events = fetch_depth_events(
            market_id="market_A",
            start=start,
            end=end,
            db_path=self.test_db_path
        )
        
        # Should only get the market_A event within date range
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["market_id"], "market_A")
        self.assertEqual(events[0]["signal_type"], "large_gap")


if __name__ == "__main__":
    unittest.main()
