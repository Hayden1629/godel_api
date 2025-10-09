# MOST Command - Quick Reference

## Overview
The MOST command opens the "Most Active" window and extracts all stock data into a pandas DataFrame for easy analysis.

## Basic Usage

```python
from godel_core import GodelTerminalController
from commands import MOSTCommand

controller = GodelTerminalController(GODEL_URL, headless=False)
controller.register_command("MOST", MOSTCommand)

controller.connect()
controller.login(username, password)
controller.load_layout("dev")
controller.open_terminal()

# Execute MOST command
result, cmd = controller.execute_command("MOST")

# Get the DataFrame
df = result['data']['dataframe']
print(df.head())

cmd.close()
controller.disconnect()
```

## Command Parameters

### Tab Selection
Choose which tab to display:
- `"ACTIVE"` - Most active stocks by volume (default)
- `"GAINERS"` - Biggest gainers by percentage
- `"LOSERS"` - Biggest losers by percentage
- `"VALUE"` - Value stocks

```python
# Get top losers
result, cmd = controller.execute_command("MOST", "LOSERS")
```

### Limit
Number of stocks to retrieve (10, 25, 50, 75, or 100):

```python
# Get top 100 gainers
result, cmd = controller.execute_command("MOST", "GAINERS", 100)
```

## DataFrame Columns

The extracted DataFrame includes:

### Original Columns
- `Ticker` - Stock symbol
- `Name` - Company name
- `Last` - Last price
- `Chg %` - Percentage change
- `Chg` - Dollar change
- `Vol` - Volume (formatted: 7.8M)
- `Vol $` - Dollar volume (formatted: 177.4M)
- `M Cap` - Market cap (formatted: 1.2B)
- `Time` - Last update time

### Cleaned Numeric Columns
The command automatically adds numeric versions:
- `Chg % Numeric` - Percentage as float
- `Last Numeric` - Price as float
- `Chg Numeric` - Change as float
- `Vol Numeric` - Volume as integer (millions converted)
- `Vol $ Numeric` - Dollar volume as integer
- `M Cap Numeric` - Market cap as integer

## Data Access

### Get DataFrame
```python
result, cmd = controller.execute_command("MOST", "ACTIVE", 50)

# Method 1: From result
df = result['data']['dataframe']

# Method 2: From command object
df = cmd.get_dataframe()
```

### Get as Records (JSON-friendly)
```python
records = result['data']['records']
# Returns: [{'Ticker': 'AAPL', 'Name': '...', ...}, ...]
```

### Get Summary
```python
summary = result['data']
print(f"Retrieved {summary['row_count']} stocks")
print(f"Tickers: {summary['tickers']}")
```

## Data Analysis Examples

### Filter by Price
```python
df = result['data']['dataframe']

# Stocks over $50
expensive = df[df['Last Numeric'] > 50]

# Stocks under $10
cheap = df[df['Last Numeric'] < 10]
```

### Filter by Change
```python
# Big gainers (>10%)
big_gainers = df[df['Chg % Numeric'] > 10]

# Big losers (<-10%)
big_losers = df[df['Chg % Numeric'] < -10]
```

### Filter by Volume
```python
# High volume (>10 million)
high_volume = df[df['Vol Numeric'] > 10_000_000]
```

### Sort Data
```python
# Top movers by percentage
top_movers = df.nlargest(10, 'Chg % Numeric')

# Highest volume
top_volume = df.nlargest(10, 'Vol Numeric')
```

### Statistical Analysis
```python
# Average change
avg_change = df['Chg % Numeric'].mean()

# Total volume
total_vol = df['Vol Numeric'].sum()

# Price statistics
price_stats = df['Last Numeric'].describe()
```

## Exporting Data

### Save to CSV
```python
result, cmd = controller.execute_command("MOST", "GAINERS", 100)

# Method 1: Using command
cmd.save_to_csv("gainers.csv")

# Method 2: Using DataFrame
df = result['data']['dataframe']
df.to_csv("gainers.csv", index=False)
```

### Save to JSON
```python
# Method 1: Using command
cmd.save_to_json("gainers.json")

# Method 2: Using DataFrame
df.to_json("gainers.json", orient='records', indent=2)
```

### Save to Excel
```python
df.to_excel("gainers.xlsx", index=False, engine='openpyxl')
```

## Complete Example

```python
from godel_core import GodelTerminalController
from commands import MOSTCommand
from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD

# Initialize
controller = GodelTerminalController(GODEL_URL, headless=False)
controller.register_command("MOST", MOSTCommand)

try:
    # Connect
    controller.connect()
    controller.login(GODEL_USERNAME, GODEL_PASSWORD)
    controller.load_layout("dev")
    controller.open_terminal()
    
    # Get top 100 losers
    result, cmd = controller.execute_command("MOST", "LOSERS", 100)
    
    if result['success']:
        df = result['data']['dataframe']
        
        # Analysis
        print(f"Retrieved {len(df)} stocks")
        print(f"Average decline: {df['Chg % Numeric'].mean():.2f}%")
        print(f"Worst decline: {df['Chg % Numeric'].min():.2f}%")
        
        # Filter high volume losers
        high_vol_losers = df[df['Vol Numeric'] > 10_000_000]
        print(f"\nHigh volume losers: {len(high_vol_losers)}")
        print(high_vol_losers[['Ticker', 'Name', 'Last', 'Chg %', 'Vol']].head(10))
        
        # Save results
        cmd.save_to_csv("top_losers.csv")
        
        cmd.close()
    else:
        print(f"Error: {result['error']}")
        
finally:
    controller.disconnect()
```

## Integration with Other Programs

### Send to API
```python
import requests

result, cmd = controller.execute_command("MOST", "GAINERS", 50)
data = result['data']['records']

response = requests.post(
    'https://your-api.com/stocks',
    json={'stocks': data}
)
```

### Save to Database
```python
import sqlite3

df = result['data']['dataframe']
conn = sqlite3.connect('stocks.db')
df.to_sql('most_active', conn, if_exists='append', index=False)
conn.close()
```

### Use with Other Libraries
```python
import matplotlib.pyplot as plt

# Plot volume distribution
df = result['data']['dataframe']
df['Vol Numeric'].hist(bins=20)
plt.xlabel('Volume')
plt.ylabel('Frequency')
plt.title('Volume Distribution')
plt.show()
```

## Error Handling

```python
result, cmd = controller.execute_command("MOST", "GAINERS", 75)

if result['success']:
    df = result['data']['dataframe']
    
    if df is not None and len(df) > 0:
        # Process data
        print(f"Success: {len(df)} stocks")
    else:
        print("No data retrieved")
else:
    print(f"Error: {result.get('error', 'Unknown error')}")
```

## Tips

1. **Wait for data to load**: The command includes automatic waits, but very large datasets (100 stocks) may need extra time
2. **Use numeric columns for calculations**: Always use the `*_Numeric` columns for math operations
3. **Filter before export**: Process and filter data before saving to reduce file size
4. **Close windows**: Always call `cmd.close()` to clean up the window
5. **Handle missing data**: Some stocks may have missing fields, use pandas' `fillna()` or `dropna()`

## See Also

- `example_most_usage.py` - Complete working examples
- `main.py` - Test function `test_most_command()`
- PRT Command - For pattern analysis
- DES Command - For detailed stock information

