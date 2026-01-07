# Wallet Event Ingestion

This document describes the wallet event ingestion system for tracking Polymarket wallet transactions.

## Overview

The wallet feed module (`app/core/wallet_feed.py`) provides functionality to:
- Fetch wallet trade events from Polymarket CLOB API
- Normalize trade data into a consistent format
- Store trades in SQLite with duplication protection
- Subscribe to real-time trade events (via polling)

## Data Schema

Trades are stored in the `wallet_trades` table with the following schema:

| Column | Type | Description |
|--------|------|-------------|
| `wallet` | string | Wallet address (maker or taker) |
| `market_id` | string | Market/token identifier |
| `side` | string | Trade side: "yes" or "no" |
| `price` | float | Trade price (0-1) |
| `size` | float | Trade size/amount |
| `timestamp` | string | ISO format timestamp |
| `tx_hash` | string | Unique transaction hash (for deduplication) |

### Indexes

The following indexes are created for efficient querying:
- `idx_tx_hash`: Unique index on `tx_hash` for duplication protection
- `idx_wallet_timestamp`: Index on `(wallet, timestamp)` for wallet queries
- `idx_market_timestamp`: Index on `(market_id, timestamp)` for market queries

## Usage

### Basic Usage

```python
from app.core.wallet_feed import WalletFeed, get_wallet_trades

# Initialize wallet feed
feed = WalletFeed()

# Fetch trades from API
trades = feed.fetch_trades(limit=100)
print(f"Fetched {len(trades)} trades")

# Store trades in database
count = feed.store_trades(trades)
print(f"Stored {count} new trades")

# Or combine fetch + store in one call
count = feed.ingest_trades(limit=100)
print(f"Ingested {count} new trades")
```

### Filtering

```python
# Fetch trades for a specific market
trades = feed.fetch_trades(market_id="0x1234...", limit=50)

# Fetch trades for a specific wallet
trades = feed.fetch_trades(wallet="0xabcd...", limit=50)

# Combine filters
trades = feed.fetch_trades(
    market_id="0x1234...",
    wallet="0xabcd...",
    limit=50
)
```

### Querying Stored Trades

```python
from app.core.wallet_feed import get_wallet_trades

# Get all trades (limit 100)
trades = get_wallet_trades(limit=100)

# Filter by wallet
trades = get_wallet_trades(wallet="0xabcd...", limit=50)

# Filter by market
trades = get_wallet_trades(market_id="0x1234...", limit=50)

# Combine filters
trades = get_wallet_trades(
    wallet="0xabcd...",
    market_id="0x1234...",
    limit=50
)
```

### Real-time Subscription

```python
from app.core.wallet_feed import WalletFeed

feed = WalletFeed()

def on_new_trade(trade):
    """Callback function for new trades."""
    print(f"New trade: {trade.wallet} - {trade.side} @ ${trade.price}")

# Subscribe to all trades (runs indefinitely)
# Run this in a separate thread or process
feed.subscribe_to_trades(
    on_trade=on_new_trade,
    poll_interval=10.0,  # Poll every 10 seconds
    auto_store=True,     # Automatically store in database
)
```

### Using in a Thread

```python
import threading
from app.core.wallet_feed import WalletFeed

feed = WalletFeed()

def on_trade(trade):
    print(f"New trade: {trade.side} @ {trade.price}")

def run_subscription():
    feed.subscribe_to_trades(
        on_trade=on_trade,
        market_id="0x1234...",  # Optional: filter by market
        poll_interval=5.0,
    )

# Start subscription in background thread
thread = threading.Thread(target=run_subscription, daemon=True)
thread.start()

# Main thread can continue doing other work
# The subscription will run in the background
```

## Configuration

The wallet feed uses the following configuration:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `clob_url` | `https://clob.polymarket.com` | Polymarket CLOB API URL |
| `db_path` | `data/wallet_trades.db` | SQLite database path |
| `max_retries` | 3 | Maximum retry attempts for failed requests |
| `retry_delay` | 1.0 | Base delay between retries (exponential backoff) |
| `timeout` | 30 | Request timeout in seconds |

### Custom Configuration

```python
from app.core.wallet_feed import WalletFeed

feed = WalletFeed(
    clob_url="https://clob.polymarket.com",
    db_path="custom/path/trades.db",
    max_retries=5,
    retry_delay=2.0,
    timeout=60,
)
```

## Features

### Retry Logic

The wallet feed implements exponential backoff retry logic:
- Retries failed requests up to `max_retries` times
- Uses exponential backoff: delay = `retry_delay * (2 ** attempt)`
- Logs warnings on retries, errors on final failure

### Duplication Protection

Duplicate trades are prevented using two mechanisms:
1. **Database unique index**: `tx_hash` field has a unique index
2. **In-memory cache**: Recently seen transaction hashes are cached for fast lookup

This ensures the same transaction is never stored twice, even across multiple ingestion runs.

### Trade Normalization

The feed normalizes trades from various API response formats:
- Handles both `maker_address` and `taker_address` fields
- Supports multiple outcome formats (0/1, "0"/"1", "yes"/"no")
- Converts timestamps from ISO strings or Unix timestamps
- Uses `transaction_hash` or `id` for transaction hash

## API Endpoints

The wallet feed uses the Polymarket CLOB API:

- **GET /trades**: Fetch historical trades
  - Query params: `asset_id`, `maker`, `limit`, `offset`

## Database Location

By default, trades are stored in:
```
data/wallet_trades.db
```

This database is separate from other application databases to keep concerns separated.

## Example Scripts

See `scripts/example_wallet_feed.py` for complete examples demonstrating:
- Fetching and storing trades
- Querying stored trades
- Real-time subscription
- Filtering and pagination

Run the example:
```bash
python scripts/example_wallet_feed.py
```

## Error Handling

The wallet feed is designed to be resilient:
- Failed API requests are retried with exponential backoff
- Database errors are logged but don't crash the application
- Invalid trade data is logged and skipped
- Callback exceptions in subscriptions are caught and logged

## Performance Considerations

- Use `store_trades()` for batch inserts (more efficient than single inserts)
- The in-memory cache reduces database lookups for duplicate detection
- Database indexes ensure efficient queries by wallet, market, and timestamp
- Polling interval should balance freshness vs. API load (recommended: 5-10 seconds)

## Limitations

- Currently uses REST API polling (not WebSocket)
- Subscription runs indefinitely (must be managed in a separate thread)
- No built-in rate limiting (relies on API limits)
- Trade normalization assumes specific API response formats

## Future Enhancements

Potential improvements for future versions:
- WebSocket support for real-time streaming
- Rate limiting and backoff strategies
- Configurable normalization rules
- Trade aggregation and analytics
- Integration with notification system
