# PRT Command - Quick Start Guide

## Overview
The PRT (Pattern Real-Time) command automates running pattern analysis on multiple tickers and exporting results to CSV.

## Basic Usage

### Using the Example Script

```bash
cd godel_api
python example_prt_usage.py
```

This will analyze 20 tickers and export the results to CSV automatically.

### Using the CLI

The CLI now supports PRT commands with this syntax:

```bash
python cli.py PRT AAPL NVDA META GOOGL MSFT
```

Or multiple tickers:

```bash
python cli.py PRT AAPL NVDA META GOOGL MSFT AMZN JPM BAC XOM HD PG KO
```

### Programmatic Usage

```python
from godel_core import GodelTerminalController
from commands.prt_command import PRTCommand
from config import GODEL_URL, USERNAME, PASSWORD

# Setup
controller = GodelTerminalController(url=GODEL_URL, headless=False)
controller.connect()
controller.login(USERNAME, PASSWORD)
controller.open_terminal()

# Option 1: Direct instantiation
tickers = ["AAPL", "NVDA", "META", "GOOGL", "MSFT"]
prt_cmd = PRTCommand(controller, tickers=tickers)
result = prt_cmd.execute()

# Option 2: Using execute_command (recommended)
controller.register_command('PRT', PRTCommand)
result, cmd = controller.execute_command('PRT', ticker=tickers)

# Check results
if result['success']:
    print(f"CSV exported to: {result['csv_file']}")
    print(f"Performance summary: {result['data']['performance_summary']}")

controller.disconnect()
```

## What It Does

1. ✅ Opens PRT window by typing "PRT" in terminal
2. ✅ Inputs your ticker list into the textarea
3. ✅ Clicks the "Run" button
4. ✅ Monitors progress until completion (100%)
5. ✅ Verifies results table populated
6. ✅ Clicks "Export CSV" button
7. ✅ Detects and returns the CSV file path
8. ✅ Extracts performance summary data

## Output

### Result Dictionary

```python
{
    'success': True,
    'command': 'PRT',
    'csv_file': '/Users/you/Downloads/prt_results.csv',
    'data': {
        'timestamp': '2025-10-09T12:30:00Z',
        'tickers': ['AAPL', 'NVDA', ...],
        'progress': {'completed': '20', 'total': '20'},
        'failures': 0,
        'performance_summary': [...]
    }
}
```

### CSV File

The CSV file is automatically downloaded to your Downloads folder and contains:
- Symbol, Time, Direction (LONG/SHORT)
- Edge, Probability Up, Mean, P10, P90
- Number of neighbors, Distance, Actual performance

## Configuration

### Timeouts
- Window creation: 10 seconds
- Analysis completion: 120 seconds
- CSV download: 10 seconds

### Requirements
- Browser must be configured to auto-download CSVs (no prompt)
- Downloads folder must be writable
- Market should be open for best results

## Troubleshooting

**CSV not downloading?**
- Check browser download settings
- Increase timeout in `export_csv()` method

**Progress stuck?**
- Check the Failures table in UI
- Verify tickers are valid
- Increase timeout in `wait_for_completion()`

**Tickers not being entered?**
- Ensure PRT window fully loaded
- Check textarea selector in code

## Examples

### Small Test Run
```python
tickers = ["AAPL", "MSFT", "GOOGL"]
prt_cmd = PRTCommand(controller, tickers=tickers)
result = prt_cmd.execute()
```

### Large Batch
```python
# Read tickers from file
with open('my_tickers.txt', 'r') as f:
    tickers = [line.strip() for line in f if line.strip()]

prt_cmd = PRTCommand(controller, tickers=tickers)
result = prt_cmd.execute()
```

### With Error Handling
```python
result = prt_cmd.execute()

if result['success']:
    csv_file = result['csv_file']
    print(f"✓ Success! CSV: {csv_file}")
    
    # Process CSV
    import pandas as pd
    df = pd.read_csv(csv_file)
    print(df.head())
else:
    print(f"✗ Failed: {result['error']}")
```

## Next Steps

- See `commands/PRT_COMMAND_README.md` for detailed documentation
- Check `example_prt_usage.py` for complete examples
- Review `godel_core.py` for the base framework

## CLI Command Format

Standard commands:
```
python cli.py TICKER ASSET COMMAND
```

PRT command (special format):
```
python cli.py PRT TICKER1 TICKER2 TICKER3 ...
```

Examples:
```bash
# DES command
python cli.py AAPL EQ DES

# PRT command
python cli.py PRT AAPL NVDA META GOOGL MSFT
```


