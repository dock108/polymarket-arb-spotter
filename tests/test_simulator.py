"""
Unit tests for simulator module.

TODO: Test simulation execution
TODO: Test statistics calculation
TODO: Test speed benchmarks
TODO: Add integration tests
"""

import unittest
from app.core.simulator import Simulator
from app.core.arb_detector import ArbitrageDetector
from app.core.mock_data import MockDataGenerator


class TestSimulator(unittest.TestCase):
    """Test simulation functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        detector = ArbitrageDetector(db_path=":memory:")
        generator = MockDataGenerator(seed=42)
        self.simulator = Simulator(detector=detector, data_generator=generator)
    
    def test_simulator_initialization(self):
        """Test simulator initialization."""
        self.assertIsNotNone(self.simulator)
        self.assertIsNotNone(self.simulator.detector)
        self.assertIsNotNone(self.simulator.data_generator)
    
    def test_batch_simulation(self):
        """Test batch simulation."""
        stats = self.simulator.run_batch_simulation(num_markets=20, batch_size=5)
        
        self.assertIsNotNone(stats)
        self.assertIn('markets_analyzed', stats)
        self.assertEqual(stats['markets_analyzed'], 20)
    
    def test_generate_report(self):
        """Test report generation."""
        self.simulator.run_batch_simulation(num_markets=10, batch_size=5)
        report = self.simulator.generate_report()
        
        self.assertIsInstance(report, str)
        self.assertGreater(len(report), 0)
    
    # TODO: Add more tests


if __name__ == '__main__':
    unittest.main()
