"""
Unit tests for mock data generator.

TODO: Test market generation
TODO: Test data consistency
TODO: Test arbitrage opportunity generation
TODO: Test edge cases
"""

import unittest
from app.core.mock_data import MockDataGenerator


class TestMockDataGenerator(unittest.TestCase):
    """Test mock data generation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.generator = MockDataGenerator(seed=42)
    
    def test_generate_single_market(self):
        """Test generating a single market."""
        market = self.generator.generate_market()
        
        self.assertIsNotNone(market)
        self.assertIn('id', market)
        self.assertIn('name', market)
        self.assertIn('outcomes', market)
        self.assertEqual(len(market['outcomes']), 2)
    
    def test_generate_multiple_markets(self):
        """Test generating multiple markets."""
        markets = self.generator.generate_markets(count=10)
        
        self.assertEqual(len(markets), 10)
        
        # Check that market IDs are unique
        ids = [m['id'] for m in markets]
        self.assertEqual(len(ids), len(set(ids)))
    
    def test_price_validity(self):
        """Test that generated prices are valid."""
        market = self.generator.generate_market()
        
        for outcome in market['outcomes']:
            price = outcome['price']
            self.assertGreaterEqual(price, 0.0)
            self.assertLessEqual(price, 1.0)
    
    # TODO: Add more tests


if __name__ == '__main__':
    unittest.main()
