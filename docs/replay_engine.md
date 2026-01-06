# Historical Replay Engine

The Historical Replay Engine allows you to replay historical market tick data at configurable speeds, emitting ticks as if they were live WebSocket data. This enables safe testing and backtesting of all existing modules against past markets.

## Features

- **Load historical ticks**: Retrieves tick data from the history store database
- **Multiple playback speeds**:
  - `1×` (real-time): Replays with original timing between ticks
  - `10×` (10× speed): Replays 10 times faster than real-time
  - `jump-to-events` (instant): No delays between ticks, maximum throughput
  - Custom speeds: Any positive float multiplier (e.g., `5.0` for 5× speed)
- **Event emission**: Emits ticks via callbacks as if they were live WebSocket data
- **Time range filtering**: Replay specific time periods
- **Market selection**: Replay single or multiple markets
- **Playback controls**: Pause, resume, and stop functionality

## Purpose

The replay engine enables you to:
- **Test detection algorithms** against historical data without risk
- **Backtest strategies** to validate performance
- **Debug issues** by reproducing exact market conditions
- **Develop new features** using real market data
- **Benchmark performance** with realistic data loads

## Quick Start

### Basic Usage

```python
from app.core.replay import HistoricalReplayEngine, PlaybackSpeed

# Create replay engine with instant playback
engine = HistoricalReplayEngine(speed=PlaybackSpeed.JUMP_TO_EVENTS)

# Define callback to process ticks
def process_tick(tick):
    print(f"Market: {tick['market_id']}, Yes: {tick['yes_price']}")

# Replay a specific market
count = engine.replay_market("market_123", on_tick=process_tick)
print(f"Replayed {count} ticks")
```

### Replay All Markets

```python
# Replay all markets in the database
results = engine.replay_all_markets(on_tick=process_tick)
print(f"Replayed {sum(results.values())} total ticks from {len(results)} markets")
```

### Different Playback Speeds

```python
# Real-time playback (1× speed)
engine = HistoricalReplayEngine(speed=PlaybackSpeed.REAL_TIME)

# 10× speed
engine = HistoricalReplayEngine(speed=PlaybackSpeed.FAST_10X)

# Custom speed (5× faster)
engine = HistoricalReplayEngine(speed=5.0)

# Jump to events (instant, no delays)
engine = HistoricalReplayEngine(speed=PlaybackSpeed.JUMP_TO_EVENTS)
```

### Time Range Filtering

```python
from datetime import datetime

# Replay specific time range
start = datetime(2024, 1, 1, 0, 0, 0)
end = datetime(2024, 1, 31, 23, 59, 59)

count = engine.replay_market(
    market_id="market_123",
    start=start,
    end=end,
    on_tick=process_tick
)
```

## API Reference

### HistoricalReplayEngine

Main class for replaying historical market data.

#### Constructor

```python
HistoricalReplayEngine(
    db_path: str = "data/market_history.db",
    speed: Union[PlaybackSpeed, float] = PlaybackSpeed.REAL_TIME
)
```

**Parameters:**
- `db_path`: Path to the history database file
- `speed`: Playback speed (PlaybackSpeed enum or float multiplier)

#### Methods

##### replay_market()

Replay historical ticks for a single market.

```python
replay_market(
    market_id: str,
    start: Optional[Union[datetime, str]] = None,
    end: Optional[Union[datetime, str]] = None,
    on_tick: Optional[Callable[[Dict[str, Any]], None]] = None,
    limit: int = 10000,
) -> int
```

**Parameters:**
- `market_id`: Market ID to replay
- `start`: Start timestamp (optional)
- `end`: End timestamp (optional)
- `on_tick`: Callback function for each tick
- `limit`: Maximum number of ticks to replay

**Returns:** Number of ticks replayed

##### replay_markets()

Replay multiple markets sequentially.

```python
replay_markets(
    market_ids: List[str],
    start: Optional[Union[datetime, str]] = None,
    end: Optional[Union[datetime, str]] = None,
    on_tick: Optional[Callable[[Dict[str, Any]], None]] = None,
    limit_per_market: int = 10000,
) -> Dict[str, int]
```

**Returns:** Dictionary mapping market_id to tick count

##### replay_all_markets()

Replay all available markets in the database.

```python
replay_all_markets(
    start: Optional[Union[datetime, str]] = None,
    end: Optional[Union[datetime, str]] = None,
    on_tick: Optional[Callable[[Dict[str, Any]], None]] = None,
    limit_per_market: int = 10000,
) -> Dict[str, int]
```

**Returns:** Dictionary mapping market_id to tick count

##### get_available_markets()

Get list of markets with historical data.

```python
get_available_markets() -> List[str]
```

**Returns:** List of market IDs

##### set_speed()

Change playback speed during runtime.

```python
set_speed(speed: Union[PlaybackSpeed, float]) -> None
```

##### stop(), pause(), resume()

Control playback.

```python
stop() -> None      # Stop replay completely
pause() -> None     # Pause replay
resume() -> None    # Resume paused replay
```

##### is_playing(), is_paused()

Check playback status.

```python
is_playing() -> bool   # True if currently replaying
is_paused() -> bool    # True if paused
```

## Example Scripts

### Basic Replay

Run the basic example to replay all markets:

```bash
python scripts/example_replay.py
```

Options:
```bash
# Replay at 10× speed
python scripts/example_replay.py --speed 10

# Replay specific market
python scripts/example_replay.py --market market_123

# Custom database
python scripts/example_replay.py --db-path /path/to/history.db

# Limit ticks per market
python scripts/example_replay.py --limit 100
```

### Replay with Arbitrage Detection

Run replay with arbitrage detection for backtesting:

```bash
python scripts/example_replay_with_arb_detector.py
```

This demonstrates:
- Loading historical data
- Processing ticks through arbitrage detector
- Finding opportunities in historical data
- Performance metrics and statistics

## Integration Examples

### With Arbitrage Detector

```python
from app.core.replay import HistoricalReplayEngine, PlaybackSpeed
from app.core.arb_detector import ArbitrageDetector

detector = ArbitrageDetector()
engine = HistoricalReplayEngine(speed=PlaybackSpeed.JUMP_TO_EVENTS)

opportunities = []

def check_for_arbitrage(tick):
    # Convert tick to market snapshot
    snapshot = {
        "id": tick["market_id"],
        "outcomes": [
            {"name": "Yes", "price": tick["yes_price"]},
            {"name": "No", "price": tick["no_price"]},
        ],
    }
    
    # Detect opportunities
    opps = detector.detect_opportunities([snapshot])
    opportunities.extend(opps)

# Run replay
engine.replay_all_markets(on_tick=check_for_arbitrage)
print(f"Found {len(opportunities)} arbitrage opportunities")
```

### With Custom Analysis

```python
from collections import defaultdict

# Track price movements
price_data = defaultdict(list)

def track_prices(tick):
    price_data[tick['market_id']].append({
        'timestamp': tick['timestamp'],
        'yes_price': tick['yes_price'],
        'no_price': tick['no_price'],
    })

engine.replay_all_markets(on_tick=track_prices)

# Analyze price volatility
for market_id, prices in price_data.items():
    yes_prices = [p['yes_price'] for p in prices]
    volatility = max(yes_prices) - min(yes_prices)
    print(f"{market_id}: volatility = {volatility:.4f}")
```

## Tick Data Format

Each tick passed to the callback contains:

```python
{
    "id": 123,                              # Database ID
    "market_id": "market_123",              # Market identifier
    "timestamp": "2024-01-05T12:00:00",     # ISO format timestamp
    "yes_price": 0.65,                      # Yes outcome price (0-1)
    "no_price": 0.35,                       # No outcome price (0-1)
    "volume": 1000.0,                       # Trading volume
    "depth_summary": {                      # Optional order book depth
        "bid_depth": 500,
        "ask_depth": 600
    }
}
```

## Performance Considerations

### Speed Selection

- **jump-to-events**: Best for backtesting and analysis where timing doesn't matter
- **10× speed**: Good balance for testing with some realistic timing
- **1× speed**: Use when testing time-sensitive logic that needs real-world timing

### Memory Usage

The replay engine loads ticks in batches (default: 10,000 per market) to manage memory:

```python
# Limit ticks for large datasets
engine.replay_market("market_123", limit=1000)  # Only load 1000 ticks
```

### Database Location

For best performance, use a local database. The default location is:
```
data/market_history.db
```

## Recording Historical Data

To collect data for replay, enable history recording in your configuration:

```python
# In .env file
ENABLE_HISTORY=true
HISTORY_SAMPLING_MS=1000  # Record every 1 second
```

Or use the history recorder programmatically:

```python
from app.core.history_recorder import start_history_recorder

recorder = start_history_recorder()
# ... your code runs and records data ...
recorder.stop()
```

## Troubleshooting

### No Historical Data Found

If you see "No historical data found in database":

1. Check database path is correct
2. Ensure history recording was enabled when data was collected
3. Verify database file exists and has data:
   ```bash
   python -c "from app.core.history_store import get_market_ids; print(get_market_ids())"
   ```

### Playback Too Slow

If real-time or 10× playback is too slow:

1. Use `PlaybackSpeed.JUMP_TO_EVENTS` for instant playback
2. Reduce the number of ticks with `limit` parameter
3. Filter to specific markets or time ranges

### Memory Issues

If replaying large datasets causes memory issues:

1. Reduce `limit` parameter to load fewer ticks per market
2. Replay markets one at a time instead of all at once
3. Use time range filters to reduce data volume

## Testing

Run the replay engine tests:

```bash
pytest tests/test_replay.py -v
```

All 35 tests should pass, covering:
- Initialization and configuration
- Playback at different speeds
- Time range filtering
- Multi-market replay
- Control functions (stop, pause, resume)
- Error handling
- Integration scenarios

## See Also

- History Store (source: `app/core/history_store.py`) - Data storage backend
- History Recorder (source: `app/core/history_recorder.py`) - Data collection
- Arbitrage Detector (source: `app/core/arb_detector.py`) - Detection algorithm
- Simulator (source: `app/core/simulator.py`) - Mock data generation for testing
