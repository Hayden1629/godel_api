"""
Godel Terminal Debug Script
Non-headless mode for debugging with browser visible
"""

import json
import time
import shutil
import pandas as pd
from pathlib import Path
from datetime import datetime
from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
from godel_core import GodelTerminalController
from commands import DESCommand, PRTCommand, MOSTCommand


def process_prt_csv(csv_file_path: str, output_dir: Path = None) -> dict:
    """
    Process PRT CSV file and convert to various formats
    
    Args:
        csv_file_path: Path to the downloaded CSV file
        output_dir: Optional directory to save processed files
    
    Returns:
        dict with processed data and file paths
    """
    try:
        # Read CSV with pandas
        df = pd.read_csv(csv_file_path)
        
        print(f"\n📊 Processing CSV: {csv_file_path}")
        print(f"   Rows: {len(df)}, Columns: {len(df.columns)}")
        print(f"   Columns: {', '.join(df.columns.tolist())}")
        
        # Convert to various formats
        result = {
            'success': True,
            'original_csv': csv_file_path,
            'data': {
                'json': df.to_dict(orient='records'),  # List of dicts (one per row)
                'json_columns': df.to_dict(orient='list'),  # Dict of lists (one per column)
                'summary': {
                    'total_rows': len(df),
                    'columns': df.columns.tolist(),
                    'symbols': df['symbol'].tolist() if 'symbol' in df.columns else []
                }
            }
        }
        
        # Optionally save to output directory
        if output_dir:
            output_dir.mkdir(exist_ok=True)
            
            # Copy CSV to output directory with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_csv_path = output_dir / f"prt_results_{timestamp}.csv"
            shutil.copy2(csv_file_path, new_csv_path)
            print(f"   ✓ Copied CSV to: {new_csv_path}")
            
            # Save as JSON
            json_path = output_dir / f"prt_results_{timestamp}.json"
            with open(json_path, 'w') as f:
                json.dump(result['data'], f, indent=2)
            print(f"   ✓ Saved JSON to: {json_path}")
            
            result['saved_files'] = {
                'csv': str(new_csv_path),
                'json': str(json_path)
            }
        
        # Print sample data
        print(f"\n📋 Sample data (first row):")
        if len(df) > 0:
            for col in df.columns:
                print(f"   {col}: {df.iloc[0][col]}")
        
        return result
        
    except Exception as e:
        print(f"\n✗ Error processing CSV: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e),
            'original_csv': csv_file_path
        }


def test_des_command():
    """Debug mode - browser stays open"""
    
    # Configuration - modify these for testing
    TICKER = "PLTR"
    ASSET_CLASS = "EQ"
    COMMAND_TYPE = "DES"
    
    print(f"\n🔍 DEBUG MODE - Executing: {TICKER} {ASSET_CLASS} {COMMAND_TYPE}\n")
    
    # Initialize in non-headless mode
    controller = GodelTerminalController(GODEL_URL, headless=False)
    controller.register_command(COMMAND_TYPE, DESCommand)
    
    try:
        # Execute
        controller.connect()
        controller.login(GODEL_USERNAME, GODEL_PASSWORD)
        controller.load_layout("dev")
        controller.open_terminal()
        
        result, cmd = controller.execute_command(COMMAND_TYPE, TICKER, ASSET_CLASS)
        
        # Save output
        if result['success']:
            output_dir = Path(__file__).parent / "output"
            output_dir.mkdir(exist_ok=True)
            output_file = output_dir / f"debug_{TICKER}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            print(f"\n✓ Saved: {output_file}")
            cmd.close()
            time.sleep(3)  # Wait before disconnect
        else:
            print(f"\n✗ Error: {result.get('error')}")
        
        # Keep browser open
        input("\n[Browser stays open] Press Enter to close...")
        
    except Exception as e:
        print(f"\n✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to close...")
    finally:
        controller.disconnect()
def test_prt_command():
    """Debug mode - browser stays open"""
    
    COMMAND_TYPE = "PRT"
    tickerList = ["AAPL", "NVDA", "META", "GOOGL", "MSFT"]
    print(f"\n🔍 DEBUG MODE - Executing: {COMMAND_TYPE}\n")
    
    # Initialize in non-headless mode
    controller = GodelTerminalController(GODEL_URL, headless=False)
    controller.register_command(COMMAND_TYPE, PRTCommand)
    
    try:
        # Execute
        controller.connect()
        controller.login(GODEL_USERNAME, GODEL_PASSWORD)
        controller.load_layout("dev")
        controller.open_terminal()
        
        result, cmd = controller.execute_command(COMMAND_TYPE, tickerList)
        
        # Process the results
        if result['success']:
            print("\n✓ PRT Command executed successfully!")
            
            # Get the CSV file path from the result
            csv_file_path = result.get('csv_file')
            
            if csv_file_path:
                print(f"\n📁 CSV downloaded to: {csv_file_path}")
                
                # Process the CSV file
                output_dir = Path(__file__).parent / "output"
                processed_data = process_prt_csv(csv_file_path, output_dir)
                
                if processed_data['success']:
                    # Now you can use the processed data
                    print(f"\n✅ Processing complete!")
                    print(f"   Total symbols analyzed: {len(processed_data['data']['summary']['symbols'])}")
                    
                    # Example: Send data to another program
                    # You can now use processed_data['data']['json'] for further processing
                    # or pass it to APIs, other functions, etc.
                    
                else:
                    print(f"\n⚠️ Warning: Failed to process CSV")
            else:
                print("\n⚠️ Warning: No CSV file path in result")
            
            # Keep browser open for inspection
            input("\n[Browser stays open] Press Enter to close...")
            cmd.close()
            time.sleep(3)  # Wait before disconnect
        else:
            print(f"\n✗ Error: {result.get('error')}")
    except Exception as e:
        print(f"\n✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to close...")
    finally:
        controller.disconnect()

def test_most_command():
    """Debug mode - browser stays open"""
    
    COMMAND_TYPE = "MOST"
    TAB = "ACTIVE"  # Options: ACTIVE, GAINERS, LOSERS, VALUE
    LIMIT = 75  # Options: 10, 25, 50, 75, 100
    
    print(f"\n🔍 DEBUG MODE - Executing: {COMMAND_TYPE} ({TAB}, Limit: {LIMIT})\n")
    
    # Initialize in non-headless mode
    controller = GodelTerminalController(GODEL_URL, headless=False)
    controller.register_command(COMMAND_TYPE, MOSTCommand)
    
    try:
        # Execute
        controller.connect()
        controller.login(GODEL_USERNAME, GODEL_PASSWORD)
        controller.load_layout("dev")
        controller.open_terminal()
        
        result, cmd = controller.execute_command(COMMAND_TYPE, TAB, LIMIT)
        
        # Process the results
        if result['success']:
            print("\n✓ MOST Command executed successfully!")
            
            # Get the DataFrame
            df = result['data']['dataframe']
            
            print(f"\n📊 Retrieved {len(df)} stocks")
            print(f"\n📋 Columns: {', '.join(df.columns.tolist())}")
            
            # Display sample data
            print(f"\n🔝 Top 5 stocks:")
            print(df.head(5).to_string())
            
            # Save to output directory
            output_dir = Path(__file__).parent / "output"
            output_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            csv_file = output_dir / f"most_{TAB.lower()}_{timestamp}.csv"
            json_file = output_dir / f"most_{TAB.lower()}_{timestamp}.json"
            
            # Save using the command's methods
            cmd.save_to_csv(str(csv_file))
            cmd.save_to_json(str(json_file))
            
            # Example: Filter and analyze
            print(f"\n📈 Analysis:")
            if 'Chg % Numeric' in df.columns:
                avg_change = df['Chg % Numeric'].mean()
                print(f"   Average change: {avg_change:.2f}%")
            
            if 'Vol Numeric' in df.columns:
                total_volume = df['Vol Numeric'].sum()
                print(f"   Total volume: {total_volume:,.0f}")
            
            # Keep browser open for inspection
            input("\n[Browser stays open] Press Enter to close...")
            cmd.close()
            time.sleep(3)  # Wait before disconnect
        else:
            print(f"\n✗ Error: {result.get('error')}")
    except Exception as e:
        print(f"\n✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to close...")
    finally:
        controller.disconnect()

def main():
    choice = input("DES, PRT, or MOST? ").upper()
    if choice == "DES":
        test_des_command()
    elif choice == "PRT":
        test_prt_command()
    elif choice == "MOST":
        test_most_command()
    else:
        print("Invalid input. Choose DES, PRT, or MOST")
        return

if __name__ == "__main__":
    main() 