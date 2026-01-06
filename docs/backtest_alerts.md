# Backtest Alerts - Dry-Run Simulation

## Overview

The backtest alerts feature allows you to simulate how your detection tools (arbitrage detector, price alerts, and depth scanner) would have performed on historical data. This helps you evaluate whether your tools were early, late, or wrong in detecting opportunities.

## Features

- **Multiple Strategy Support**: Test arbitrage detection, price alerts, and depth scanning simultaneously
- **Historical Replay**: Pipe historical ticks through detection algorithms
- **Result Tracking**: Store simulation outcomes in the `backtest_results` table
- **Performance Metrics**: Track statistics across strategies and markets
- **Flexible Filtering**: Query results by strategy, market, time range, and more

## Database Schema

The backtest results are stored in the `backtest_results` table:

```sql
CREATE TABLE backtest_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy TEXT,              -- "arb_detector", "price_alert", or "depth_scanner"
    market_id TEXT,             -- Market identifier
    timestamp TEXT,             -- ISO format timestamp
    signal TEXT,                -- JSON-encoded signal details
    simulated_outcome TEXT,     -- "would_trigger", "early", "late", "wrong"
    notes TEXT                  -- Human-readable description
);
```

## Usage

### Basic Example

```python
from app.core.replay import create_backtest_engine
from app.core.arb_detector import ArbitrageDetector

# Initialize backtest engine
engine = create_backtest_engine()

# Configure arbitrage detector
detector = ArbitrageDetector()
engine.set_arb_detector(detector)

# Run backtest
results = engine.run_backtest()

# View statistics
print(f"Ticks processed: {results['ticks_processed']}")
print(f"Arbitrage signals: {results['arb_signals']}")
print(f"Markets analyzed: {results['markets_analyzed']}")
```

### Adding Price Alerts

```python
# Add price alerts for specific markets
engine.add_price_alert("market_123", "above", 0.70)
engine.add_price_alert("market_123", "below", 0.30)
engine.add_price_alert("market_456", "above", 0.65)

# Run backtest
results = engine.run_backtest()
print(f"Price alerts triggered: {results['price_alerts_triggered']}")
```

### Configuring Depth Scanner

```python
# Configure depth scanner thresholds
depth_config = {
    "min_depth": 500.0,          # Minimum liquidity threshold
    "max_gap": 0.10,             # Maximum acceptable bid-ask spread
    "imbalance_ratio": 300.0,    # Maximum depth imbalance
}
engine.set_depth_config(depth_config)

# Run backtest
results = engine.run_backtest()
print(f"Depth signals: {results['depth_signals']}")
```

### Testing Specific Markets

```python
# Backtest specific markets only
results = engine.run_backtest(
    market_ids=["market_123", "market_456"],
    limit_per_market=1000
)
```

### Time Range Filtering

```python
from datetime import datetime, timedelta

# Backtest a specific time period
start_time = datetime(2024, 1, 1)
end_time = start_time + timedelta(days=7)

results = engine.run_backtest(
    start=start_time,
    end=end_time
)
```

## Querying Results

After running a backtest, you can query the stored results:

```python
from app.core.history_store import get_backtest_results

# Get all arbitrage detector results
arb_results = get_backtest_results(strategy="arb_detector", limit=100)

# Get results for a specific market
market_results = get_backtest_results(market_id="market_123")

# Get results within a time range
time_filtered = get_backtest_results(
    start=datetime(2024, 1, 1),
    end=datetime(2024, 1, 7)
)

# Process results
for result in arb_results:
    print(f"Market: {result['market_id']}")
    print(f"Time: {result['timestamp']}")
    print(f"Outcome: {result['simulated_outcome']}")
    print(f"Signal: {result['signal']}")
    print(f"Notes: {result['notes']}")
    print()
```

## Command-Line Example

The included example script provides a complete demonstration:

```bash
# Backtest all markets with all strategies
python scripts/example_backtest.py

# Backtest specific market
python scripts/example_backtest.py --market market_123

# Use custom database path
python scripts/example_backtest.py --db-path data/my_history.db

# Limit ticks per market
python scripts/example_backtest.py --limit 500
```

## Signal Data Structure

### Arbitrage Detector Signals

```python
{
    "opportunity_type": "two-way",
    "expected_profit": 10.00,        # Per $100 invested
    "expected_return_pct": 11.11,    # Percentage return
    "yes_price": 0.45,
    "no_price": 0.45,
    "price_sum": 0.90
}
```

### Price Alert Signals

```python
{
    "direction": "above",
    "target_price": 0.70,
    "current_price": 0.72,
    "alert_type": "price_alert"
}
```

### Depth Scanner Signals

```python
{
    "signal_type": "thin_depth",
    "metrics": {
        "total_depth": 250.0,
        "threshold": 500.0,
        "total_yes_depth": 125.0,
        "total_no_depth": 125.0
    },
    "reason": "Thin orderbook depth: 250.00 < 500.00"
}
```

## Simulated Outcomes

The `simulated_outcome` field indicates how the tool performed:

- **`would_trigger`**: Signal was generated (most common for initial implementation)
- **`early`**: Tool signaled before optimal entry (future enhancement)
- **`late`**: Tool signaled after opportunity passed (future enhancement)
- **`wrong`**: Signal was a false positive (future enhancement)

## Performance Evaluation

Use the backtest results to evaluate your tools:

```python
from app.core.history_store import get_backtest_results

# Count signals by strategy
strategies = ["arb_detector", "price_alert", "depth_scanner"]
for strategy in strategies:
    results = get_backtest_results(strategy=strategy)
    print(f"{strategy}: {len(results)} signals")

# Analyze arbitrage opportunities
arb_results = get_backtest_results(strategy="arb_detector")
if arb_results:
    profits = [r['signal'].get('expected_profit', 0) for r in arb_results]
    returns = [r['signal'].get('expected_return_pct', 0) for r in arb_results]
    
    print(f"Total opportunities: {len(arb_results)}")
    print(f"Average profit: ${sum(profits) / len(profits):.2f}")
    print(f"Average return: {sum(returns) / len(returns):.2f}%")
    print(f"Best return: {max(returns):.2f}%")
```

## Integration with Live System

The backtest engine uses the same detection modules as the live system, ensuring consistency:

```python
# Same detector used for both backtesting and live trading
from app.core.arb_detector import ArbitrageDetector

detector = ArbitrageDetector()

# Use for backtesting
backtest_engine = create_backtest_engine()
backtest_engine.set_arb_detector(detector)
backtest_results = backtest_engine.run_backtest()

# Use for live trading (hypothetical)
# live_engine.set_detector(detector)
```

## Best Practices

1. **Start with Jump Speed**: Use `PlaybackSpeed.JUMP_TO_EVENTS` for fast initial testing
2. **Test Representative Data**: Ensure your historical data covers various market conditions
3. **Validate Results**: Cross-check backtest signals against known market events
4. **Iterate on Thresholds**: Use backtest results to tune detection parameters
5. **Regular Testing**: Backtest periodically as you collect new historical data

## Limitations

- Current implementation focuses on "would_trigger" outcomes
- Depth scanner requires orderbook data in tick depth_summary
- Price alerts only check yes_price by default
- Backtest speed depends on database size and strategy complexity

## Future Enhancements

Potential improvements to the backtest system:

- **Outcome Classification**: Implement "early", "late", and "wrong" detection
- **Performance Metrics**: Add precision, recall, and timing analysis
- **Comparison Mode**: Compare multiple strategy configurations
- **Visualization**: Generate charts of signal performance over time
- **Replay Integration**: Real-time visualization of backtest as it runs
