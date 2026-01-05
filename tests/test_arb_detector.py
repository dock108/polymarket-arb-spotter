"""
Unit tests for arbitrage detection module.
"""

import unittest
from datetime import datetime
from app.core.arb_detector import ArbitrageDetector, ArbitrageOpportunity, ArbAlert
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


class TestArbAlert(unittest.TestCase):
    """Test ArbAlert class and check_arbitrage method."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.detector = ArbitrageDetector(db_path=":memory:")
    
    def test_arb_alert_dataclass(self):
        """Test ArbAlert dataclass creation and to_dict."""
        alert = ArbAlert(
            profitable=True,
            reason="Test reason",
            metrics={'expected_profit_pct': 5.0, 'market_name': 'Test'}
        )
        
        self.assertTrue(alert.profitable)
        self.assertEqual(alert.reason, "Test reason")
        self.assertEqual(alert.metrics['expected_profit_pct'], 5.0)
        
        d = alert.to_dict()
        self.assertEqual(d['profitable'], True)
        self.assertEqual(d['reason'], "Test reason")
        self.assertIn('metrics', d)
    
    def test_check_arbitrage_profitable(self):
        """Test check_arbitrage with profitable opportunity."""
        # Market with sum_price = 0.80 < (1 - 0.02) = 0.98
        market = {
            'id': 'arb_market',
            'name': 'Profitable Arbitrage Market',
            'outcomes': [
                {'name': 'Yes', 'price': 0.40, 'volume': 10000},
                {'name': 'No', 'price': 0.40, 'volume': 10000}
            ],
        }
        
        alert = self.detector.check_arbitrage(market, fee_buffer=0.02)
        
        self.assertTrue(alert.profitable)
        self.assertIn('Arbitrage opportunity', alert.reason)
        self.assertEqual(alert.metrics['market_name'], 'Profitable Arbitrage Market')
        self.assertAlmostEqual(alert.metrics['sum_price'], 0.80)
        self.assertAlmostEqual(alert.metrics['prices']['yes_price'], 0.40)
        self.assertAlmostEqual(alert.metrics['prices']['no_price'], 0.40)
        self.assertIn('timestamp', alert.metrics)
        self.assertGreater(alert.metrics['expected_profit_pct'], 0)
    
    def test_check_arbitrage_not_profitable(self):
        """Test check_arbitrage with no opportunity."""
        # Market with sum_price = 1.00 >= (1 - 0.02) = 0.98
        market = {
            'id': 'normal_market',
            'name': 'Normal Market',
            'outcomes': [
                {'name': 'Yes', 'price': 0.50, 'volume': 10000},
                {'name': 'No', 'price': 0.50, 'volume': 10000}
            ],
        }
        
        alert = self.detector.check_arbitrage(market, fee_buffer=0.02)
        
        self.assertFalse(alert.profitable)
        self.assertIn('No arbitrage', alert.reason)
        self.assertEqual(alert.metrics['expected_profit_pct'], 0.0)
        self.assertEqual(alert.metrics['market_name'], 'Normal Market')
        self.assertAlmostEqual(alert.metrics['sum_price'], 1.00)
    
    def test_check_arbitrage_with_high_sum(self):
        """Test check_arbitrage when prices sum > 1."""
        # Market with sum_price = 1.05 > 0.98
        market = {
            'id': 'high_sum_market',
            'name': 'High Sum Market',
            'outcomes': [
                {'name': 'Yes', 'price': 0.55, 'volume': 10000},
                {'name': 'No', 'price': 0.50, 'volume': 10000}
            ],
        }
        
        alert = self.detector.check_arbitrage(market, fee_buffer=0.02)
        
        self.assertFalse(alert.profitable)
        self.assertAlmostEqual(alert.metrics['sum_price'], 1.05)
    
    def test_check_arbitrage_insufficient_outcomes(self):
        """Test check_arbitrage with insufficient outcomes."""
        market = {
            'id': 'bad_market',
            'name': 'Single Outcome Market',
            'outcomes': [
                {'name': 'Yes', 'price': 0.50, 'volume': 10000}
            ],
        }
        
        alert = self.detector.check_arbitrage(market, fee_buffer=0.02)
        
        self.assertFalse(alert.profitable)
        self.assertIn('Insufficient outcomes', alert.reason)
        self.assertEqual(alert.metrics['expected_profit_pct'], 0.0)
    
    def test_check_arbitrage_empty_outcomes(self):
        """Test check_arbitrage with empty outcomes list."""
        market = {
            'id': 'empty_market',
            'name': 'Empty Market',
            'outcomes': [],
        }
        
        alert = self.detector.check_arbitrage(market, fee_buffer=0.02)
        
        self.assertFalse(alert.profitable)
        self.assertIn('Insufficient outcomes', alert.reason)
    
    def test_check_arbitrage_custom_fee_buffer(self):
        """Test check_arbitrage with custom fee buffer."""
        # With fee_buffer=0.10, threshold = 0.90
        # sum_price = 0.85 < 0.90 should be profitable
        market = {
            'id': 'custom_fee_market',
            'name': 'Custom Fee Market',
            'outcomes': [
                {'name': 'Yes', 'price': 0.42, 'volume': 10000},
                {'name': 'No', 'price': 0.43, 'volume': 10000}
            ],
        }
        
        alert = self.detector.check_arbitrage(market, fee_buffer=0.10)
        
        self.assertTrue(alert.profitable)
        self.assertAlmostEqual(alert.metrics['threshold'], 0.90)
        self.assertAlmostEqual(alert.metrics['sum_price'], 0.85)
    
    def test_check_arbitrage_boundary_case_below_threshold(self):
        """Test check_arbitrage at boundary just below threshold."""
        # sum_price = 0.97, threshold = 0.98, should be profitable
        market = {
            'id': 'boundary_market',
            'name': 'Boundary Market',
            'outcomes': [
                {'name': 'Yes', 'price': 0.485, 'volume': 10000},
                {'name': 'No', 'price': 0.485, 'volume': 10000}
            ],
        }
        
        alert = self.detector.check_arbitrage(market, fee_buffer=0.02)
        
        self.assertTrue(alert.profitable)
        self.assertAlmostEqual(alert.metrics['sum_price'], 0.97)
    
    def test_check_arbitrage_boundary_case_at_threshold(self):
        """Test check_arbitrage at exact threshold."""
        # sum_price = 0.98, threshold = 0.98, should NOT be profitable
        market = {
            'id': 'threshold_market',
            'name': 'Threshold Market',
            'outcomes': [
                {'name': 'Yes', 'price': 0.49, 'volume': 10000},
                {'name': 'No', 'price': 0.49, 'volume': 10000}
            ],
        }
        
        alert = self.detector.check_arbitrage(market, fee_buffer=0.02)
        
        self.assertFalse(alert.profitable)
        self.assertAlmostEqual(alert.metrics['sum_price'], 0.98)
    
    def test_check_arbitrage_metrics_structure(self):
        """Test that all required metrics are present."""
        market = {
            'id': 'metrics_test',
            'name': 'Metrics Test Market',
            'outcomes': [
                {'name': 'Yes', 'price': 0.35, 'volume': 10000},
                {'name': 'No', 'price': 0.35, 'volume': 10000}
            ],
        }
        
        alert = self.detector.check_arbitrage(market, fee_buffer=0.02)
        
        # Check all required metrics
        self.assertIn('expected_profit_pct', alert.metrics)
        self.assertIn('market_name', alert.metrics)
        self.assertIn('prices', alert.metrics)
        self.assertIn('timestamp', alert.metrics)
        self.assertIn('sum_price', alert.metrics)
        
        # Check prices structure
        self.assertIn('yes_price', alert.metrics['prices'])
        self.assertIn('no_price', alert.metrics['prices'])
    
    def test_check_arbitrage_expected_profit_calculation(self):
        """Test expected profit percentage calculation."""
        # sum_price = 0.80, profit_margin = 0.20
        # expected_profit_pct = (0.20 / 0.80) * 100 = 25%
        market = {
            'id': 'profit_calc_market',
            'name': 'Profit Calc Market',
            'outcomes': [
                {'name': 'Yes', 'price': 0.40, 'volume': 10000},
                {'name': 'No', 'price': 0.40, 'volume': 10000}
            ],
        }
        
        alert = self.detector.check_arbitrage(market, fee_buffer=0.02)
        
        self.assertTrue(alert.profitable)
        self.assertAlmostEqual(alert.metrics['expected_profit_pct'], 25.0, places=1)


if __name__ == '__main__':
    unittest.main()
