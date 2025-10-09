"""
Example: Using PRT and MOST commands with pandas DataFrames

This script demonstrates how to:
1. Execute MOST command and get DataFrame
2. Execute PRT command and get DataFrame
3. Manipulate and analyze the DataFrames
"""

from godel_core import GodelTerminalController
from commands.most_command import MOSTCommand
from commands.prt_command import PRTCommand
import pandas as pd


def example_most_dataframe():
    """Example: Get MOST data as DataFrame"""
    print("=" * 50)
    print("MOST DataFrame Example")
    print("=" * 50)
    
    # Initialize controller
    controller = GodelTerminalController()
    controller.connect()
    controller.login()
    controller.load_layout("dev")
    
    # Create MOST command
    most_cmd = MOSTCommand(controller, tab="GAINERS", limit=50)
    result = most_cmd.execute()
    
    if result['success']:
        # Method 1: Get DataFrame directly from command
        df = most_cmd.get_dataframe()
        
        # Method 2: Get DataFrame from result dict
        # df = result['data']['dataframe']
        
        print(f"\nDataFrame shape: {df.shape}")
        print(f"\nColumns: {df.columns.tolist()}")
        print(f"\nFirst 5 rows:")
        print(df.head())
        
        # Access specific columns
        if 'Ticker' in df.columns:
            tickers = df['Ticker'].tolist()
            print(f"\nTickers: {tickers[:10]}...")
        
        # Filter data
        if 'Chg % Numeric' in df.columns:
            top_gainers = df.nlargest(5, 'Chg % Numeric')
            print(f"\nTop 5 gainers:")
            print(top_gainers[['Ticker', 'Last', 'Chg %']])
        
        # Save to CSV
        most_cmd.save_to_csv('most_output.csv')
        
        # Save to JSON
        most_cmd.save_to_json('most_output.json')
        
        return df
    else:
        print(f"Error: {result.get('error')}")
        return None


def example_prt_dataframe():
    """Example: Get PRT data as DataFrame"""
    print("\n" + "=" * 50)
    print("PRT DataFrame Example")
    print("=" * 50)
    
    # Initialize controller
    controller = GodelTerminalController()
    controller.connect()
    controller.login()
    controller.load_layout("dev")
    
    # Sample tickers
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
    
    # Create PRT command
    prt_cmd = PRTCommand(controller, tickers)
    result = prt_cmd.execute()
    
    if result['success']:
        # Method 1: Get DataFrame directly from command
        df = prt_cmd.get_dataframe()
        
        # Method 2: Get DataFrame from result dict
        # df = result['data']['dataframe']
        
        print(f"\nDataFrame shape: {df.shape}")
        print(f"\nColumns: {df.columns.tolist()}")
        print(f"\nFirst 5 rows:")
        print(df.head())
        
        # Analyze the data
        print(f"\nDataFrame info:")
        print(df.info())
        
        # Example: Filter for specific patterns or criteria
        # (adjust based on your actual PRT CSV structure)
        if 'Ticker' in df.columns:
            print(f"\nUnique tickers in results: {df['Ticker'].nunique()}")
        
        # Save to CSV (different location than auto-downloaded file)
        prt_cmd.save_to_csv('prt_processed.csv')
        
        # Save to JSON
        prt_cmd.save_to_json('prt_processed.json')
        
        return df
    else:
        print(f"Error: {result.get('error')}")
        return None


def example_combined_workflow():
    """Example: Use MOST to get tickers, then run PRT on them"""
    print("\n" + "=" * 50)
    print("Combined Workflow: MOST -> PRT")
    print("=" * 50)
    
    # Initialize controller
    controller = GodelTerminalController()
    controller.connect()
    controller.login()
    controller.load_layout("dev")
    
    # Step 1: Get most active stocks
    print("\nStep 1: Getting most active stocks...")
    most_cmd = MOSTCommand(controller, tab="ACTIVE", limit=25)
    most_result = most_cmd.execute()
    
    if not most_result['success']:
        print(f"MOST failed: {most_result.get('error')}")
        return
    
    most_df = most_cmd.get_dataframe()
    print(f"Got {len(most_df)} stocks from MOST")
    
    # Step 2: Extract tickers
    if 'Ticker' not in most_df.columns:
        print("Error: No 'Ticker' column in MOST data")
        return
    
    tickers = most_df['Ticker'].tolist()[:10]  # Limit to first 10
    print(f"Selected tickers: {tickers}")
    
    # Step 3: Run PRT analysis on those tickers
    print("\nStep 2: Running PRT analysis on selected tickers...")
    prt_cmd = PRTCommand(controller, tickers)
    prt_result = prt_cmd.execute()
    
    if not prt_result['success']:
        print(f"PRT failed: {prt_result.get('error')}")
        return
    
    prt_df = prt_cmd.get_dataframe()
    print(f"Got {len(prt_df)} results from PRT")
    
    # Step 4: Combine and analyze
    print("\nStep 3: Analyzing combined data...")
    print(f"MOST DataFrame columns: {most_df.columns.tolist()}")
    print(f"PRT DataFrame columns: {prt_df.columns.tolist()}")
    
    # Example: You could merge the DataFrames on ticker if both have it
    # merged_df = pd.merge(most_df, prt_df, on='Ticker', how='inner')
    
    return most_df, prt_df


if __name__ == "__main__":
    print("Pandas DataFrame Examples for MOST and PRT Commands\n")
    
    # Uncomment the example you want to run:
    
    # Example 1: MOST DataFrame
    # example_most_dataframe()
    
    # Example 2: PRT DataFrame
    # example_prt_dataframe()
    
    # Example 3: Combined workflow
    # example_combined_workflow()
    
    print("\nUncomment the example you want to run in the __main__ section")

