"""
Unit tests for arbitrage detection module.
"""

import unittest
from datetime import datetime
from app.core.arb_detector import ArbitrageDetector, ArbitrageOpportunity
from app.core.mock_data import MockDataGenerator


class TestArbitrageDetector(unittest.TestCase):
    """Test arbitrage detection functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.detector = ArbitrageDetector(db_path=":memory:")
    
    def test_detector_initialization(self):
        """Test detector initialization."""
        self.assertIsNotNone(self.detector)
        self.assertIsNotNone(self.detector.db_path)
    
    def test_detect_opportunities_empty(self):
        """Test detection with no market data."""
        opportunities = self.detector.detect_opportunities([])
        self.assertEqual(len(opportunities), 0)
    
    def test_save_opportunity(self):
        """Test saving opportunity to database."""
        opp = ArbitrageOpportunity(
            market_id="test_market",
            market_name="Test Market",
            opportunity_type="two-way",
            expected_profit=10.0,
            expected_return_pct=1.5,
            positions=[],
            detected_at=datetime.now()
        )
        
        # Should not raise exception
        self.detector.save_opportunity(opp)
    
    def test_get_recent_opportunities(self):
        """Test retrieving recent opportunities."""
        opportunities = self.detector.get_recent_opportunities(limit=10)
        self.assertIsInstance(opportunities, list)
    
    def test_detect_two_way_arbitrage(self):
        """Test detection of two-way arbitrage opportunities."""
        # Create a market with clear arbitrage (prices sum to less than 1)
        market = {
            'id': 'arb_market_1',
            'name': 'Arbitrage Test Market',
            'outcomes': [
                {'name': 'Yes', 'price': 0.40, 'volume': 10000},
                {'name': 'No', 'price': 0.40, 'volume': 10000}
            ],
            'expires_at': '2025-12-31T23:59:59',
            'liquidity': 100000
        }
        
        opportunities = self.detector.detect_opportunities([market])
        
        self.assertEqual(len(opportunities), 1)
        opp = opportunities[0]
        self.assertEqual(opp.market_id, 'arb_market_1')
        self.assertEqual(opp.opportunity_type, 'two-way')
        self.assertGreater(opp.expected_profit, 0)
        self.assertGreater(opp.expected_return_pct, 0)
    
    def test_no_arbitrage_normal_market(self):
        """Test that normal markets don't trigger arbitrage detection."""
        # Create a market without arbitrage (prices sum to ~1.0)
        market = {
            'id': 'normal_market_1',
            'name': 'Normal Market',
            'outcomes': [
                {'name': 'Yes', 'price': 0.50, 'volume': 10000},
                {'name': 'No', 'price': 0.50, 'volume': 10000}
            ],
            'expires_at': '2025-12-31T23:59:59',
            'liquidity': 50000
        }
        
        opportunities = self.detector.detect_opportunities([market])
        self.assertEqual(len(opportunities), 0)
    
    def test_no_arbitrage_high_sum(self):
        """Test that markets with price sum > 1 don't trigger detection."""
        market = {
            'id': 'high_sum_market',
            'name': 'High Sum Market',
            'outcomes': [
                {'name': 'Yes', 'price': 0.55, 'volume': 10000},
                {'name': 'No', 'price': 0.50, 'volume': 10000}
            ],
            'expires_at': '2025-12-31T23:59:59',
            'liquidity': 50000
        }
        
        opportunities = self.detector.detect_opportunities([market])
        self.assertEqual(len(opportunities), 0)
    
    def test_detect_multiple_markets(self):
        """Test detection across multiple markets."""
        markets = [
            {
                'id': 'normal_1',
                'name': 'Normal Market 1',
                'outcomes': [
                    {'name': 'Yes', 'price': 0.50, 'volume': 10000},
                    {'name': 'No', 'price': 0.50, 'volume': 10000}
                ],
                'expires_at': '2025-12-31T23:59:59',
                'liquidity': 50000
            },
            {
                'id': 'arb_1',
                'name': 'Arbitrage Market 1',
                'outcomes': [
                    {'name': 'Yes', 'price': 0.35, 'volume': 10000},
                    {'name': 'No', 'price': 0.35, 'volume': 10000}
                ],
                'expires_at': '2025-12-31T23:59:59',
                'liquidity': 100000
            },
            {
                'id': 'arb_2',
                'name': 'Arbitrage Market 2',
                'outcomes': [
                    {'name': 'Yes', 'price': 0.40, 'volume': 10000},
                    {'name': 'No', 'price': 0.45, 'volume': 10000}
                ],
                'expires_at': '2025-12-31T23:59:59',
                'liquidity': 75000
            },
        ]
        
        opportunities = self.detector.detect_opportunities(markets)
        
        # Should find 2 arbitrage opportunities
        self.assertEqual(len(opportunities), 2)
        arb_ids = {opp.market_id for opp in opportunities}
        self.assertIn('arb_1', arb_ids)
        self.assertIn('arb_2', arb_ids)
    
    def test_opportunity_positions(self):
        """Test that opportunities include correct positions."""
        market = {
            'id': 'position_test',
            'name': 'Position Test',
            'outcomes': [
                {'name': 'Yes', 'price': 0.40, 'volume': 5000},
                {'name': 'No', 'price': 0.40, 'volume': 8000}
            ],
            'expires_at': '2025-12-31T23:59:59',
            'liquidity': 50000
        }
        
        opportunities = self.detector.detect_opportunities([market])
        self.assertEqual(len(opportunities), 1)
        
        opp = opportunities[0]
        self.assertEqual(len(opp.positions), 2)
        
        # Check position details
        yes_pos = next(p for p in opp.positions if p['outcome'] == 'Yes')
        self.assertEqual(yes_pos['action'], 'BUY')
        self.assertEqual(yes_pos['price'], 0.40)
        self.assertEqual(yes_pos['volume'], 5000)
    
    def test_risk_score_calculation(self):
        """Test risk score is calculated."""
        market = {
            'id': 'risk_test',
            'name': 'Risk Test',
            'outcomes': [
                {'name': 'Yes', 'price': 0.30, 'volume': 10000},
                {'name': 'No', 'price': 0.30, 'volume': 10000}
            ],
            'expires_at': '2025-12-31T23:59:59',
            'liquidity': 200000  # High liquidity = lower risk
        }
        
        opportunities = self.detector.detect_opportunities([market])
        self.assertEqual(len(opportunities), 1)
        
        opp = opportunities[0]
        # Risk score should be calculated and within valid range
        self.assertGreaterEqual(opp.risk_score, 0.0)
        self.assertLessEqual(opp.risk_score, 1.0)
    
    def test_integration_with_mock_generator(self):
        """Test detection with mock data generator."""
        generator = MockDataGenerator(seed=42, arb_frequency=0.5)
        snapshots = generator.generate_snapshots(count=100)
        
        opportunities = self.detector.detect_opportunities(snapshots)
        
        # With 50% arb frequency, should find some opportunities
        self.assertGreater(len(opportunities), 0)
        
        # All opportunities should be valid
        for opp in opportunities:
            self.assertIsInstance(opp, ArbitrageOpportunity)
            self.assertGreater(opp.expected_profit, 0)
    
    def test_opportunity_to_dict(self):
        """Test converting opportunity to dictionary."""
        opp = ArbitrageOpportunity(
            market_id="test_market",
            market_name="Test Market",
            opportunity_type="two-way",
            expected_profit=20.0,
            expected_return_pct=25.0,
            positions=[{'outcome': 'Yes', 'action': 'BUY', 'price': 0.4}],
            detected_at=datetime.now(),
            risk_score=0.3
        )
        
        d = opp.to_dict()
        
        self.assertEqual(d['market_id'], 'test_market')
        self.assertEqual(d['expected_profit'], 20.0)
        self.assertEqual(d['risk_score'], 0.3)
        self.assertIn('detected_at', d)


if __name__ == '__main__':
    unittest.main()
