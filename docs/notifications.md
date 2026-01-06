# Notification Service Documentation

## Overview

The notification service allows the Polymarket Arbitrage Spotter to send alerts when arbitrage opportunities are detected. It supports two notification methods:

1. **Telegram Bot** (Preferred) - Fast, reliable, mobile-friendly notifications
2. **Email via SMTP** (Optional) - Traditional email notifications

## Features

- ✅ Multiple notification channels (Telegram, Email)
- ✅ Graceful handling of missing credentials (logs instead of crashes)
- ✅ Throttling to prevent notification spam
- ✅ Per-market throttling (allows different markets to notify independently)
- ✅ Rich notification formatting
- ✅ Easy integration with arbitrage detector

## Configuration

### Environment Variables

Create a `.env` file in the project root or set the following environment variables:

#### Telegram Configuration

```bash
ALERT_METHOD=telegram
TELEGRAM_API_KEY=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
NOTIFICATION_THROTTLE_SECONDS=300  # 5 minutes
```

**Getting Telegram Credentials:**

1. **Create a bot:**
   - Open Telegram and search for `@BotFather`
   - Send `/newbot` and follow instructions
   - Copy the API token provided

2. **Get your chat ID:**
   - Send a message to your bot
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find the `"chat":{"id":123456789}` value

#### Email Configuration

```bash
ALERT_METHOD=email
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_FROM=your_email@gmail.com
EMAIL_TO=recipient@example.com
NOTIFICATION_THROTTLE_SECONDS=300  # 5 minutes
```

**Gmail Setup:**

1. Enable 2-factor authentication on your Google account
2. Generate an App Password (Settings → Security → App Passwords)
3. Use the App Password as `EMAIL_PASSWORD`

## Usage

### Basic Usage

```python
from app.core.notifications import send_alert
from datetime import datetime

# Create alert data
alert = {
    'market_id': 'market_123',
    'market_name': 'Will Bitcoin hit $100k by end of 2024?',
    'expected_profit_pct': 2.5,
    'prices': {
        'yes_price': 0.48,
        'no_price': 0.50
    },
    'sum_price': 0.98,
    'timestamp': datetime.now().isoformat()
}

# Send notification
success = send_alert(alert)
```

### Integration with Arbitrage Detector

```python
from app.core.arb_detector import ArbitrageDetector
from app.core.notifications import send_alert

# Initialize detector
detector = ArbitrageDetector()

# Check market for arbitrage
alert = detector.check_arbitrage(market_data)

# Send notification if profitable
if alert.profitable:
    # Add market_id for throttling
    notification_data = alert.metrics.copy()
    notification_data['market_id'] = market_data['id']
    
    # Send alert
    if send_alert(notification_data):
        print("Alert sent successfully!")
```

### Using the NotificationService Class

```python
from app.core.notifications import NotificationService
from app.core.config import Config

# Create custom config
config = Config(
    alert_method="telegram",
    telegram_api_key="your_key",
    telegram_chat_id="your_chat_id",
    notification_throttle_seconds=300
)

# Initialize service
service = NotificationService(config)

# Send alert
success = service.send_alert(alert_data)
```

## Alert Data Format

The `send_alert()` function expects a dictionary with the following keys:

### Required Fields
- `market_name` (str): Name of the market
- `expected_profit_pct` (float): Expected profit percentage
- `prices` (dict): Dictionary with `yes_price` and `no_price`
- `sum_price` (float): Sum of outcome prices
- `timestamp` (str): ISO format timestamp

### Optional Fields
- `market_id` (str): Market identifier (for throttling)
- `threshold` (float): Arbitrage threshold used
- `profit_margin` (float): Raw profit margin

## Throttling

The notification service includes built-in throttling to prevent spam:

- **Per-Market Throttling**: Each market is throttled independently
- **Configurable Window**: Default is 5 minutes (300 seconds)
- **Automatic Management**: No manual throttle management needed

Example:
```python
# Market 1 sends notification
send_alert({'market_id': 'market_1', ...})  # ✓ Sent

# Immediate retry for same market
send_alert({'market_id': 'market_1', ...})  # ✗ Throttled

# Different market is not affected
send_alert({'market_id': 'market_2', ...})  # ✓ Sent
```

## Error Handling

The notification service handles errors gracefully:

### Missing Credentials
```python
# If credentials are missing, logs warning and returns False
success = send_alert(alert)  # Returns False
# Logs: "Telegram API key not configured, cannot send notification"
```

### Network Errors
```python
# Network errors are caught and logged
success = send_alert(alert)  # Returns False
# Logs: "Failed to send Telegram notification: Connection timeout"
```

### SMTP Errors
```python
# SMTP errors are caught and logged
success = send_alert(alert)  # Returns False
# Logs: "SMTP error sending email notification: Authentication failed"
```

## Testing

Run the notification tests:

```bash
# Run all notification tests
pytest tests/test_notifications.py -v

# Run specific test
pytest tests/test_notifications.py::TestNotificationService::test_send_telegram_success -v
```

## Example Scripts

Two example scripts are provided:

### Basic Example
```bash
python scripts/example_notification.py
```

Shows basic notification service usage and configuration status.

### Integration Example
```bash
python scripts/example_arb_with_notifications.py
```

Demonstrates integration with the arbitrage detector, showing how to send notifications when opportunities are detected.

## Notification Format

### Telegram Message
```
🚨 Arbitrage Opportunity Detected!

Market: Will Bitcoin hit $100k by end of 2024?
Expected Profit: 2.50%

Prices:
- Yes: $0.4800
- No: $0.5000
- Sum: $0.9800

Timestamp: 2024-01-06T12:30:45.123456

This is an automated alert from Polymarket Arbitrage Spotter.
```

### Email
**Subject:** `🚨 Arbitrage Alert: Will Bitcoin hit $100k by end of 2024? (2.50% profit)`

**Body:** Same format as Telegram message

## Security Considerations

- 🔒 All credentials are stored in environment variables (never in code)
- 🔒 Email uses STARTTLS for secure connections
- 🔒 Telegram uses HTTPS API
- 🔒 No credentials are logged or exposed in error messages
- 🔒 `.env` file is in `.gitignore` (credentials never committed)

## Troubleshooting

### Notifications Not Sending

1. **Check configuration:**
   ```python
   from app.core.config import get_config
   config = get_config()
   print(f"Alert method: {config.alert_method}")
   print(f"Telegram configured: {bool(config.telegram_api_key and config.telegram_chat_id)}")
   print(f"Email configured: {bool(config.email_smtp_server and config.email_username)}")
   ```

2. **Check logs:**
   ```bash
   # Look for warning messages in logs
   tail -f data/polymarket_arb.log
   ```

3. **Test manually:**
   ```bash
   python scripts/example_notification.py
   ```

### Telegram Not Working

- Verify bot token is correct
- Verify chat ID is correct
- Check that you've started a conversation with the bot
- Test the API manually:
  ```bash
  curl "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"
  ```

### Email Not Working

- Verify SMTP server and port
- Check username and password
- For Gmail, ensure App Password is used (not account password)
- Check firewall/network allows SMTP connections
- Test SMTP connection:
  ```python
  import smtplib
  server = smtplib.SMTP('smtp.gmail.com', 587)
  server.starttls()
  server.login('your_email@gmail.com', 'your_app_password')
  server.quit()
  ```

## API Reference

### `send_alert(alert_object: Dict[str, Any]) -> bool`

Send a notification alert.

**Parameters:**
- `alert_object`: Dictionary containing alert information

**Returns:**
- `True` if notification sent successfully
- `False` if notification failed or was throttled

### `get_notification_service() -> NotificationService`

Get or create the global notification service instance.

**Returns:**
- `NotificationService` instance

### `NotificationService(config=None)`

Create a notification service instance.

**Parameters:**
- `config`: Optional Config object. If not provided, uses global config.

**Methods:**
- `send_alert(alert_object)`: Send a notification alert
- `_send_telegram(message)`: Internal method for Telegram
- `_send_email(subject, body)`: Internal method for Email

## Performance Notes

- Telegram notifications are typically faster (< 1 second)
- Email notifications may take 2-5 seconds depending on SMTP server
- Throttling is checked in-memory (no database queries)
- Network errors have a 10-second timeout

## Future Enhancements

Potential improvements for future versions:

- [ ] Discord webhook support
- [ ] Slack integration
- [ ] SMS notifications (via Twilio)
- [ ] Push notifications (via OneSignal)
- [ ] Webhook support for custom integrations
- [ ] Notification templates with customizable formatting
- [ ] Rate limiting per notification method
- [ ] Notification batching for multiple opportunities
- [ ] Retry logic with exponential backoff
- [ ] Notification history/audit log
