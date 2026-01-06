# 🎯 Polymarket Arbitrage Spotter

A Python tool for detecting arbitrage opportunities in Polymarket prediction markets. This tool focuses on detection only - no trading is performed.

## 🚀 Features

- **Real-time Detection**: Monitor Polymarket markets for arbitrage opportunities
- **Mock Data Simulation**: Test detection algorithms with generated data
- **Interactive Dashboard**: Streamlit-based UI for visualization
- **SQLite Storage**: Persistent storage of detected opportunities
- **Performance Testing**: Speed benchmarking tools
- **Notification Support**: Telegram and email alerts

## 📁 Project Structure

```
polymarket-arb-spotter/
├── app/                  # Application code
│   ├── core/            # Core detection logic
│   └── ui/              # Streamlit UI components
├── tests/               # Unit tests
├── scripts/             # Example scripts
├── docs/                # Documentation
├── data/                # Data storage (gitignored)
├── run_live.py          # Streamlit dashboard entry point
└── run_mock_speed.py    # Speed test script
```

## 🔧 Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Setup

1. Clone the repository:
```bash
git clone https://github.com/dock108/polymarket-arb-spotter.git
cd polymarket-arb-spotter
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables (optional):
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your preferred settings
nano .env  # or use your favorite editor
```

See the [Configuration](#️-configuration) section below for details on all available environment variables.

## 🎮 Usage

### Running the Live Dashboard

Start the Streamlit dashboard for real-time monitoring:

```bash
streamlit run run_live.py
```

This will open a web browser with the interactive dashboard where you can:
- Monitor detected arbitrage opportunities
- View historical data
- Configure detection parameters
- Track system status

### Running Speed Tests

Test the detection performance with mock data:

```bash
# Run a 60-second speed test
python run_mock_speed.py

# Run with custom duration
python run_mock_speed.py --duration 120

# Run batch mode with specific number of markets
python run_mock_speed.py --mode batch --num-markets 10000 --batch-size 100
```

Options:
- `--duration SECONDS`: Duration for speed test mode (default: 60)
- `--mode {speed|batch}`: Test mode (default: speed)
- `--batch-size N`: Markets per batch (default: 10)
- `--num-markets N`: Total markets for batch mode (default: 1000)
- `--log-level LEVEL`: Logging level (default: INFO)
- `--seed N`: Random seed for reproducibility (default: 42)

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_arb_detector.py
```

## ⚙️ Configuration

The application uses environment variables for configuration. Create a `.env` file:

```bash
cp .env.example .env
nano .env  # Edit with your settings
```

### Key Configuration Options

**Detection Parameters:**
- `MIN_PROFIT_PERCENT` - Minimum profit threshold (default: 1.0)
- `FEE_BUFFER_PERCENT` - Fee buffer for transaction fees (default: 0.5)
- `MAX_STAKE` - Maximum stake per opportunity in USD (default: 1000.0)

**Alerts:**
- `ALERT_METHOD` - `"telegram"` or `"email"` (leave empty to disable)
- `TELEGRAM_API_KEY` - Telegram bot token
- `TELEGRAM_CHAT_ID` - Telegram chat ID
- `EMAIL_SMTP_SERVER` - SMTP server for email alerts

**Database & Logging:**
- `LOG_DB_PATH` - Path to logs database (default: `data/arb_logs.sqlite`)
- `LOG_LEVEL` - Logging level (default: INFO)

See [docs/notifications.md](docs/notifications.md) for detailed notification setup.

## 📚 Documentation

- [Notification Setup](docs/notifications.md) - Configure Telegram/email alerts
- [Deployment Guide](docs/deployment.md) - Deploy on Raspberry Pi or servers
- [Scripts Documentation](docs/scripts.md) - Example scripts and utilities

## 🔒 Security Notes

- Store API keys in `.env` file (gitignored)
- Never commit sensitive data
- This tool is detection-only - no trading credentials needed

## 📝 Development

### Code Style

The project uses:
- **Black** for code formatting
- **Flake8** for linting
- **MyPy** for type checking

```bash
# Format code
black app/ tests/

# Lint code
flake8 app/ tests/

# Type check
mypy app/
```

## 📄 License

TODO: Add license information

## 🤝 Contributing

Contributions are welcome! Please submit a Pull Request.

## ⚠️ Disclaimer

This software is for educational and research purposes only. It does not perform any trading operations. Use at your own risk.

---

**Note**: This is an alpha version under active development.