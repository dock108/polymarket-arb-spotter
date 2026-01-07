# 🎯 Polymarket Arbitrage Spotter

A Python tool for detecting arbitrage opportunities in Polymarket prediction markets. **Detection only - no trading is performed.**

## 🚀 Features

- **Real-time Detection**: Monitor Polymarket markets for arbitrage opportunities
- **Historical Replay Engine**: Test algorithms against past markets with configurable playback speeds
- **Backtest Alerts**: Dry-run simulation to evaluate detection tool performance on historical data
- **Price Alert Watcher**: Subscribe to markets and get alerted when prices cross thresholds
- **WebSocket Streaming**: Real-time price updates via WebSocket connections
- **Mock Data Simulation**: Test detection algorithms with generated data
- **Interactive Dashboard**: Streamlit-based UI for visualization
- **SQLite Storage**: Persistent storage of detected opportunities and historical ticks
- **Notification Support**: Telegram and email alerts

## 📁 Project Structure

```
polymarket-arb-spotter/
├── app/                  # Application code
│   ├── core/            # Core detection logic
│   └── ui/              # Streamlit UI components
├── tests/               # Unit tests
├── scripts/             # Example and production scripts
├── docs/                # Documentation
├── data/                # Data storage (gitignored)
├── run_live.py          # Streamlit dashboard entry point
└── run_mock_speed.py    # Speed test script
```

## 🔧 Quick Start

### Prerequisites

- Python 3.8+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/dock108/polymarket-arb-spotter.git
cd polymarket-arb-spotter

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure (optional)
cp .env.example .env
```

## 🎮 Usage

### Interactive Dashboard

```bash
streamlit run run_live.py
```

Opens a web dashboard for real-time monitoring, historical data, and system status.

### Speed Tests

```bash
python run_mock_speed.py                    # Default 60-second test
python run_mock_speed.py --duration 120     # Custom duration
```

### Price Alert Watcher

```bash
python scripts/run_price_alerts.py
```

See [docs/price_alerts_usage.md](docs/price_alerts_usage.md) for detailed usage.

### Historical Replay Engine

```bash
# Replay all historical markets instantly
python scripts/example_replay.py

# Replay at 10× speed
python scripts/example_replay.py --speed 10

# Backtest with arbitrage detection
python scripts/example_replay_with_arb_detector.py

# Run backtest simulation on all strategies
python scripts/example_backtest.py

# Backtest specific market
python scripts/example_backtest.py --market market_123
```

See [docs/replay_engine.md](docs/replay_engine.md) and [docs/backtest_alerts.md](docs/backtest_alerts.md) for detailed documentation.

## 🧪 Testing

```bash
pytest                              # Run all tests
pytest --cov=app --cov-report=html  # With coverage
```

## ⚙️ Configuration

Copy `.env.example` to `.env` and configure:

| Variable | Description | Default |
|----------|-------------|---------|
| `MIN_PROFIT_PERCENT` | Minimum profit threshold | 1.0 |
| `FEE_BUFFER_PERCENT` | Fee buffer for transaction fees | 0.5 |
| `MAX_STAKE` | Maximum stake per opportunity (USD) | 1000.0 |
| `ALERT_METHOD` | `telegram` or `email` (empty to disable) | - |
| `LOG_LEVEL` | Logging level | INFO |

See `.env.example` for all available options.

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [Replay Engine](docs/replay_engine.md) | Historical data replay and backtesting |
| [Backtest Alerts](docs/backtest_alerts.md) | Dry-run simulation for tool evaluation |
| [Notification Setup](docs/notifications.md) | Configure Telegram/email alerts |
| [Deployment Guide](docs/deployment.md) | Deploy on Raspberry Pi or servers |
| [Scripts Documentation](docs/scripts.md) | Example scripts and utilities |
| [Price Alerts](docs/price_alerts_usage.md) | Price alert watcher usage |

## 🔒 Security

- Store API keys in `.env` file (gitignored)
- Never commit sensitive data
- Detection-only tool - no trading credentials needed

## 📝 Development

```bash
black app/ tests/    # Format code
flake8 app/ tests/   # Lint code
mypy app/            # Type check
```

## ⚠️ Disclaimer

This software is for educational and research purposes only. It does not perform any trading operations. Use at your own risk.

---

**Note**: This is an alpha version under active development.