# PRT Command Documentation

## Overview

The **PRT (Pattern Real-Time) Command** is a Selenium-based automation component that executes pattern analysis on a list of stock tickers and exports the results to CSV format.

## Features

- ✅ Accepts custom list of tickers
- ✅ Automatically inputs tickers into the PRT window
- ✅ Clicks "Run" to start batch analysis
- ✅ Monitors progress until completion
- ✅ Verifies results table population
- ✅ Exports results to CSV file
- ✅ Extracts performance summary data
- ✅ Returns CSV file path in results

## Architecture

The `PRTCommand` class extends `BaseCommand` from `godel_core.py` and follows the same pattern as other commands like `DESCommand`.

### Key Methods

| Method | Description |
|--------|-------------|
| `__init__(controller, tickers)` | Initialize with controller and optional ticker list |
| `get_command_string()` | Returns "PRT" to send to terminal |
| `set_tickers(tickers)` | Update the ticker list |
| `input_tickers()` | Clear and input tickers into textarea |
| `click_run_button()` | Click Run button to start analysis |
| `wait_for_completion()` | Wait for progress bar to reach 100% |
| `verify_results_table()` | Verify "Top suggestions" table has data |
| `export_csv()` | Click Export CSV and detect downloaded file |
| `execute()` | Main execution flow (overrides BaseCommand) |
| `extract_data()` | Extract summary data from PRT window |

## Usage

### Basic Usage

```python
from godel_core import GodelTerminalController
from commands.prt_command import PRTCommand
from config import GODEL_URL, USERNAME, PASSWORD

# Initialize controller
controller = GodelTerminalController(url=GODEL_URL, headless=False)
controller.connect()
controller.login(USERNAME, PASSWORD)
controller.open_terminal()

# Define tickers
tickers = ["AAPL", "NVDA", "META", "GOOGL", "MSFT"]

# Create and execute PRT command
prt_cmd = PRTCommand(controller, tickers=tickers)
result = prt_cmd.execute()

# Check results
if result['success']:
    print(f"CSV File: {result['csv_file']}")
    print(f"Data: {result['data']}")
else:
    print(f"Error: {result['error']}")

# Cleanup
controller.disconnect()
```

### Using Default Tickers

If you don't want to change the tickers that are already in the UI:

```python
# Create command without specifying tickers
prt_cmd = PRTCommand(controller, tickers=None)
result = prt_cmd.execute()
```

### Updating Tickers After Creation

```python
prt_cmd = PRTCommand(controller)
prt_cmd.set_tickers(["TSLA", "NFLX", "AMD"])
result = prt_cmd.execute()
```

## Response Format

### Success Response

```python
{
    'success': True,
    'command': 'PRT',
    'data': {
        'timestamp': '2025-10-09T12:30:00Z',
        'window_id': '3909-window',
        'tickers': ['AAPL', 'NVDA', ...],
        'csv_file_path': '/Users/you/Downloads/prt_results_20251009.csv',
        'progress': {
            'completed': '20',
            'total': '20'
        },
        'failures': 0,
        'performance_summary': [
            {
                'bucket': 'Top 1%',
                'n': '1',
                'long': '0',
                'short': '1',
                'win_rate': '100.0%',
                'mean_pl': '0.52%',
                'median_pl': '0.52%'
            },
            ...
        ]
    },
    'csv_file': '/Users/you/Downloads/prt_results_20251009.csv'
}
```

### Error Response

```python
{
    'success': False,
    'error': 'Analysis did not complete in time',
    'command': 'PRT',
    'window_id': '3909-window'
}
```

## Implementation Details

### Window Detection

The command uses the `DOMMonitor` to detect when the PRT window appears after sending the "PRT" command to the terminal.

### Completion Detection

The command monitors two indicators to determine completion:
1. **Progress bar width**: Checks if the green progress bar has `width: 100%`
2. **Progress text**: Checks if the text shows equal values (e.g., "20 / 20")

### CSV Export

The CSV export works by:
1. Recording existing CSV files in the Downloads folder
2. Clicking the "Export CSV" button
3. Polling for new CSV files (up to 10 seconds)
4. Returning the path to the newly created file

### Table Verification

Before exporting, the command verifies that the "Top suggestions" table contains data rows to ensure the analysis completed successfully.

## Selectors Reference

Key HTML selectors used by the command:

| Element | Selector |
|---------|----------|
| Ticker textarea | `.//label[contains(., 'Symbols')]//textarea` |
| Run button | `.//button[contains(@class, 'bg-emerald-600') and contains(text(), 'Run')]` |
| Progress bar | `div.h-full.bg-\[\#10b981\]` |
| Progress text | `.//div[contains(text(), '/')]` |
| Top suggestions table | `.//div[contains(text(), 'Top suggestions')]/..//table` |
| Export CSV button | `.//button[contains(text(), 'Export CSV')]` |
| Performance summary | `.//div[contains(text(), 'Performance Summary')]/..//table` |

## Configuration

### Timeouts

- **Window creation**: 10 seconds
- **Analysis completion**: 120 seconds (2 minutes)
- **CSV download**: 10 seconds

These can be adjusted in the method implementations if needed.

### Download Directory

The command assumes CSV files are downloaded to the user's Downloads folder:
- Windows: `C:\Users\{username}\Downloads`
- macOS/Linux: `/Users/{username}/Downloads` or `/home/{username}/Downloads`

## Error Handling

The command handles various error scenarios:

1. **Failed to send command**: Terminal input not available
2. **No new window created**: PRT window didn't appear
3. **Failed to input tickers**: Textarea not found or not interactable
4. **Failed to click Run button**: Button not found or disabled
5. **Analysis timeout**: Progress didn't reach 100% within timeout
6. **Failed to export CSV**: Export button not found or CSV not downloaded

## Integration Example

See `example_prt_usage.py` for complete working examples:

```bash
cd godel_api
python example_prt_usage.py
```

## Testing Considerations

When testing the PRT command:

1. **Market Hours**: Some tickers may fail outside market hours
2. **Ticker Validity**: Ensure tickers exist and are valid
3. **Network Speed**: Slow connections may require increased timeouts
4. **Download Folder**: Ensure write permissions to Downloads folder
5. **Browser Downloads**: Ensure browser is configured to download CSVs automatically (not prompt for location)

## Comparison to DES Command

| Feature | DES Command | PRT Command |
|---------|-------------|-------------|
| Input | Single ticker + asset class | List of tickers |
| Output | JSON data | CSV file + JSON summary |
| Execution | Per-ticker | Batch analysis |
| Data Extraction | Comprehensive company info | Performance metrics |
| Export | JSON to file | CSV export from UI |

## Future Enhancements

Potential improvements for future versions:

1. **Custom Parameters**: Support for k, extend, horizon, weighting, etc.
2. **Real-time Streaming**: Monitor progress with callbacks
3. **Result Validation**: Parse CSV and validate data structure
4. **Parallel Execution**: Run multiple PRT analyses concurrently
5. **Custom Download Location**: Allow specifying download directory
6. **Retry Logic**: Auto-retry failed tickers
7. **Performance Metrics**: Track execution time and success rates

## Troubleshooting

### CSV Not Downloading

- Check browser download settings
- Ensure Downloads folder exists and is writable
- Try increasing the timeout in `export_csv()`

### Progress Bar Not Reaching 100%

- Increase timeout in `wait_for_completion()`
- Check for failures in the Failures table
- Verify tickers are valid and market is open

### Ticker Input Failing

- Ensure PRT window has fully loaded
- Check textarea selector is correct
- Verify no modal or overlay is blocking the textarea

## Support

For issues or questions:
- Check `godel_api/USAGE_GUIDE.md` for general usage
- See `godel_api/ARCHITECTURE.md` for system architecture
- Review logs for detailed error messages


