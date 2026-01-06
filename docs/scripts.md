# Scripts Documentation

This directory contains utility and operational scripts for the Polymarket Arbitrage Spotter.

## Available Scripts

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
