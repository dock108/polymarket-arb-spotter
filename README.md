# 🎯 Polymarket Arbitrage Spotter

Polymarket Arbitrage Spotter is a Python tool + Streamlit dashboard to **detect** potential arbitrage opportunities and related signals in Polymarket prediction markets.

**Note: No trading is performed. This is a read-only monitoring and analysis tool.**

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip

### Setup
```bash
git clone https://github.com/dock108/polymarket-arb-spotter.git
cd polymarket-arb-spotter

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment (optional)
cp .env.example .env
```

### Run the Dashboard
```bash
streamlit run run_live.py
```

### Run Mock Speed Test
```bash
python run_mock_speed.py --duration 120
```

## 📚 Documentation

Deeper documentation lives in the `/docs` directory:

- [Agents & AI Guidance](docs/AGENTS.md) - Context for AI coding assistants
- [Deployment Guide](docs/deployment.md) - guidance for Raspberry Pi and server deployment
- [Feature: Replay Engine](docs/replay_engine.md) - Analyze historical market behavior
- [Feature: Price Alerts](docs/price_alerts_usage.md) - Configure price-based notifications
- [Feature: Notifications](docs/notifications.md) - Outbound alert delivery (Telegram/Email)
- [Feature: Wallet Feed](docs/wallet_feed.md) - Monitor whale and fresh wallet activity
- [Scripts & Entrypoints](docs/scripts.md) - Overview of available CLI tools

## 🛠️ Architecture

- `app/core/` — Domain logic, API clients, detection algorithms, and storage.
- `app/ui/` — Streamlit presentation layer (read-only).
- `scripts/` — Example scripts and standalone entrypoints.
- `data/` — Local SQLite databases and JSON configuration files.

## ⚠️ Disclaimer

This software is for educational and research purposes only. It does not perform any trading operations. Use at your own risk.
