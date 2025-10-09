"""
Example Usage: MOST Command
Demonstrates how to use the MOST command to get market data
"""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
from godel_core import GodelTerminalController
from commands import MOSTCommand


def example_basic_most():
    """Example 1: Basic MOST command usage"""
    print("=" * 60)
    print("EXAMPLE 1: Basic MOST Command")
    print("=" * 60)
    
    controller = GodelTerminalController(GODEL_URL, headless=False)
    controller.register_command("MOST", MOSTCommand)
    
    try:
        # Connect and login
        controller.connect()
        controller.login(GODEL_USERNAME, GODEL_PASSWORD)
        controller.load_layout("dev")
        controller.open_terminal()
        
        # Execute MOST command (default: ACTIVE tab, 75 results)
        result, cmd = controller.execute_command("MOST")
        
        if result['success']:
            df = result['data']['dataframe']
            print(f"\n✓ Retrieved {len(df)} stocks")
            print(f"\nTop 10 stocks:")
            print(df.head(10)[['Ticker', 'Name', 'Last', 'Chg %', 'Vol']].to_string())
            
            cmd.close()
        else:
            print(f"Error: {result.get('error')}")
    
    finally:
        controller.disconnect()


def example_most_with_tabs():
    """Example 2: Get data from different tabs"""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: MOST Command with Different Tabs")
    print("=" * 60)
    
    controller = GodelTerminalController(GODEL_URL, headless=False)
    controller.register_command("MOST", MOSTCommand)
    
    try:
        controller.connect()
        controller.login(GODEL_USERNAME, GODEL_PASSWORD)
        controller.load_layout("dev")
        controller.open_terminal()
        
        tabs = ["ACTIVE", "GAINERS", "LOSERS"]
        
        for tab in tabs:
            print(f"\n📊 Getting {tab} stocks...")
            result, cmd = controller.execute_command("MOST", tab, 25)
            
            if result['success']:
                df = result['data']['dataframe']
                print(f"   Retrieved {len(df)} stocks")
                
                # Save to file
                output_dir = Path(__file__).parent / "output"
                output_dir.mkdir(exist_ok=True)
                csv_file = output_dir / f"most_{tab.lower()}.csv"
                df.to_csv(csv_file, index=False)
                print(f"   Saved to: {csv_file}")
                
                cmd.close()
            else:
                print(f"   Error: {result.get('error')}")
    
    finally:
        controller.disconnect()


def example_most_analysis():
    """Example 3: Analyze MOST data with pandas"""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Analyzing MOST Data")
    print("=" * 60)
    
    controller = GodelTerminalController(GODEL_URL, headless=False)
    controller.register_command("MOST", MOSTCommand)
    
    try:
        controller.connect()
        controller.login(GODEL_USERNAME, GODEL_PASSWORD)
        controller.load_layout("dev")
        controller.open_terminal()
        
        # Get losers data
        result, cmd = controller.execute_command("MOST", "LOSERS", 100)
        
        if result['success']:
            df = result['data']['dataframe']
            
            print(f"\n📊 Analysis of {len(df)} biggest losers:\n")
            
            # Statistical analysis
            if 'Chg % Numeric' in df.columns:
                print(f"Average decline: {df['Chg % Numeric'].mean():.2f}%")
                print(f"Median decline: {df['Chg % Numeric'].median():.2f}%")
                print(f"Worst decline: {df['Chg % Numeric'].min():.2f}%")
            
            # Volume analysis
            if 'Vol Numeric' in df.columns:
                print(f"\nTotal volume: {df['Vol Numeric'].sum():,.0f}")
                print(f"Average volume: {df['Vol Numeric'].mean():,.0f}")
            
            # Find stocks with biggest losses and high volume
            print(f"\n🔍 Big losers with high volume (top 5):")
            if 'Vol Numeric' in df.columns and 'Chg % Numeric' in df.columns:
                high_vol = df.nlargest(20, 'Vol Numeric')
                big_losers = high_vol.nsmallest(5, 'Chg % Numeric')
                print(big_losers[['Ticker', 'Name', 'Last', 'Chg %', 'Vol']].to_string())
            
            cmd.close()
        else:
            print(f"Error: {result.get('error')}")
    
    finally:
        controller.disconnect()


def example_most_filter():
    """Example 4: Filter MOST data"""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Filtering MOST Data")
    print("=" * 60)
    
    controller = GodelTerminalController(GODEL_URL, headless=False)
    controller.register_command("MOST", MOSTCommand)
    
    try:
        controller.connect()
        controller.login(GODEL_USERNAME, GODEL_PASSWORD)
        controller.load_layout("dev")
        controller.open_terminal()
        
        # Get gainers
        result, cmd = controller.execute_command("MOST", "GAINERS", 100)
        
        if result['success']:
            df = result['data']['dataframe']
            
            print(f"\n📊 Filtering {len(df)} gainers:\n")
            
            # Filter 1: Stocks up more than 10%
            if 'Chg % Numeric' in df.columns:
                big_gainers = df[df['Chg % Numeric'] > 10]
                print(f"🚀 Stocks up >10%: {len(big_gainers)}")
                if len(big_gainers) > 0:
                    print(big_gainers[['Ticker', 'Name', 'Chg %', 'Vol']].head(5).to_string())
            
            # Filter 2: High volume stocks (>10M)
            if 'Vol Numeric' in df.columns:
                print(f"\n📈 High volume stocks (>10M):")
                high_vol = df[df['Vol Numeric'] > 10_000_000]
                print(f"   Found {len(high_vol)} stocks")
                if len(high_vol) > 0:
                    print(high_vol[['Ticker', 'Name', 'Vol', 'Chg %']].head(5).to_string())
            
            # Filter 3: Stocks with price > $50
            if 'Last Numeric' in df.columns:
                print(f"\n💰 Stocks priced >$50:")
                expensive = df[df['Last Numeric'] > 50]
                print(f"   Found {len(expensive)} stocks")
                if len(expensive) > 0:
                    print(expensive[['Ticker', 'Name', 'Last', 'Chg %']].head(5).to_string())
            
            cmd.close()
        else:
            print(f"Error: {result.get('error')}")
    
    finally:
        controller.disconnect()


def example_most_export():
    """Example 5: Export MOST data in different formats"""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Exporting MOST Data")
    print("=" * 60)
    
    controller = GodelTerminalController(GODEL_URL, headless=False)
    controller.register_command("MOST", MOSTCommand)
    
    try:
        controller.connect()
        controller.login(GODEL_USERNAME, GODEL_PASSWORD)
        controller.load_layout("dev")
        controller.open_terminal()
        
        result, cmd = controller.execute_command("MOST", "ACTIVE", 50)
        
        if result['success']:
            df = result['data']['dataframe']
            output_dir = Path(__file__).parent / "output"
            output_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Export as CSV
            csv_file = output_dir / f"most_active_{timestamp}.csv"
            df.to_csv(csv_file, index=False)
            print(f"✓ Exported CSV: {csv_file}")
            
            # Export as JSON
            json_file = output_dir / f"most_active_{timestamp}.json"
            df.to_json(json_file, orient='records', indent=2)
            print(f"✓ Exported JSON: {json_file}")
            
            # Export as Excel (requires openpyxl)
            try:
                excel_file = output_dir / f"most_active_{timestamp}.xlsx"
                df.to_excel(excel_file, index=False, engine='openpyxl')
                print(f"✓ Exported Excel: {excel_file}")
            except ImportError:
                print("⚠️  Excel export requires openpyxl (pip install openpyxl)")
            
            # Export filtered data
            if 'Chg % Numeric' in df.columns:
                big_movers = df[abs(df['Chg % Numeric']) > 5]
                if len(big_movers) > 0:
                    filtered_file = output_dir / f"most_bigmovers_{timestamp}.csv"
                    big_movers.to_csv(filtered_file, index=False)
                    print(f"✓ Exported big movers: {filtered_file}")
            
            cmd.close()
        else:
            print(f"Error: {result.get('error')}")
    
    finally:
        controller.disconnect()


def example_most_comparison():
    """Example 6: Compare gainers vs losers"""
    print("\n" + "=" * 60)
    print("EXAMPLE 6: Comparing Gainers vs Losers")
    print("=" * 60)
    
    controller = GodelTerminalController(GODEL_URL, headless=False)
    controller.register_command("MOST", MOSTCommand)
    
    try:
        controller.connect()
        controller.login(GODEL_USERNAME, GODEL_PASSWORD)
        controller.load_layout("dev")
        controller.open_terminal()
        
        # Get gainers
        print("\n📈 Getting GAINERS...")
        result_gainers, cmd_gainers = controller.execute_command("MOST", "GAINERS", 50)
        
        if result_gainers['success']:
            df_gainers = result_gainers['data']['dataframe']
            cmd_gainers.close()
        
        # Get losers
        print("📉 Getting LOSERS...")
        result_losers, cmd_losers = controller.execute_command("MOST", "LOSERS", 50)
        
        if result_losers['success']:
            df_losers = result_losers['data']['dataframe']
            cmd_losers.close()
        
        # Compare
        if result_gainers['success'] and result_losers['success']:
            print(f"\n📊 Comparison:")
            print(f"   Gainers: {len(df_gainers)} stocks")
            if 'Chg % Numeric' in df_gainers.columns:
                print(f"   Average gain: {df_gainers['Chg % Numeric'].mean():.2f}%")
                print(f"   Top gainer: {df_gainers['Chg % Numeric'].max():.2f}%")
            
            print(f"\n   Losers: {len(df_losers)} stocks")
            if 'Chg % Numeric' in df_losers.columns:
                print(f"   Average loss: {df_losers['Chg % Numeric'].mean():.2f}%")
                print(f"   Worst loser: {df_losers['Chg % Numeric'].min():.2f}%")
            
            # Market sentiment
            if 'Chg % Numeric' in df_gainers.columns and 'Chg % Numeric' in df_losers.columns:
                avg_gain = df_gainers['Chg % Numeric'].mean()
                avg_loss = df_losers['Chg % Numeric'].mean()
                sentiment = avg_gain + avg_loss
                print(f"\n📊 Market Sentiment Score: {sentiment:.2f}")
                print(f"   (Positive = bullish, Negative = bearish)")
    
    finally:
        controller.disconnect()


def main():
    """Run all examples"""
    print("MOST Command Examples\n")
    print("Choose an example:")
    print("1. Basic MOST usage")
    print("2. Get data from different tabs")
    print("3. Analyze MOST data")
    print("4. Filter MOST data")
    print("5. Export MOST data")
    print("6. Compare gainers vs losers")
    print("7. Run all examples")
    
    choice = input("\nEnter choice (1-7): ").strip()
    
    if choice == "1":
        example_basic_most()
    elif choice == "2":
        example_most_with_tabs()
    elif choice == "3":
        example_most_analysis()
    elif choice == "4":
        example_most_filter()
    elif choice == "5":
        example_most_export()
    elif choice == "6":
        example_most_comparison()
    elif choice == "7":
        example_basic_most()
        example_most_with_tabs()
        example_most_analysis()
        example_most_filter()
        example_most_export()
        example_most_comparison()
    else:
        print("Invalid choice")
    
    print("\n✅ Examples complete!")


if __name__ == "__main__":
    main()

