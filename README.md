# 🎯 Polymarket Arbitrage Spotter

Polymarket Arbitrage Spotter is a Python tool that **detects** arbitrage opportunities in Polymarket prediction markets (no trading is performed).

## 🚀 Run Locally

### Prerequisites
- Python 3.8+
- pip

### Setup
```bash
git clone https://github.com/dock108/polymarket-arb-spotter.git
cd polymarket-arb-spotter

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env  # Optional configuration
```

### Start the Dashboard
```bash
streamlit run run_live.py
```

### Run a Mock Speed Test
```bash
python run_mock_speed.py --duration 120
```

## 📦 Deployment Basics

For Raspberry Pi and server deployment guidance, see the deployment guide in `/docs`.

- [Deployment Guide](docs/deployment.md)

## 📚 Documentation

Deeper documentation lives in `/docs`:
- [Wallet Feed](docs/wallet_feed.md)
- [Wallet Profiles](docs/wallet_profiles.md)
- [Replay Engine](docs/replay_engine.md)
- [Backtest Alerts](docs/backtest_alerts.md)
- [Notifications](docs/notifications.md)
- [Scripts](docs/scripts.md)
- [Price Alerts](docs/price_alerts_usage.md)

## ⚠️ Disclaimer

This software is for educational and research purposes only. It does not perform any trading operations. Use at your own risk.
