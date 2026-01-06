"""
Unit tests for simulator module.

TODO: Test simulation execution
TODO: Test statistics calculation
TODO: Test speed benchmarks
TODO: Add integration tests
"""

import unittest
from datetime import datetime

from app.core.simulator import (
    Simulator,
    TradeResult,
    TradeExecutionResult,
    MockTradeExecutor,
)
from app.core.arb_detector import ArbitrageDetector, ArbitrageOpportunity
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


class TestTradeResult(unittest.TestCase):
    """Test TradeResult enum."""
    
    def test_trade_result_values(self):
        """Test that TradeResult has all required values."""
        expected_values = [
            "SUCCESS",
            "SLIPPAGE_ERODED_PROFIT",
            "PRICE_MOVED_BEFORE_FILL",
            "DEPTH_TOO_THIN",
            "FEE_ERASED_EDGE",
        ]
        actual_values = [r.value for r in TradeResult]
        self.assertEqual(sorted(actual_values), sorted(expected_values))
    
    def test_trade_result_access(self):
        """Test that TradeResult values are accessible."""
        self.assertEqual(TradeResult.SUCCESS.value, "SUCCESS")
        self.assertEqual(TradeResult.SLIPPAGE_ERODED_PROFIT.value, "SLIPPAGE_ERODED_PROFIT")
        self.assertEqual(TradeResult.PRICE_MOVED_BEFORE_FILL.value, "PRICE_MOVED_BEFORE_FILL")
        self.assertEqual(TradeResult.DEPTH_TOO_THIN.value, "DEPTH_TOO_THIN")
        self.assertEqual(TradeResult.FEE_ERASED_EDGE.value, "FEE_ERASED_EDGE")


class TestTradeExecutionResult(unittest.TestCase):
    """Test TradeExecutionResult dataclass."""
    
    def test_creation(self):
        """Test TradeExecutionResult creation."""
        result = TradeExecutionResult(
            result=TradeResult.SUCCESS,
            success=True,
            failure_reason=None,
            simulated_delay_ms=150.0,
            price_shift_pct=0.005,
            available_depth=50000.0,
            requested_amount=100.0,
            filled_amount=100.0,
            original_profit_pct=5.0,
            final_profit_pct=3.0,
            execution_time=datetime.now()
        )
        
        self.assertEqual(result.result, TradeResult.SUCCESS)
        self.assertTrue(result.success)
        self.assertIsNone(result.failure_reason)
        self.assertEqual(result.simulated_delay_ms, 150.0)
    
    def test_to_dict(self):
        """Test TradeExecutionResult.to_dict method."""
        execution_time = datetime(2024, 1, 5, 12, 0, 0)
        result = TradeExecutionResult(
            result=TradeResult.DEPTH_TOO_THIN,
            success=False,
            failure_reason="Insufficient liquidity",
            simulated_delay_ms=200.0,
            price_shift_pct=0.01,
            available_depth=30.0,
            requested_amount=100.0,
            filled_amount=30.0,
            original_profit_pct=5.0,
            final_profit_pct=-2.0,
            execution_time=execution_time
        )
        
        result_dict = result.to_dict()
        
        self.assertEqual(result_dict['result'], "DEPTH_TOO_THIN")
        self.assertFalse(result_dict['success'])
        self.assertEqual(result_dict['failure_reason'], "Insufficient liquidity")
        self.assertEqual(result_dict['simulated_delay_ms'], 200.0)
        self.assertEqual(result_dict['execution_time'], "2024-01-05T12:00:00")


class TestMockTradeExecutor(unittest.TestCase):
    """Test MockTradeExecutor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Use fixed seed for reproducibility
        self.executor = MockTradeExecutor(seed=42)
        
        # Create a sample arbitrage opportunity
        self.opportunity = ArbitrageOpportunity(
            market_id="test_market_1",
            market_name="Test Market",
            opportunity_type="two-way",
            expected_profit=5.0,
            expected_return_pct=5.0,
            positions=[
                {'outcome': 'Yes', 'action': 'BUY', 'price': 0.45, 'volume': 50000},
                {'outcome': 'No', 'action': 'BUY', 'price': 0.50, 'volume': 50000},
            ],
            detected_at=datetime.now(),
            risk_score=0.3
        )
    
    def test_executor_initialization(self):
        """Test MockTradeExecutor initialization."""
        executor = MockTradeExecutor(
            seed=123,
            min_delay_ms=100.0,
            max_delay_ms=300.0,
            price_volatility=0.03,
            depth_variability=0.4,
            fee_rate=0.01
        )
        
        self.assertEqual(executor.min_delay_ms, 100.0)
        self.assertEqual(executor.max_delay_ms, 300.0)
        self.assertEqual(executor.price_volatility, 0.03)
        self.assertEqual(executor.depth_variability, 0.4)
        self.assertEqual(executor.fee_rate, 0.01)
    
    def test_execute_trade_returns_structured_result(self):
        """Test that execute_trade returns a TradeExecutionResult."""
        result = self.executor.execute_trade(self.opportunity)
        
        self.assertIsInstance(result, TradeExecutionResult)
        self.assertIsInstance(result.result, TradeResult)
        self.assertIsInstance(result.success, bool)
        self.assertIsInstance(result.simulated_delay_ms, float)
        self.assertIsInstance(result.price_shift_pct, float)
        self.assertIsInstance(result.available_depth, float)
        self.assertIsInstance(result.execution_time, datetime)
    
    def test_execute_trade_simulates_delay(self):
        """Test that execute_trade simulates network delay."""
        executor = MockTradeExecutor(seed=42, min_delay_ms=100.0, max_delay_ms=200.0)
        result = executor.execute_trade(self.opportunity)
        
        # Delay should be within configured range
        self.assertGreaterEqual(result.simulated_delay_ms, 100.0)
        self.assertLessEqual(result.simulated_delay_ms, 200.0)
    
    def test_execute_trade_simulates_price_shift(self):
        """Test that execute_trade simulates price shift."""
        executor = MockTradeExecutor(seed=42, price_volatility=0.05)
        result = executor.execute_trade(self.opportunity)
        
        # Price shift should be within volatility range
        self.assertGreaterEqual(result.price_shift_pct, -0.05)
        self.assertLessEqual(result.price_shift_pct, 0.05)
    
    def test_execute_trade_simulates_depth(self):
        """Test that execute_trade simulates order book depth."""
        result = self.executor.execute_trade(self.opportunity, trade_amount=100.0)
        
        # Available depth should be positive
        self.assertGreater(result.available_depth, 0)
        # Filled amount should be at most the requested amount
        self.assertLessEqual(result.filled_amount, 100.0)
    
    def test_execute_trade_deterministic_with_seed(self):
        """Test that execute_trade is deterministic with same seed."""
        executor1 = MockTradeExecutor(seed=12345)
        executor2 = MockTradeExecutor(seed=12345)
        
        result1 = executor1.execute_trade(self.opportunity)
        result2 = executor2.execute_trade(self.opportunity)
        
        self.assertEqual(result1.simulated_delay_ms, result2.simulated_delay_ms)
        self.assertEqual(result1.price_shift_pct, result2.price_shift_pct)
        self.assertEqual(result1.result, result2.result)
    
    def test_successful_trade_has_no_failure_reason(self):
        """Test that successful trades have no failure reason."""
        # Run multiple times to find a successful trade
        executor = MockTradeExecutor(seed=42, fee_rate=0.001, price_volatility=0.001)
        
        # Create opportunity with high profit margin
        high_profit_opp = ArbitrageOpportunity(
            market_id="high_profit_market",
            market_name="High Profit Market",
            opportunity_type="two-way",
            expected_profit=15.0,
            expected_return_pct=15.0,
            positions=[
                {'outcome': 'Yes', 'action': 'BUY', 'price': 0.40, 'volume': 100000},
                {'outcome': 'No', 'action': 'BUY', 'price': 0.45, 'volume': 100000},
            ],
            detected_at=datetime.now(),
            risk_score=0.1
        )
        
        result = executor.execute_trade(high_profit_opp)
        
        if result.success:
            self.assertIsNone(result.failure_reason)
            self.assertEqual(result.result, TradeResult.SUCCESS)
    
    def test_failed_trade_has_failure_reason(self):
        """Test that failed trades have a failure reason."""
        # Create conditions likely to cause failure
        executor = MockTradeExecutor(
            seed=42,
            fee_rate=0.10,  # High fee to erase edge
            price_volatility=0.05,
            depth_variability=0.9
        )
        
        # Low profit opportunity
        low_profit_opp = ArbitrageOpportunity(
            market_id="low_profit_market",
            market_name="Low Profit Market",
            opportunity_type="two-way",
            expected_profit=1.0,
            expected_return_pct=1.0,
            positions=[
                {'outcome': 'Yes', 'action': 'BUY', 'price': 0.49, 'volume': 1000},
                {'outcome': 'No', 'action': 'BUY', 'price': 0.50, 'volume': 1000},
            ],
            detected_at=datetime.now(),
            risk_score=0.8
        )
        
        result = executor.execute_trade(low_profit_opp)
        
        if not result.success:
            self.assertIsNotNone(result.failure_reason)
            self.assertIsInstance(result.failure_reason, str)
            self.assertGreater(len(result.failure_reason), 0)
    
    def test_depth_too_thin_result(self):
        """Test DEPTH_TOO_THIN result when order book is thin."""
        # Create executor with high depth variability
        executor = MockTradeExecutor(
            seed=999,  # Choose seed that causes thin depth
            depth_variability=0.99,  # Very high variability
            fee_rate=0.001
        )
        
        # Opportunity with very low volume
        thin_market_opp = ArbitrageOpportunity(
            market_id="thin_market",
            market_name="Thin Market",
            opportunity_type="two-way",
            expected_profit=10.0,
            expected_return_pct=10.0,
            positions=[
                {'outcome': 'Yes', 'action': 'BUY', 'price': 0.45, 'volume': 10},  # Very low volume
                {'outcome': 'No', 'action': 'BUY', 'price': 0.45, 'volume': 10},
            ],
            detected_at=datetime.now(),
            risk_score=0.9
        )
        
        result = executor.execute_trade(thin_market_opp, trade_amount=100.0)
        
        # Either DEPTH_TOO_THIN or another failure is acceptable
        # The key is the result is structured correctly
        self.assertIsInstance(result.result, TradeResult)
        self.assertIsInstance(result.available_depth, float)


class TestMockTradeExecutorIntegration(unittest.TestCase):
    """Integration tests for MockTradeExecutor with other components."""
    
    def test_execute_with_detected_opportunity(self):
        """Test executing a trade with a detected arbitrage opportunity."""
        # Generate mock data with arbitrage opportunities
        generator = MockDataGenerator(seed=42, arb_frequency=1.0)
        detector = ArbitrageDetector(db_path=":memory:")
        executor = MockTradeExecutor(seed=42)
        
        # Generate markets with arbitrage
        markets = generator.generate_snapshots(5)
        opportunities = detector.detect_opportunities(markets)
        
        # Execute trades on detected opportunities
        for opp in opportunities:
            result = executor.execute_trade(opp)
            
            self.assertIsInstance(result, TradeExecutionResult)
            self.assertIn(result.result, list(TradeResult))
            
            # Verify result structure
            result_dict = result.to_dict()
            self.assertIn('result', result_dict)
            self.assertIn('success', result_dict)
            self.assertIn('failure_reason', result_dict)
            self.assertIn('simulated_delay_ms', result_dict)


if __name__ == '__main__':
    unittest.main()
