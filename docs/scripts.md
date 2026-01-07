# Scripts Documentation

This directory contains utility and operational scripts for the Polymarket Arbitrage Spotter.

## Available Scripts

### Production Scripts

#### 📡 run_live_observer.py - Live CLI Observer

**Purpose:** Command-line observer for real-time arbitrage detection.

**Usage:**
```bash
python scripts/run_live_observer.py [OPTIONS]
```

**Options:**
- `--mode {stream,poll}` - Connection mode (default: poll)
- `--poll-interval SECONDS` - Polling interval (default: 30)
- `--duration SECONDS` - Duration to run (default: run forever)
- `--max-markets N` - Maximum markets to monitor (default: 100)
- `--mock-trades` / `--no-mock-trades` - Enable/disable mock trade simulation
- `--log-level LEVEL` - Logging level (default: INFO)

**Description:**
Connects to Polymarket API and monitors markets for arbitrage opportunities. Sends alerts via configured notification method and logs all events.

---

#### 🔔 run_price_alerts.py - Price Alert Watcher

**Purpose:** Monitor markets and trigger price threshold alerts.

**Usage:**
```bash
python scripts/run_price_alerts.py [--log-level LEVEL]
```

**Description:**
Loads alerts from persistent storage and monitors markets via WebSocket. Sends notifications when price thresholds are crossed.

---

### Example Scripts

#### 📧 example_notification.py - Test Notification System

**Purpose:** Test the notification system configuration.

**Usage:**
```bash
python scripts/example_notification.py
```

**Description:**
Shows basic notification service usage and configuration status.

---

#### 🎯 example_arb_with_notifications.py - Integration Example

**Purpose:** Demonstrates how to integrate arbitrage detection with notifications.

**Usage:**
```bash
python scripts/example_arb_with_notifications.py
```

**Description:**
Shows integration with the arbitrage detector, demonstrating how to send notifications when opportunities are detected.

---

#### 📊 example_event_correlation.py - Pattern Analysis

**Purpose:** Demonstrates the event correlation analyzer for computing statistics from market patterns.

**Usage:**
```bash
python scripts/example_event_correlation.py
```

**Description:**
Shows how to use the EventCorrelationAnalyzer to compute descriptive statistics from historical market data and user labels, helping understand pattern performance and characteristics.

---

#### 🔍 example_interesting_moments.py - Interesting Moments Finder

**Purpose:** Demonstrates automated detection of timestamps worth reviewing during analysis.

**Usage:**
```bash
python scripts/example_interesting_moments.py
```

**Description:**
Shows how to use the InterestingMomentsFinder to automatically detect:
- Sudden price accelerations
- Abnormal volume clusters
- Imbalance reversals
- Repeated alert firing

This saves massive time during analysis by highlighting review candidates and prioritizing them by severity.

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
