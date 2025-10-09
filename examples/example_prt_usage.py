"""
Example usage of PRT Command
Demonstrates how to run Pattern Real-Time analysis and export CSV
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from godel_core import GodelTerminalController
from commands.prt_command import PRTCommand
from config import GODEL_URL, USERNAME, PASSWORD


def main():
    # Initialize controller
    controller = GodelTerminalController(url=GODEL_URL, headless=False)
    
    try:
        # Connect and login
        print("Connecting to Godel Terminal...")
        controller.connect()
        controller.login(USERNAME, PASSWORD)
        
        # Load layout (optional)
        controller.load_layout("dev")
        
        # Open terminal
        controller.open_terminal()
        
        # Define tickers to analyze
        tickers = [
            "AAPL", "NVDA", "META", "GOOGL", "MSFT", "AMZN", 
            "JPM", "BAC", "XOM", "HD", "PG", "KO", "PEP", 
            "JNJ", "UNH", "TPL", "SMCI", "COIN", "SBAC", "HSY"
        ]
        
        # Create PRT command with tickers
        print(f"\nCreating PRT command with {len(tickers)} tickers...")
        prt_cmd = PRTCommand(controller, tickers=tickers)
        
        # Execute the command
        print("Executing PRT analysis...")
        result = prt_cmd.execute()
        
        # Check results
        if result['success']:
            print("\n" + "="*60)
            print("✓ PRT Analysis Complete!")
            print("="*60)
            
            # Print CSV file path
            csv_file = result.get('csv_file')
            print(f"\nCSV File: {csv_file}")
            
            # Print extracted data
            if 'data' in result:
                data = result['data']
                
                print(f"\nTimestamp: {data.get('timestamp')}")
                print(f"Window ID: {data.get('window_id')}")
                print(f"Tickers analyzed: {len(data.get('tickers', []))}")
                
                # Print progress
                if data.get('progress'):
                    prog = data['progress']
                    print(f"Progress: {prog.get('completed')}/{prog.get('total')}")
                
                # Print failure count
                failures = data.get('failures', 0)
                print(f"Failures: {failures}")
                
                # Print performance summary
                if data.get('performance_summary'):
                    print("\nPerformance Summary:")
                    print("-" * 60)
                    for perf in data['performance_summary']:
                        print(f"  {perf['bucket']:12} | N: {perf['n']:3} | "
                              f"Win Rate: {perf['win_rate']:7} | "
                              f"Mean P&L: {perf['mean_pl']:7} | "
                              f"Median P&L: {perf['median_pl']:7}")
            
            print("\n" + "="*60)
            
            # Optionally close the window
            # prt_cmd.close()
            
        else:
            print("\n✗ PRT Analysis Failed")
            print(f"Error: {result.get('error')}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Keep browser open for inspection
        input("\nPress Enter to close browser and exit...")
        controller.disconnect()


def run_with_custom_tickers():
    """Example: Run PRT with a custom ticker list"""
    controller = GodelTerminalController(url=GODEL_URL, headless=False)
    
    try:
        controller.connect()
        controller.login(USERNAME, PASSWORD)
        controller.open_terminal()
        
        # Custom ticker list
        my_tickers = ["TSLA", "NFLX", "AMD", "PLTR", "SOFI"]
        
        # Create and execute
        prt_cmd = PRTCommand(controller, tickers=my_tickers)
        result = prt_cmd.execute()
        
        if result['success']:
            print(f"✓ CSV exported to: {result['csv_file']}")
        else:
            print(f"✗ Failed: {result['error']}")
            
    finally:
        input("\nPress Enter to close...")
        controller.disconnect()


def run_without_changing_tickers():
    """Example: Run PRT with default tickers already in the UI"""
    controller = GodelTerminalController(url=GODEL_URL, headless=False)
    
    try:
        controller.connect()
        controller.login(USERNAME, PASSWORD)
        controller.open_terminal()
        
        # Create PRT command without specifying tickers
        # It will use whatever is already in the textarea
        prt_cmd = PRTCommand(controller, tickers=None)
        result = prt_cmd.execute()
        
        if result['success']:
            print(f"✓ CSV exported to: {result['csv_file']}")
        else:
            print(f"✗ Failed: {result['error']}")
            
    finally:
        input("\nPress Enter to close...")
        controller.disconnect()


if __name__ == "__main__":
    # Run the main example
    main()
    
    # Uncomment to run other examples:
    # run_with_custom_tickers()
    # run_without_changing_tickers()


