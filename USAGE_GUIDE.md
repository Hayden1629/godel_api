# Godel Terminal Monitor - Usage Guide

## Overview

The `godel_terminal_monitor.py` script provides comprehensive DOM monitoring and data extraction for the Godel Terminal's DES command.

## Features

### 1. **DOMMonitor Class**
- Tracks all window elements in the DOM
- Detects when new windows are created
- Prevents duplicate tracking with window ID tracking

### 2. **DESDataExtractor Class**
Extracts structured data including:
- **Company Header**: Name, logo, website, address, CEO
- **Description**: Company business description
- **Stats**: Price, Shares Outstanding, Market Cap
- **EPS Estimates**: Quarterly and annual estimates
- **Analyst Ratings**: Firm, analyst, rating, target price, date
- **Snapshot**: Market info, company stats, valuation ratios, dividends, risk metrics

### 3. **GodelTerminalController Class**
- Opens browser and navigates to terminal
- Opens terminal with backtick key
- Sends commands
- Monitors for window creation
- Waits for loading completion
- Extracts all data
- Saves to JSON

## Quick Start

### Step 1: Update Configuration

Edit the `main()` function in `godel_terminal_monitor.py`:

```python
# Configuration
TERMINAL_URL = "https://app.godelterminal.com"  # Your actual terminal URL
TICKER = "SRPT"  # Ticker you want to query
ASSET_CLASS = "EQ"  # Asset class
```

### Step 2: Run the Script

```bash
python godel_terminal_monitor.py
```

### Step 3: Observe the Process

The script will:
1. Open browser
2. Navigate to terminal
3. Press backtick to open terminal
4. Send "SRPT EQ DES" command
5. Monitor for new window
6. Wait for loading to complete
7. Extract all data
8. Save to JSON file
9. Display summary
10. Wait for you to press Enter before closing

## Output Format

### Console Output

```
============================================================
Godel Terminal DES Command Monitor
============================================================
Connected to https://app.godelterminal.com
Terminal opened

Executing: SRPT EQ DES
Current windows: 0
Command sent: SRPT EQ DES
Waiting for new window...
New window detected: 3729-window
Waiting for content to load...
Loading complete
Extracting data...

============================================================
RESULTS
============================================================
✓ Command executed successfully

Ticker: SRPT US
Window ID: 3729-window

Company: Sarepta Therapeutics Inc
Website: https://sarepta.com
CEO: Mr. Douglas S. Ingram Esq., J.D.

Stats:
  price: $18.85
  shares_out: 96.9M
  market_cap: $1.8B

Analyst Ratings: 5 found

✓ Full data saved to: des_data_SRPT_20251001_120000.json

============================================================
Press Enter to close browser...
```

### JSON Output

```json
{
  "success": true,
  "command": "SRPT EQ DES",
  "data": {
    "timestamp": "2025-10-01T12:00:00Z",
    "window_id": "3729-window",
    "ticker": "SRPT US",
    "company_info": {
      "company_name": "Sarepta Therapeutics Inc",
      "asset_class": "EQ",
      "logo_url": "https://api.twelvedata.com/logo/sarepta.com",
      "website": "https://sarepta.com",
      "address": "215 FIRST STREET, SUITE 415, CAMBRIDGE, MA, 02142",
      "ceo": "CEO: Mr. Douglas S. Ingram Esq., J.D."
    },
    "description": "Sarepta Therapeutics, Inc., a commercial-stage biopharmaceutical company, focuses on the discovery and development of RNA-targeted therapeut...",
    "stats": {
      "price": "$18.85",
      "shares_out": "96.9M",
      "market_cap": "$1.8B"
    },
    "eps_estimates": {
      "date": {
        "Q4": "Dec 25",
        "FY25": "Dec 25",
        "FY26": "Dec 26"
      },
      "eps": {
        "Q4": "-0.85",
        "FY25": "-2.27",
        "FY26": "3.25"
      }
    },
    "analyst_ratings": [
      {
        "firm": "BMO Capital",
        "analyst": "Kostas Biliouris",
        "rating": "Outperform",
        "target": "$50 → $50",
        "date": "09/22/25 12:19"
      }
      // ... more ratings
    ],
    "snapshot": {
      "market_info": {
        "Exchange": "XNGS",
        "Currency": "USD",
        "Float": "87.6M"
      },
      "company_stats": {
        "Employees": "1,372",
        "Insiders": "4.66%",
        "Institutions": "82.23%"
      },
      "valuation_ratios": {
        "P/Sales": "0.77",
        "P/Book": "1.32",
        "EV/EBITDA": "58.74"
        // ... more ratios
      }
      // ... more sections
    }
  }
}
```

## Usage as a Library

You can also use the classes as a library in your own scripts:

```python
from godel_terminal_monitor import GodelTerminalController

# Initialize
controller = GodelTerminalController("https://app.godelterminal.com")
controller.connect()

# Open terminal
controller.open_terminal()

# Execute command and get data
result = controller.execute_des_command("AAPL", "EQ")

if result['success']:
    data = result['data']
    print(f"Company: {data['company_info']['company_name']}")
    print(f"Price: {data['stats']['price']}")
else:
    print(f"Error: {result['error']}")

# Clean up
controller.disconnect()
```

## Multiple Tickers

To query multiple tickers:

```python
from godel_terminal_monitor import GodelTerminalController
import time

controller = GodelTerminalController("https://app.godelterminal.com")
controller.connect()
controller.open_terminal()

tickers = ["SRPT", "AAPL", "MSFT", "GOOGL"]
results = []

for ticker in tickers:
    result = controller.execute_des_command(ticker, "EQ")
    results.append(result)
    time.sleep(2)  # Be nice to the server

controller.disconnect()

# Process results
for result in results:
    if result['success']:
        print(f"{result['data']['ticker']}: ✓")
    else:
        print(f"{ticker}: ✗ {result['error']}")
```

## Headless Mode

For production use, run in headless mode:

```python
controller = GodelTerminalController(
    "https://app.godelterminal.com",
    headless=True
)
```

## Troubleshooting

### Issue: Terminal doesn't open
**Solution**: The backtick key might not be the correct key. Check the terminal's keyboard shortcuts.

### Issue: Window not detected
**Solutions**:
1. Increase timeout: Modify `get_new_window(timeout=20)`
2. Check CSS selector is still valid
3. Ensure you're logged in if authentication is required

### Issue: Loading timeout
**Solutions**:
1. Increase timeout: Modify `wait_for_loading(timeout=60)`
2. Check network connection
3. Verify ticker symbol is valid

### Issue: Data extraction fails
**Solutions**:
1. Check if HTML structure has changed
2. Use browser DevTools to inspect elements
3. Update CSS selectors in `DESDataExtractor` methods

## Customization

### Extract Additional Data

Add new extraction methods to `DESDataExtractor`:

```python
@staticmethod
def extract_custom_field(window) -> Any:
    """Extract your custom field"""
    try:
        element = window.find_element(By.CSS_SELECTOR, "your-selector")
        return element.text
    except Exception as e:
        print(f"Error: {e}")
        return None
```

Then add to `extract_all()`:

```python
data['custom_field'] = DESDataExtractor.extract_custom_field(window)
```

### Add Authentication

If terminal requires login:

```python
def login(self):
    """Login to terminal"""
    username_input = self.driver.find_element(By.ID, "username")
    password_input = self.driver.find_element(By.ID, "password")
    
    username_input.send_keys("your_username")
    password_input.send_keys("your_password")
    password_input.send_keys(Keys.RETURN)
    
    time.sleep(3)  # Wait for login
```

Call after `connect()`:

```python
controller.connect()
controller.login()
controller.open_terminal()
```

## Best Practices

1. **Rate Limiting**: Add delays between requests
2. **Error Handling**: Always check `result['success']`
3. **Logging**: Save logs for debugging
4. **Cleanup**: Always call `disconnect()` (use try/finally)
5. **Validation**: Verify extracted data makes sense

## Next Steps

1. **Extend to Other Commands**: Create extractors for G (chart), N (news), etc.
2. **Database Storage**: Store extracted data in a database instead of JSON
3. **Scheduling**: Run periodically with cron or Task Scheduler
4. **API Server**: Wrap in Flask/FastAPI for REST API
5. **Monitoring Dashboard**: Visualize extracted data 