# Pattern Labeling Interface - User Guide

## Overview

The Pattern Labeling Interface allows you to annotate historical market data with pattern labels, building a dataset for pattern recognition, machine learning, or analysis.

## Accessing the Interface

1. Start the Streamlit dashboard:
   ```bash
   streamlit run run_live.py
   ```
   Or use the dashboard:
   ```bash
   streamlit run app/ui/dashboard.py
   ```

2. Navigate to **"Replay & Label"** from the sidebar menu

## Features

### 1. Market Selection
- Choose from all markets with historical data in the history store
- See the number of available data points for each market

### 2. Date Range Selection
- Pick start and end dates to focus on specific time periods
- Default range: last 7 days

### 3. Price Chart Tab
View historical price data with interactive charts:
- **Yes & No Prices**: Shows both outcome prices over time
- **Yes Price Only**: Isolated Yes price chart
- **No Price Only**: Isolated No price chart
- **Volume**: Optional volume overlay

The timeline shows labeled events as markers with timestamps.

### 4. Annotate Tab
Add new pattern labels to specific timestamps:

**Available Label Types:**
- **"news-driven move"** - Price movements caused by news events
- **"whale entry"** - Large trader activity detected
- **"arb collapse"** - Arbitrage opportunity collapse
- **"false signal"** - False positive in detection

**To add a label:**
1. Select the date and time of the pattern
2. Choose the label type from dropdown
3. Optionally add notes explaining the pattern
4. Click "Save Label"

### 5. View Labels Tab
Browse and manage existing labels:

**Features:**
- Filter by label type
- Sort by timestamp (newest/oldest first)
- View statistics (total counts per label type)
- Export labels to CSV
- Delete individual labels
- Bulk delete all labels (with confirmation)

## Use Cases

### 1. Building Training Datasets
Label historical patterns to create datasets for:
- Machine learning model training
- Pattern recognition algorithms
- Anomaly detection systems

### 2. Market Analysis
Document and analyze:
- Market-moving events
- Whale activity patterns
- Arbitrage opportunity lifecycles
- Detection false positives

### 3. Algorithm Validation
- Label known patterns to validate detection algorithms
- Identify false signals for algorithm improvement
- Build ground truth datasets for backtesting

## Database Schema

Labels are stored in the `history_labels` table:
```sql
CREATE TABLE history_labels (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    market_id TEXT,
    label_type TEXT,
    notes TEXT
)
```

## API Functions

Programmatic access to labels:

```python
from app.core.logger import (
    save_history_label,
    fetch_history_labels,
    delete_history_label,
)
from datetime import datetime

# Save a label
save_history_label({
    "timestamp": datetime.now(),
    "market_id": "market_123",
    "label_type": "whale entry",
    "notes": "Large buy detected at 0.65"
})

# Fetch labels
labels = fetch_history_labels(
    market_id="market_123",
    start="2024-01-01T00:00:00",
    end="2024-12-31T23:59:59",
    limit=100
)

# Delete a label
delete_history_label(label_id=1)
```

## Tips

1. **Be Specific with Notes**: Add context that explains why you chose this label
2. **Use Consistent Criteria**: Develop clear rules for each label type
3. **Export Regularly**: Back up your labels to CSV files
4. **Review Timeline**: Use the timeline view to see patterns in your labeling

## Example Workflow

1. Generate or collect historical market data
2. Navigate to Replay & Label view
3. Select a market with interesting patterns
4. Adjust date range to focus on specific period
5. Review the price chart to identify patterns
6. Switch to Annotate tab
7. Add labels at key timestamps
8. Switch to View Labels tab to review
9. Export labeled dataset to CSV for analysis

## Integration with Other Tools

The labeled data can be:
- Exported to CSV for analysis in Excel, Python, R
- Queried directly from the SQLite database
- Used to train ML models for pattern recognition
- Combined with arbitrage detection logs for validation

## Troubleshooting

**No markets available:**
- Run data collection scripts to populate history store
- Check that `data/market_history.db` exists and contains data

**Labels not saving:**
- Verify timestamp is within selected date range
- Check database write permissions
- Review logs for error messages

**Charts not displaying:**
- Ensure market has tick data in the selected date range
- Try a different date range or market

## Future Enhancements

Potential additions (not yet implemented):
- Multi-user labeling with user tracking
- Label confidence scores
- Bulk labeling tools
- Label revision history
- Inter-rater reliability metrics
