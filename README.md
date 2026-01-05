# 🎯 Polymarket Arbitrage Spotter

A Python monorepo for detecting arbitrage opportunities in Polymarket prediction markets. This tool focuses on detection only - no trading is performed.

## 🚀 Features

- **Real-time Detection**: Monitor Polymarket markets for arbitrage opportunities
- **Mock Data Simulation**: Test detection algorithms with generated data
- **Interactive Dashboard**: Streamlit-based UI for visualization
- **SQLite Storage**: Persistent storage of detected opportunities
- **Performance Testing**: Speed benchmarking tools
- **Comprehensive Logging**: Track all detection activity

## 📁 Project Structure

```
polymarket-arb-spotter/
├── app/
│   ├── core/              # Core arbitrage detection logic
│   │   ├── config.py      # Configuration management
│   │   ├── logger.py      # Logging utilities
│   │   ├── arb_detector.py # Main detection engine
│   │   ├── mock_data.py   # Mock data generator
│   │   ├── simulator.py   # Simulation engine
│   │   └── api_client.py  # Polymarket API client
│   └── ui/                # Streamlit UI components
│       ├── dashboard.py   # Main dashboard
│       ├── history_view.py # Historical opportunities
│       └── settings_view.py # Configuration UI
├── tests/                 # Unit tests
│   ├── test_config.py
│   ├── test_arb_detector.py
│   ├── test_mock_data.py
│   └── test_simulator.py
├── scripts/               # Utility scripts (empty, reserved for future)
├── data/                  # Data storage (gitignored)
├── run_live.py           # Main application entry point
├── run_mock_speed.py     # Speed test script
├── requirements.txt      # Python dependencies
├── .gitignore           # Git ignore rules
└── README.md            # This file
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

Configuration can be managed through:

1. **UI Settings Page**: Use the Settings page in the dashboard
2. **Environment Variables**: Set environment variables for configuration
3. **Code Configuration**: Modify `app/core/config.py`

Key configuration options:
- `api_endpoint`: Polymarket API endpoint
- `api_key`: API key (if required)
- `db_path`: SQLite database location
- `min_profit_threshold`: Minimum profit to consider (default: 1%)
- `max_stake`: Maximum stake per opportunity
- `log_level`: Logging verbosity

## 📊 Database Schema

The application uses SQLite for storing detected opportunities:

```sql
CREATE TABLE opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL,
    market_name TEXT,
    opportunity_type TEXT,
    expected_profit REAL,
    expected_return_pct REAL,
    detected_at TIMESTAMP,
    risk_score REAL
);
```

Data is stored in `data/polymarket_arb.db` by default.

## 🚧 TODO & Roadmap

### High Priority
- [ ] Implement actual Polymarket API integration
- [ ] Complete arbitrage detection algorithms
- [ ] Add two-way arbitrage detection
- [ ] Add triangular arbitrage detection
- [ ] Implement real-time monitoring via WebSocket
- [ ] Add comprehensive test coverage

### Medium Priority
- [ ] Add notification system (email, telegram, discord)
- [ ] Implement risk scoring algorithm
- [ ] Add profit calculation with fees
- [ ] Create backtesting framework
- [ ] Add performance metrics and analytics
- [ ] Implement configuration persistence

### Low Priority
- [ ] Add authentication for dashboard
- [ ] Create REST API for external access
- [ ] Add Docker containerization
- [ ] Implement distributed monitoring
- [ ] Add machine learning for opportunity prediction
- [ ] Create mobile app interface

## 🔒 Security Notes

- API keys and secrets should be stored in environment variables or `.env` file (gitignored)
- Never commit sensitive data to the repository
- The `.gitignore` file excludes database files and logs
- This tool is for detection only - no trading credentials are handled

## 📝 Development

### Code Style

The project uses:
- **Black** for code formatting
- **Flake8** for linting
- **MyPy** for type checking

Run code quality tools:
```bash
# Format code
black app/ tests/

# Lint code
flake8 app/ tests/

# Type check
mypy app/
```

### Adding New Features

1. Create feature branch
2. Implement changes with tests
3. Ensure all tests pass
4. Update documentation
5. Submit pull request

## 📄 License

TODO: Add license information

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## ⚠️ Disclaimer

This software is for educational and research purposes only. It does not perform any trading operations. Use of this software for actual trading is at your own risk. Always do your own research and consult with financial advisors before making investment decisions.

## 📧 Contact

For questions or support, please open an issue on GitHub.

---

**Note**: This is an alpha version under active development. Many features are planned but not yet implemented. Check the TODO section for current status.