# Scripts Directory

This directory contains utility and operational scripts for the Polymarket Arbitrage Spotter.

## Available Scripts

### 🚀 run_live.py - Live Arbitrage Observer

**Purpose:** Monitor Polymarket markets in real-time for arbitrage opportunities.

**Features:**
- ✅ Connect to Polymarket API (poll or stream mode)
- ✅ Detect arbitrage opportunities using detection engine
- ✅ Send alerts via configured notification method (Telegram/Email)
- ✅ Run mock trade simulations to estimate execution success
- ✅ Log all events to SQLite database
- ✅ Display helpful console summaries and statistics
- ⛔ **NEVER TRADES** - detection and monitoring only!

**Usage:**
```bash
# Basic usage - poll mode with 30s interval
python scripts/run_live.py

# Run for 5 minutes with mock trades
python scripts/run_live.py --duration 300 --poll-interval 60

# Run in stream mode (requires WebSocket connection)
python scripts/run_live.py --mode stream

# Disable mock trade simulation
python scripts/run_live.py --no-mock-trades

# Show help
python scripts/run_live.py --help
```

**Options:**
- `--mode {stream,poll}` - Connection mode (default: poll)
- `--poll-interval SECONDS` - Polling interval for poll mode (default: 30)
- `--duration SECONDS` - Duration to run in seconds (default: run forever)
- `--max-markets N` - Maximum markets to monitor (default: 100)
- `--mock-trades` / `--no-mock-trades` - Enable/disable mock trade simulation
- `--log-level LEVEL` - Logging level (default: INFO)

**Output:**
- Console: Real-time arbitrage alerts with detailed metrics
- Database: `data/arb_logs.sqlite` - all detected opportunities
- Logs: `data/polymarket_arb.log` - operational logs

**Important Notes:**
- This is a **detection-only** system - it NEVER executes real trades
- Requires network access to Polymarket API
- Configure alerts in `.env` file (see main README.md)
- All events are logged to database for analysis

---

### 📊 run_mock_speed.py - Speed Test with Mock Data

**Purpose:** Convenience wrapper for the main `run_mock_speed.py` script at repository root.

**Usage:**
```bash
python scripts/run_mock_speed.py --duration 60
```

See main `run_mock_speed.py` for full documentation.

---

### 📧 example_notification.py - Test Notification System

**Purpose:** Test the notification system configuration.

**Usage:**
```bash
python scripts/example_notification.py
```

---

### 🎯 example_arb_with_notifications.py - Integration Example

**Purpose:** Demonstrates how to integrate arbitrage detection with notifications.

**Usage:**
```bash
python scripts/example_arb_with_notifications.py
```

---

## Configuration

All scripts use the global configuration from `.env` file. See the main README.md for configuration details.

**Key configuration variables:**
- `ALERT_METHOD` - Alert method: "telegram" or "email"
- `TELEGRAM_API_KEY` - Telegram bot API key
- `TELEGRAM_CHAT_ID` - Telegram chat ID
- `EMAIL_SMTP_SERVER` - Email SMTP server
- `MIN_PROFIT_PERCENT` - Minimum profit threshold
- `FEE_BUFFER_PERCENT` - Fee buffer for arbitrage detection
- `LOG_DB_PATH` - Database path for event logging

## Requirements

Install dependencies from the main requirements.txt:
```bash
pip install -r requirements.txt
```

## Safety Reminders

⚠️ **IMPORTANT:** All scripts in this directory are for **detection and monitoring only**.

- ⛔ **NO TRADING** - No script executes real trades
- 🔍 **OBSERVATION ONLY** - For monitoring and analysis purposes
- 💾 **DATA LOGGING** - All events are logged for review
- 🔒 **NO FINANCIAL RISK** - No real money is involved

These tools help you **identify** arbitrage opportunities, but you must make your own decisions about whether to act on them.
