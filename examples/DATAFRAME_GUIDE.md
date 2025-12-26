# DataFrame Guide: PRT and MOST Commands

Both `PRTCommand` and `MOSTCommand` now return pandas DataFrames, making it easy to analyze and manipulate the data programmatically.

## Overview

### MOST Command
- Extracts data directly from the HTML table
- Returns DataFrame with cleaned numeric columns
- Includes parsed values for volumes, market caps, and percentages

### PRT Command
- Downloads CSV file automatically
- Loads CSV into pandas DataFrame
- Keeps reference to both CSV file path and DataFrame

## Quick Start

```python
from godel_core import GodelTerminalController
from commands.most_command import MOSTCommand
from commands.prt_command import PRTCommand

# Initialize controller
controller = GodelTerminalController()
controller.connect()
controller.login()
controller.load_layout("dev")

# Get MOST data
most_cmd = MOSTCommand(controller, tab="GAINERS", limit=50)
result = most_cmd.execute()
most_df = most_cmd.get_dataframe()

# Get PRT data
prt_cmd = PRTCommand(controller, tickers=['AAPL', 'MSFT', 'GOOGL'])
result = prt_cmd.execute()
prt_df = prt_cmd.get_dataframe()
```

## MOST Command DataFrame

### Accessing the DataFrame

```python
# Method 1: Using get_dataframe()
most_cmd = MOSTCommand(controller, tab="ACTIVE", limit=75)
result = most_cmd.execute()
df = most_cmd.get_dataframe()

# Method 2: From result dictionary
df = result['data']['dataframe']
```

### Available Columns

The MOST DataFrame typically includes:
- `Ticker`: Stock ticker symbol
- `Last`: Last price
- `Chg`: Price change
- `Chg %`: Percentage change
- `Vol`: Volume (with K, M, B suffixes)
- `Vol $`: Dollar volume
- `M Cap`: Market capitalization

### Cleaned Numeric Columns

MOST automatically creates numeric versions of certain columns:
- `Chg % Numeric`: Float version of percentage change
- `Vol Numeric`: Numeric volume (multipliers applied)
- `Vol $ Numeric`: Numeric dollar volume
- `M Cap Numeric`: Numeric market cap
- `Last Numeric`: Numeric last price
- `Chg Numeric`: Numeric change

### Example Usage

```python
# Get top gainers
most_cmd = MOSTCommand(controller, tab="GAINERS", limit=100)
result = most_cmd.execute()
df = most_cmd.get_dataframe()

# Filter by percentage change
top_10 = df.nlargest(10, 'Chg % Numeric')
print(top_10[['Ticker', 'Last', 'Chg %', 'Vol']])

# Filter by volume
high_volume = df[df['Vol Numeric'] > 10_000_000]

# Get tickers for further analysis
tickers = df['Ticker'].tolist()
```

### Saving Data

```python
# Save to CSV
most_cmd.save_to_csv('most_gainers.csv')

# Save to JSON
most_cmd.save_to_json('most_gainers.json')
```

## PRT Command DataFrame

### Accessing the DataFrame

```python
# Method 1: Using get_dataframe()
prt_cmd = PRTCommand(controller, tickers=['AAPL', 'MSFT'])
result = prt_cmd.execute()
df = prt_cmd.get_dataframe()

# Method 2: From result dictionary
df = result['data']['dataframe']

# Also get CSV file path
csv_path = result['csv_file']
csv_path2 = result['data']['csv_file_path']
```

### Available Data

The PRT DataFrame contains whatever columns are in the exported CSV. This typically includes:
- Pattern analysis results
- Trade suggestions
- Historical performance metrics
- Risk/reward ratios
- Entry/exit points

*(Exact columns depend on your PRT configuration)*

### Example Usage

```python
# Run PRT on multiple tickers
tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
prt_cmd = PRTCommand(controller, tickers)
result = prt_cmd.execute()
df = prt_cmd.get_dataframe()

# Analyze results
print(f"Total results: {len(df)}")
print(f"Columns: {df.columns.tolist()}")

# Filter for specific patterns or criteria
# (adjust based on your actual column names)
if 'Ticker' in df.columns:
    unique_tickers = df['Ticker'].unique()
    print(f"Analyzed tickers: {unique_tickers}")

# Access the CSV file directly if needed
csv_file = result['csv_file']
print(f"CSV saved at: {csv_file}")
```

### Saving Data

```python
# Save processed DataFrame to different location
prt_cmd.save_to_csv('prt_processed.csv')

# Save to JSON
prt_cmd.save_to_json('prt_processed.json')

# Note: Original CSV is already saved in Downloads folder
```

## Combined Workflow

### MOST → PRT Pipeline

```python
# Step 1: Get most active stocks
most_cmd = MOSTCommand(controller, tab="ACTIVE", limit=75)
most_result = most_cmd.execute()
most_df = most_cmd.get_dataframe()

# Step 2: Filter and select tickers
# Example: Get top 20 by volume
top_volume = most_df.nlargest(20, 'Vol Numeric')
tickers = top_volume['Ticker'].tolist()

# Step 3: Run PRT analysis
prt_cmd = PRTCommand(controller, tickers)
prt_result = prt_cmd.execute()
prt_df = prt_cmd.get_dataframe()

# Step 4: Combine and analyze
# Merge DataFrames if both have 'Ticker' column
combined_df = pd.merge(
    most_df, 
    prt_df, 
    on='Ticker', 
    how='inner',
    suffixes=('_most', '_prt')
)
```

### Automated Trading Loop

See `algo_loop.py` for a complete example of an automated loop that:
1. Fetches MOST data periodically
2. Extracts tickers
3. Runs PRT analysis
4. Processes trade signals
5. (TODO) Sends orders to trading API

```python
from algo_loop import main

# Run the automated loop
main()
```

## Return Value Structure

### MOST Command Result

```python
{
    'success': True,
    'command': 'MOST',
    'data': {
        'timestamp': '2025-10-09T12:00:00Z',
        'window_id': 'window_123',
        'tab': 'GAINERS',
        'limit': 50,
        'row_count': 50,
        'columns': ['Ticker', 'Last', 'Chg', ...],
        'dataframe': <pandas.DataFrame>,  # ← The DataFrame
        'records': [{...}, {...}, ...],    # Dict list format
        'tickers': ['AAPL', 'MSFT', ...]
    }
}
```

### PRT Command Result

```python
{
    'success': True,
    'command': 'PRT',
    'csv_file': '/Users/username/Downloads/prt_results.csv',
    'data': {
        'timestamp': '2025-10-09T12:00:00Z',
        'window_id': 'window_456',
        'tickers': ['AAPL', 'MSFT', ...],
        'csv_file_path': '/Users/username/Downloads/prt_results.csv',
        'dataframe': <pandas.DataFrame>,  # ← The DataFrame
        'row_count': 150,
        'columns': ['Ticker', 'Pattern', ...],
        'performance_summary': [...],
        'progress': {'completed': '5', 'total': '5'},
        'failures': 0
    }
}
```

## Error Handling

```python
# Always check for success
result = most_cmd.execute()
if result['success']:
    df = most_cmd.get_dataframe()
    if df is not None:
        # Process DataFrame
        print(f"Got {len(df)} rows")
    else:
        print("DataFrame is None")
else:
    print(f"Command failed: {result.get('error')}")
```

## Tips & Best Practices

1. **Check DataFrame before using**: Always verify `df is not None` and `len(df) > 0`

2. **Use numeric columns for filtering**: MOST provides `*_Numeric` columns for easy numerical operations

3. **Save important results**: Use `save_to_csv()` or `save_to_json()` to persist data

4. **Handle exceptions**: Wrap DataFrame operations in try-except blocks

5. **Limit ticker lists**: When passing tickers to PRT, consider limiting to 50-100 at a time

6. **Monitor CSV downloads**: PRT CSVs are saved to Downloads folder by default

## Complete Example

```python
from godel_core import GodelTerminalController
from commands.most_command import MOSTCommand
from commands.prt_command import PRTCommand
import pandas as pd

def analyze_top_movers():
    """Find top movers and analyze with PRT"""
    # Initialize
    controller = GodelTerminalController()
    controller.connect()
    controller.login()
    controller.load_layout("dev")
    
    # Get top gainers
    most_cmd = MOSTCommand(controller, tab="GAINERS", limit=100)
    most_result = most_cmd.execute()
    
    if not most_result['success']:
        print(f"MOST failed: {most_result['error']}")
        return
    
    most_df = most_cmd.get_dataframe()
    print(f"Found {len(most_df)} gainers")
    
    # Filter: > 5% gain and > 1M volume
    filtered = most_df[
        (most_df['Chg % Numeric'] > 5.0) & 
        (most_df['Vol Numeric'] > 1_000_000)
    ]
    
    print(f"Filtered to {len(filtered)} stocks")
    tickers = filtered['Ticker'].tolist()[:20]  # Top 20
    
    # Run PRT analysis
    prt_cmd = PRTCommand(controller, tickers)
    prt_result = prt_cmd.execute()
    
    if not prt_result['success']:
        print(f"PRT failed: {prt_result['error']}")
        return
    
    prt_df = prt_cmd.get_dataframe()
    print(f"PRT analyzed {len(prt_df)} patterns")
    
    # Save results
    most_cmd.save_to_csv('top_gainers.csv')
    prt_cmd.save_to_csv('prt_analysis.csv')
    
    return most_df, prt_df

if __name__ == "__main__":
    most_df, prt_df = analyze_top_movers()
```

## See Also

- `example_dataframe_usage.py` - Complete working examples
- `algo_loop.py` - Automated trading loop implementation
- `example_most_usage.py` - MOST-specific examples
- `example_prt_usage.py` - PRT-specific examples

