# Godel Terminal Framework Architecture

## Overview
Modular framework for automating Godel Terminal commands using Selenium WebDriver.

## Structure

```
godel_api/
├── godel_core.py          # Core framework (Controller, BaseCommand, DOMMonitor)
├── commands/              # Command implementations
│   ├── __init__.py       # Package exports
│   ├── des_command.py    # Description command (fully implemented)
│   ├── g_command.py      # Chart command (placeholder)
│   ├── gip_command.py    # Intraday chart (placeholder)
│   └── qm_command.py     # Quote monitor (placeholder)
├── main.py               # Example usage
└── config.py             # URL and credentials
```

## Core Components

### `GodelTerminalController`
Main controller for browser automation and command execution.

**Key Methods:**
- `connect()` - Initialize Chrome browser
- `login(username, password)` - Authenticate
- `register_command(type, class)` - Register command implementations
- `execute_command(type, ticker, asset_class)` - Execute and return `(result_dict, command_instance)`
- `close_all_windows()` - Clean up

### `BaseCommand` (Abstract)
Base class for all commands. Subclasses must implement:
- `get_command_string(ticker, asset_class)` - Format command
- `extract_data()` - Extract window data

**Built-in Methods:**
- `execute(ticker, asset_class)` - Full execution lifecycle
- `close()` - Close window

### `DOMMonitor`
Tracks DOM changes to detect new windows and loading states.

## Command Implementation Example

```python
from godel_core import BaseCommand

class MyCommand(BaseCommand):
    def get_command_string(self, ticker, asset_class):
        return f"{ticker} {asset_class} CMD"
    
    def extract_data(self):
        # Extract from self.window
        return {'data': '...'}
```

## Usage

```python
from godel_core import GodelTerminalController
from commands import DESCommand
from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD

# Initialize
controller = GodelTerminalController(GODEL_URL)
controller.register_command('DES', DESCommand)

# Execute
controller.connect()
controller.login(GODEL_USERNAME, GODEL_PASSWORD)
controller.open_terminal()

result, cmd = controller.execute_command('DES', 'AAPL', 'EQ')
if result['success']:
    print(result['data'])
    cmd.close()

controller.disconnect()
```

## DES Command Details

**Extracted Data:**
- Ticker symbol
- Company info (name, logo, website, address, CEO)
- Company description (auto-expands "See more")
- EPS estimates (formatted as `{'Q4, Dec 25': '-0.85'}`)
- Analyst ratings (firm, analyst, rating, target, date)
- Snapshot metrics (exchange, float, P/E ratios, dividends, etc.)

**Auto-expansion:**
- Clicks "See more" for full description
- Clicks "Show all" for complete analyst ratings

## Extension

1. Create new command in `commands/my_command.py`
2. Inherit from `BaseCommand`
3. Implement `get_command_string()` and `extract_data()`
4. Register: `controller.register_command('MY', MyCommand)`

## Error Handling

All extraction methods include:
- Try/except blocks with detailed logging
- Traceback printing for debugging
- Graceful degradation (returns empty dict/list on failure) 