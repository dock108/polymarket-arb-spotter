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

The application supports flexible configuration through multiple methods:

1. **Environment Variables** (Recommended): Create a `.env` file in the project root
2. **UI Settings Page**: Use the Settings page in the dashboard
3. **Code Configuration**: Modify `app/core/config.py` directly

### Environment Variables

The application uses `python-dotenv` to load configuration from a `.env` file. To get started:

```bash
# Copy the example file
cp .env.example .env

# Edit with your settings
nano .env
```

#### Available Environment Variables

**Arbitrage Detection Parameters:**
- `MIN_PROFIT_PERCENT` - Minimum profit percentage to consider an opportunity (default: `1.0`)
- `FEE_BUFFER_PERCENT` - Fee buffer percentage to account for transaction fees (default: `0.5`)
- `MAX_STAKE` - Maximum stake per arbitrage opportunity in USD (default: `1000.0`)

**Alert Configuration:**
- `ALERT_METHOD` - Alert method: `"email"` or `"telegram"` (optional, leave empty to disable)
- `TELEGRAM_API_KEY` - Telegram bot API key (required if `ALERT_METHOD=telegram`)
- `EMAIL_SMTP_SERVER` - Email SMTP server address (required if `ALERT_METHOD=email`)
  - Example: `smtp.gmail.com:587`

**Database Configuration:**
- `LOG_DB_PATH` - Path to the arbitrage logs database (default: `data/arb_logs.sqlite`)
- `DB_PATH` - Path to the main application database (default: `data/polymarket_arb.db`)

**API Configuration:**
- `API_ENDPOINT` - Polymarket API endpoint (default: `https://api.polymarket.com`)
- `API_KEY` - Polymarket API key (optional, if required by API)

**Logging Configuration:**
- `LOG_LEVEL` - Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (default: `INFO`)
- `LOG_FILE` - Path to log file (default: `data/polymarket_arb.log`)

#### Example Configuration

```bash
# .env file example
MIN_PROFIT_PERCENT=2.0
FEE_BUFFER_PERCENT=0.75
MAX_STAKE=5000.0

ALERT_METHOD=telegram
TELEGRAM_API_KEY=your_bot_token_here

LOG_DB_PATH=data/arb_logs.sqlite
LOG_LEVEL=INFO
```

### Accessing Configuration in Code

The configuration is automatically loaded when the application starts. You can access it using the `get_config()` helper:

```python
from app.core.config import get_config

config = get_config()
print(f"Min profit: {config.min_profit_percent}%")
print(f"Alert method: {config.alert_method}")
```

### Configuration Validation

The configuration system automatically validates settings on startup and will:
- Log errors for invalid values (negative profit thresholds, etc.)
- Log warnings for incomplete alert configurations
- Display a summary of loaded configuration values
- Create required directories automatically

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

## 🥧 Running on Raspberry Pi

The Polymarket Arbitrage Spotter can run efficiently on Raspberry Pi devices, making it an excellent choice for 24/7 monitoring with low power consumption.

### Recommended Hardware

- **Raspberry Pi 4** (2GB RAM minimum, 4GB+ recommended)
- **Raspberry Pi 3 B+** (will work but slower)
- **32GB+ microSD card** (Class 10 or UHS-I)
- **Reliable power supply** (official Raspberry Pi power supply recommended)
- **Active cooling** (heatsinks or fan for continuous operation)

### Installation on Raspberry Pi

1. **Install Raspberry Pi OS Lite** (64-bit recommended for better performance):
   ```bash
   # Update system
   sudo apt update && sudo apt upgrade -y
   ```

2. **Install Python 3.8+ and dependencies**:
   ```bash
   # Install Python and pip
   sudo apt install -y python3 python3-pip python3-venv git
   
   # Install system dependencies for numpy/pandas
   sudo apt install -y libatlas-base-dev libopenblas-dev
   ```

3. **Clone and setup the application**:
   ```bash
   # Clone repository
   git clone https://github.com/dock108/polymarket-arb-spotter.git
   cd polymarket-arb-spotter
   
   # Create virtual environment
   python3 -m venv venv
   source venv/bin/activate
   
   # Install Python dependencies
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   # Create .env file with your settings
   cp .env.example .env
   nano .env
   ```

### Performance Optimization

To optimize performance on Raspberry Pi:

1. **Use lighter logging levels**:
   ```bash
   # In .env file
   LOG_LEVEL=WARNING
   ```

2. **Reduce batch sizes** in mock mode:
   ```bash
   python run_mock_speed.py --batch-size 5 --duration 30
   ```

3. **Use swap memory** if you have < 4GB RAM:
   ```bash
   # Increase swap size
   sudo dphys-swapfile swapoff
   sudo nano /etc/dphys-swapfile  # Change CONF_SWAPSIZE to 2048
   sudo dphys-swapfile setup
   sudo dphys-swapfile swapon
   ```

### Running as a Service

For 24/7 operation, set up the application as a systemd service:

1. **Create service file**:
   ```bash
   sudo nano /etc/systemd/system/polymarket-arb.service
   ```

2. **Add the following configuration**:
   ```ini
   [Unit]
   Description=Polymarket Arbitrage Spotter
   After=network.target
   
   [Service]
   Type=simple
   User=pi
   WorkingDirectory=/home/pi/polymarket-arb-spotter
   Environment="PATH=/home/pi/polymarket-arb-spotter/venv/bin"
   ExecStart=/home/pi/polymarket-arb-spotter/venv/bin/python run_mock_speed.py --duration 86400
   Restart=always
   RestartSec=10
   StandardOutput=append:/home/pi/polymarket-arb-spotter/data/service.log
   StandardError=append:/home/pi/polymarket-arb-spotter/data/service_error.log
   
   [Install]
   WantedBy=multi-user.target
   ```

3. **Enable and start the service**:
   ```bash
   # Reload systemd
   sudo systemctl daemon-reload
   
   # Enable service to start on boot
   sudo systemctl enable polymarket-arb.service
   
   # Start the service
   sudo systemctl start polymarket-arb.service
   
   # Check status
   sudo systemctl status polymarket-arb.service
   ```

4. **View logs**:
   ```bash
   # View service logs
   sudo journalctl -u polymarket-arb.service -f
   
   # View application logs
   tail -f data/polymarket_arb.log
   ```

### Monitoring and Maintenance

1. **Check service health**:
   ```bash
   # Service status
   sudo systemctl status polymarket-arb.service
   
   # CPU and memory usage
   htop
   
   # Disk space
   df -h
   ```

2. **Auto-restart on failure**:
   The systemd service configuration includes `Restart=always`, which automatically restarts the service if it fails.

3. **Log rotation** to prevent disk space issues:
   ```bash
   # Create logrotate config
   sudo nano /etc/logrotate.d/polymarket-arb
   ```
   
   Add:
   ```
   /home/pi/polymarket-arb-spotter/data/*.log {
       daily
       rotate 7
       compress
       delaycompress
       missingok
       notifempty
   }
   ```

4. **Database maintenance**:
   ```bash
   # Periodically vacuum the SQLite databases
   sqlite3 data/polymarket_arb.db "VACUUM;"
   sqlite3 data/arb_logs.sqlite "VACUUM;"
   ```

### Troubleshooting on Raspberry Pi

**Issue: Out of memory errors**
- Increase swap size (see Performance Optimization above)
- Reduce batch sizes in configuration
- Close other applications

**Issue: Slow performance**
- Ensure active cooling is working
- Check CPU throttling: `vcgencmd get_throttled`
- Reduce logging level to WARNING or ERROR

**Issue: Service won't start**
- Check logs: `sudo journalctl -u polymarket-arb.service -n 50`
- Verify Python path and virtual environment
- Ensure all dependencies are installed

**Issue: Network connectivity problems**
- Check network: `ping google.com`
- Verify firewall settings: `sudo ufw status`
- Test API connectivity: `curl https://api.polymarket.com`

### Power Management

For reliable 24/7 operation:
- Use the official Raspberry Pi power supply (5V 3A for Pi 4)
- Consider a UPS (Uninterruptible Power Supply) for critical monitoring
- Enable automatic restart after power loss in Raspberry Pi config

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