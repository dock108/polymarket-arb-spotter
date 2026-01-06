# Deployment Guide

## Running on Raspberry Pi

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
