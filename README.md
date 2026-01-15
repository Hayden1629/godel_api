# Godel Terminal API

Selenium-based API for automating the Godel Terminal. Execute commands programmatically and get structured data back.

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy `config-example.py` to `config.py` and fill in your credentials:
```bash
cp config-example.py config.py
# Edit config.py with your Godel Terminal credentials
```

## Quick Start

```python
from godel_core import GodelTerminalController
from commands import DESCommand, PRTCommand, MOSTCommand
from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD

# Initialize controller
controller = GodelTerminalController(GODEL_URL, headless=False)
controller.connect()
controller.login(GODEL_USERNAME, GODEL_PASSWORD)

# Execute a command
des = DESCommand(controller)
result = des.execute("AAPL", "EQ")
print(result['data'])

# Cleanup
controller.disconnect()
```

## Core Components

### `GodelTerminalController`

Main controller class that manages the Selenium browser session and terminal interaction.

**Methods:**
- `connect()` - Initialize browser and navigate to terminal
- `login(username, password)` - Log in to Godel Terminal
- `load_layout(layout_name)` - Load a specific layout (default: "dev")
- `open_terminal()` - Open terminal using backtick key
- `send_command(command_str)` - Send a command string to terminal
- `execute_command(command_type, ticker, asset_class, **kwargs)` - Execute a registered command
- `close_all_windows()` - Close all active command windows
- `disconnect()` - Close browser and cleanup

### `BaseCommand`

Abstract base class for all terminal commands. Provides common functionality for:
- Window detection and management
- Data extraction workflow
- Window closing with multiple fallback strategies

## Available Commands

### DES (Description) Command

Extracts comprehensive company information including description, financials, and analyst ratings.

**Usage:**
```python
from commands import DESCommand

des = DESCommand(controller)
result = des.execute("AAPL", "EQ")

# Access extracted data
data = result['data']
print(data['company_info']['company_name'])
print(data['description'])
print(data['analyst_ratings'])
print(data['eps_estimates'])
print(data['snapshot'])
```

**Returns:**
- `company_info`: Company name, logo, website, address, CEO, asset class
- `description`: Full company description
- `eps_estimates`: EPS estimates by quarter/fiscal year
- `analyst_ratings`: List of analyst ratings with firm, analyst, rating, targets, date
- `snapshot`: Key financial metrics (market cap, P/E, etc.)

### PRT (Pattern Real-Time) Command

Runs batch pattern analysis on multiple tickers and exports results to CSV.

**Usage:**
```python
from commands import PRTCommand

# Initialize with list of tickers
prt = PRTCommand(controller, tickers=["AAPL", "MSFT", "GOOGL"])
result = prt.execute()

# Access CSV file path and DataFrame
csv_path = result['csv_file']
df = prt.get_dataframe()

# Or save to custom location
prt.save_to_csv("custom_path.csv")
prt.save_to_json("custom_path.json")
```

**Parameters:**
- `tickers`: List of ticker symbols to analyze

**Returns:**
- `csv_file_path`: Path to downloaded CSV file
- `dataframe`: pandas DataFrame with results
- `performance_summary`: Performance metrics by bucket
- `progress`: Completion status
- `failures`: Number of failed analyses

### MOST (Most Active Stocks) Command

Extracts most active stocks table data into a pandas DataFrame.

**Usage:**
```python
from commands import MOSTCommand

# Initialize with tab and limit
most = MOSTCommand(controller, tab="ACTIVE", limit=75)
result = most.execute()

# Access DataFrame
df = most.get_dataframe()
tickers = result['data']['tickers']

# Save results
most.save_to_csv("most_active.csv")
most.save_to_json("most_active.json")
```

**Parameters:**
- `tab`: Tab to select - "ACTIVE", "GAINERS", "LOSERS", or "VALUE" (default: "ACTIVE")
- `limit`: Number of results - 10, 25, 50, 75, or 100 (default: 75)

**Returns:**
- `dataframe`: pandas DataFrame with stock data
- `tickers`: List of ticker symbols
- `records`: List of dictionaries with row data
- `row_count`: Number of rows extracted

### G (Chart) Command

Opens price chart window (data extraction not yet implemented).

**Usage:**
```python
from commands import GCommand

g = GCommand(controller)
result = g.execute("AAPL", "EQ")
```

### GIP (Intraday Chart) Command

Opens intraday price chart window (data extraction not yet implemented).

**Usage:**
```python
from commands import GIPCommand

gip = GIPCommand(controller)
result = gip.execute("AAPL", "EQ")
```

### QM (Quote Monitor) Command

Opens quote monitor window (data extraction not yet implemented).

**Usage:**
```python
from commands import QMCommand

qm = QMCommand(controller)
result = qm.execute("AAPL", "EQ")
```

## Command Execution Pattern

All commands follow the same execution pattern:

1. **Initialize**: Create command instance with controller
2. **Execute**: Call `execute(ticker, asset_class)` or `execute()` for commands that don't need tickers
3. **Check Result**: Verify `result['success']` is `True`
4. **Access Data**: Use `result['data']` to access extracted information
5. **Close**: Command windows are automatically tracked; use `controller.close_all_windows()` to close all

## Error Handling

All commands return a result dictionary with:
- `success`: Boolean indicating if command succeeded
- `error`: Error message if `success` is `False`
- `command`: Command string that was executed
- `data`: Extracted data (if successful)

Always check `result['success']` before accessing `result['data']`.

## Best Practices

1. **Reuse Controller**: Initialize controller once and reuse for multiple commands
2. **Close Windows**: Periodically call `controller.close_all_windows()` to prevent window buildup
3. **Error Handling**: Always check `result['success']` before accessing data
4. **Headless Mode**: Use `headless=True` for automated scripts (but may have limitations)
5. **Cleanup**: Always call `controller.disconnect()` when done

## Architecture

```
godel_api/
├── godel_core.py          # Core framework (Controller, BaseCommand, DOMMonitor)
├── commands/
│   ├── __init__.py       # Command exports
│   ├── des_command.py    # DES command implementation
│   ├── prt_command.py    # PRT command implementation
│   ├── most_command.py   # MOST command implementation
│   ├── g_command.py      # G command implementation
│   ├── gip_command.py    # GIP command implementation
│   └── qm_command.py     # QM command implementation
├── config-example.py     # Configuration template
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## Python Module Interface

For programmatic use in other Python scripts, use the `godel_api` module:

```python
from godel_api import GodelAPI

# Using context manager (recommended)
with GodelAPI() as api:
    # Execute DES command
    result = api.des("AAPL", "EQ")
    if result['success']:
        print(result['data']['company_info']['company_name'])
    
    # Execute PRT command
    result = api.prt(["AAPL", "MSFT", "GOOGL"], output_path="results.csv")
    
    # Execute MOST command
    result = api.most(tab="GAINERS", limit=50, output_path="gainers.csv")
    if result['success']:
        df = result['data']['dataframe']
        print(df.head())

# Or manual connection management
api = GodelAPI()
api.connect()
result = api.des("AAPL")
api.disconnect()
```

### Quick Functions

For one-off commands, use the quick functions:

```python
from godel_api import quick_des, quick_prt, quick_most

# Quick DES
result = quick_des("AAPL")

# Quick PRT
result = quick_prt(["AAPL", "MSFT"])

# Quick MOST
result = quick_most(tab="ACTIVE", limit=75)
```

## Command Line Interface

Use the CLI for command-line execution:

```bash
# DES command
python cli.py des AAPL --output aapl_des.json

# PRT command
python cli.py prt AAPL MSFT GOOGL --output results.csv

# MOST command
python cli.py most --tab GAINERS --limit 50 --output gainers.csv

# With custom layout
python cli.py des AAPL --layout my_layout

# Headless mode
python cli.py des AAPL --headless
```

Run `python cli.py --help` for full usage information.

## Notes

- Commands automatically detect new windows created by the terminal
- Window closing uses multiple fallback strategies for reliability
- Data extraction waits for loading spinners to complete
- CSV exports from PRT go to your Downloads folder by default
- Use context managers (`with` statement) for automatic cleanup
