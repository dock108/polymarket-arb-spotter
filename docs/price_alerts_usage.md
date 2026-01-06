# Price Alerts JSON Storage

## Overview

The price alerts system provides persistent storage for market price alerts using a simple JSON file at `/data/price_alerts.json`. Alerts automatically persist across application restarts.

## Features

- **Persistent Storage**: Alerts are stored in JSON format and survive application restarts
- **Simple API**: Three main functions: `add_alert()`, `remove_alert()`, `list_alerts()`
- **Validation**: Automatic validation of price ranges (0-1) and market ID format
- **Unique IDs**: Auto-generated UUIDs or custom alert IDs
- **Sorted Listings**: Alerts are listed newest-first by creation time

## Usage

### Adding Alerts

```python
from app.core.price_alerts import add_alert

# Add alert with auto-generated ID
alert_id = add_alert(
    market_id="market_btc_100k",
    direction="above",  # or "below"
    target_price=0.85
)
print(f"Alert created with ID: {alert_id}")

# Add alert with custom ID
custom_id = add_alert(
    market_id="market_eth_merge",
    direction="below",
    target_price=0.30,
    alert_id="my_custom_alert_123"
)
```

### Listing Alerts

```python
from app.core.price_alerts import list_alerts

# Get all alerts (sorted by creation time, newest first)
alerts = list_alerts()

for alert in alerts:
    print(f"Alert {alert['id']}")
    print(f"  Market: {alert['market_id']}")
    print(f"  Direction: {alert['direction']}")
    print(f"  Target Price: {alert['target_price']}")
    print(f"  Created: {alert['created_at']}")
```

### Removing Alerts

```python
from app.core.price_alerts import remove_alert

# Remove by alert ID
success = remove_alert("my_custom_alert_123")
if success:
    print("Alert removed successfully")
else:
    print("Alert not found")
```

## Data Structure

Each alert in the JSON file has the following structure:

```json
{
  "alert-id-uuid": {
    "id": "alert-id-uuid",
    "market_id": "market_btc_100k",
    "direction": "above",
    "target_price": 0.85,
    "created_at": "2026-01-06T12:00:00.000000"
  }
}
```

## Validation

The system performs automatic validation:

- **Price Range**: Must be between 0.0 and 1.0 (inclusive)
- **Direction**: Must be either "above" or "below"
- **Market ID**: Must be a non-empty string (no whitespace-only strings)
- **Alert ID**: Must be unique (no duplicates)

## Error Handling

```python
from app.core.price_alerts import add_alert

# These will raise ValueError:
try:
    add_alert("market_id", "above", 1.5)  # Price > 1
except ValueError as e:
    print(f"Error: {e}")

try:
    add_alert("", "above", 0.5)  # Empty market_id
except ValueError as e:
    print(f"Error: {e}")

try:
    add_alert("market_id", "sideways", 0.5)  # Invalid direction
except ValueError as e:
    print(f"Error: {e}")
```

## File Location

By default, alerts are stored at:
```
/data/price_alerts.json
```

This file is automatically created when the first alert is added. The `/data` directory is automatically created if it doesn't exist.

**Note**: The `data/*.json` pattern is in `.gitignore`, so alert files remain local and are not committed to version control.

## Testing Persistence

To verify that alerts persist across restarts:

```python
# Session 1: Add some alerts
from app.core.price_alerts import add_alert, list_alerts

id1 = add_alert("market_1", "above", 0.7)
id2 = add_alert("market_2", "below", 0.3)
print(f"Added {len(list_alerts())} alerts")

# Session 2: Restart the application and list alerts
from app.core.price_alerts import list_alerts

alerts = list_alerts()
print(f"Found {len(alerts)} alerts after restart")
# Should print: Found 2 alerts after restart
```

## Complete Example

```python
from app.core.price_alerts import add_alert, remove_alert, list_alerts

# Start fresh
print("Initial alerts:", len(list_alerts()))

# Add some alerts
btc_id = add_alert("market_btc_100k", "above", 0.85)
eth_id = add_alert("market_eth_5k", "below", 0.30)
custom_id = add_alert("market_election", "above", 0.60, alert_id="election_alert")

print(f"Added 3 alerts")

# List all alerts
print("\nAll alerts:")
for alert in list_alerts():
    print(f"  - {alert['market_id']}: {alert['direction']} {alert['target_price']}")

# Remove one alert
remove_alert(custom_id)
print(f"\nRemoved alert: {custom_id}")

# List remaining alerts
print(f"Remaining alerts: {len(list_alerts())}")
```

## Integration with Price Checking

You can combine the storage system with the existing price checking functionality:

```python
from app.core.price_alerts import list_alerts, check_price_alert, PriceAlert

# Load stored alerts
stored_alerts = list_alerts()

# Check current prices (example)
for stored_alert in stored_alerts:
    # Recreate PriceAlert object
    alert = PriceAlert(
        market_id=stored_alert['market_id'],
        direction=stored_alert['direction'],
        target_price=stored_alert['target_price']
    )
    
    # Get current price from API (example)
    current_price = 0.88  # This would come from your API
    
    # Check if alert should trigger
    checked_alert = check_price_alert(alert, current_price)
    
    if checked_alert.triggered:
        print(f"🚨 Alert triggered: {checked_alert.alert_message}")
```
