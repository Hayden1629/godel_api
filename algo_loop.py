'''
loops requests to most and prt,
generates lists of tickers then sends them to schwab API
'''
from godel_core import GodelTerminalController
from commands.most_command import MOSTCommand
from commands.prt_command import PRTCommand
import pandas as pd
import time


def process_most(dataframe):
    """Process MOST data and extract tickers"""
    # process most data
    if 'Ticker' in dataframe.columns:
        list_of_tickers = dataframe['Ticker'].tolist()
        return list_of_tickers
    else:
        print("Warning: 'Ticker' column not found in MOST dataframe")
        return []


def process_prt(dataframe):
    """Process PRT data and extract trade signals"""
    # process prt data
    # Example: filter for high-probability trades
    # Adjust based on your actual PRT CSV structure
    if dataframe is not None and len(dataframe) > 0:
        # Filter for trades with specific criteria
        # This is just an example - adjust based on your needs
        list_of_trades = dataframe.to_dict('records')
        return list_of_trades
    else:
        print("Warning: Empty PRT dataframe")
        return []


def main():
    """Main loop for MOST -> PRT -> Schwab API workflow"""
    # initialize controller
    controller = GodelTerminalController()
    controller.connect()
    controller.login()
    controller.load_layout("dev")
    
    # loop requests to most and prt
    # persistent window 
    try:
        while True:
            # request most
            print("\n=== Fetching MOST data ===")
            most_cmd = MOSTCommand(controller, tab="ACTIVE", limit=75)
            most_result = most_cmd.execute()
            
            # Check if successful and get dataframe
            if most_result['success']:
                most_df = most_cmd.get_dataframe()
                print(f"MOST DataFrame shape: {most_df.shape}")
                print(f"Columns: {most_df.columns.tolist()}")
                
                # Process most data to get tickers
                list_of_tickers = process_most(most_df)
                print(f"Extracted {len(list_of_tickers)} tickers: {list_of_tickers[:10]}...")
                
                # request prt
                if list_of_tickers:
                    print("\n=== Fetching PRT data ===")
                    prt_cmd = PRTCommand(controller, list_of_tickers)
                    prt_result = prt_cmd.execute()
                    
                    # Check if successful and get dataframe
                    if prt_result['success']:
                        prt_df = prt_cmd.get_dataframe()
                        print(f"PRT DataFrame shape: {prt_df.shape}")
                        print(f"Columns: {prt_df.columns.tolist()}")
                        
                        # Process prt data to get trades
                        list_of_trades = process_prt(prt_df)
                        print(f"Extracted {len(list_of_trades)} trade signals")
                        
                        # TODO: send list of trades to schwab API
                        # schwab_api.place_orders(list_of_trades)
                    else:
                        print(f"PRT failed: {prt_result.get('error')}")
                else:
                    print("No tickers to process with PRT")
            else:
                print(f"MOST failed: {most_result.get('error')}")
            
            # Wait before next iteration
            print("\nWaiting 60 seconds before next iteration...")
            time.sleep(60)
            
    except KeyboardInterrupt:
        print("\nStopping algo loop...")
    except Exception as e:
        print(f"Error in main loop: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
    
    