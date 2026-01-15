#!/usr/bin/env python3
"""
Godel Terminal CLI
Command-line interface for executing Godel Terminal commands
"""

import argparse
import sys
import json
from pathlib import Path
from typing import List, Optional

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from godel_core import GodelTerminalController
from commands import (
    DESCommand, PRTCommand, MOSTCommand,
    GCommand, GIPCommand, QMCommand
)

try:
    from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
except ImportError:
    print("Error: config.py not found. Please copy config-example.py to config.py and fill in your credentials.")
    sys.exit(1)


def execute_des(controller: GodelTerminalController, ticker: str, asset_class: str = "EQ", output: Optional[str] = None):
    """Execute DES command"""
    print(f"Executing DES command for {ticker} {asset_class}...")
    des = DESCommand(controller)
    result = des.execute(ticker, asset_class)
    
    if result['success']:
        print("✓ DES command executed successfully")
        if output:
            with open(output, 'w') as f:
                json.dump(result['data'], f, indent=2)
            print(f"Data saved to {output}")
        else:
            print(json.dumps(result['data'], indent=2))
        return True
    else:
        print(f"✗ DES command failed: {result.get('error', 'Unknown error')}")
        return False


def execute_prt(controller: GodelTerminalController, tickers: List[str], output: Optional[str] = None):
    """Execute PRT command"""
    print(f"Executing PRT command for {len(tickers)} tickers...")
    prt = PRTCommand(controller, tickers=tickers)
    result = prt.execute()
    
    if result['success']:
        print("✓ PRT command executed successfully")
        print(f"CSV file: {result.get('csv_file', 'N/A')}")
        
        # Save DataFrame if output specified
        if output:
            if output.endswith('.csv'):
                prt.save_to_csv(output)
            elif output.endswith('.json'):
                prt.save_to_json(output)
            else:
                prt.save_to_csv(output + '.csv')
            print(f"Results saved to {output}")
        
        # Print summary
        df = prt.get_dataframe()
        if df is not None:
            print(f"Rows: {len(df)}, Columns: {len(df.columns)}")
        
        return True
    else:
        print(f"✗ PRT command failed: {result.get('error', 'Unknown error')}")
        return False


def execute_most(controller: GodelTerminalController, tab: str = "ACTIVE", limit: int = 75, output: Optional[str] = None):
    """Execute MOST command"""
    print(f"Executing MOST command (tab: {tab}, limit: {limit})...")
    most = MOSTCommand(controller, tab=tab, limit=limit)
    result = most.execute()
    
    if result['success']:
        print("✓ MOST command executed successfully")
        data = result['data']
        print(f"Rows extracted: {data.get('row_count', 0)}")
        
        # Save DataFrame if output specified
        if output:
            if output.endswith('.csv'):
                most.save_to_csv(output)
            elif output.endswith('.json'):
                most.save_to_json(output)
            else:
                most.save_to_csv(output + '.csv')
            print(f"Results saved to {output}")
        
        # Print tickers
        tickers = data.get('tickers', [])
        if tickers:
            print(f"Tickers: {', '.join(tickers[:10])}{'...' if len(tickers) > 10 else ''}")
        
        return True
    else:
        print(f"✗ MOST command failed: {result.get('error', 'Unknown error')}")
        return False


def execute_g(controller: GodelTerminalController, ticker: str, asset_class: str = "EQ"):
    """Execute G command"""
    print(f"Executing G command for {ticker} {asset_class}...")
    g = GCommand(controller)
    result = g.execute(ticker, asset_class)
    
    if result['success']:
        print("✓ G command executed successfully")
        print(json.dumps(result['data'], indent=2))
        return True
    else:
        print(f"✗ G command failed: {result.get('error', 'Unknown error')}")
        return False


def execute_gip(controller: GodelTerminalController, ticker: str, asset_class: str = "EQ"):
    """Execute GIP command"""
    print(f"Executing GIP command for {ticker} {asset_class}...")
    gip = GIPCommand(controller)
    result = gip.execute(ticker, asset_class)
    
    if result['success']:
        print("✓ GIP command executed successfully")
        print(json.dumps(result['data'], indent=2))
        return True
    else:
        print(f"✗ GIP command failed: {result.get('error', 'Unknown error')}")
        return False


def execute_qm(controller: GodelTerminalController, ticker: str, asset_class: str = "EQ"):
    """Execute QM command"""
    print(f"Executing QM command for {ticker} {asset_class}...")
    qm = QMCommand(controller)
    result = qm.execute(ticker, asset_class)
    
    if result['success']:
        print("✓ QM command executed successfully")
        print(json.dumps(result['data'], indent=2))
        return True
    else:
        print(f"✗ QM command failed: {result.get('error', 'Unknown error')}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Godel Terminal CLI - Execute terminal commands programmatically',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Execute DES command
  python cli.py des AAPL
  
  # Execute DES with custom asset class and save output
  python cli.py des AAPL --asset-class OPT --output aapl_des.json
  
  # Execute PRT command with multiple tickers
  python cli.py prt AAPL MSFT GOOGL --output results.csv
  
  # Execute MOST command
  python cli.py most --tab GAINERS --limit 50 --output gainers.csv
  
  # Execute G command
  python cli.py g AAPL
  
  # Headless mode (no browser window)
  python cli.py des AAPL --headless
        """
    )
    
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--url', default=GODEL_URL, help=f'Godel Terminal URL (default: {GODEL_URL})')
    parser.add_argument('--layout', default='dev', help='Layout name to load (default: dev)')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # DES command
    des_parser = subparsers.add_parser('des', help='Execute DES (Description) command')
    des_parser.add_argument('ticker', help='Ticker symbol')
    des_parser.add_argument('--asset-class', default='EQ', help='Asset class (default: EQ)')
    des_parser.add_argument('--output', '-o', help='Output file path (JSON)')
    
    # PRT command
    prt_parser = subparsers.add_parser('prt', help='Execute PRT (Pattern Real-Time) command')
    prt_parser.add_argument('tickers', nargs='+', help='Ticker symbols (space-separated)')
    prt_parser.add_argument('--output', '-o', help='Output file path (CSV or JSON)')
    
    # MOST command
    most_parser = subparsers.add_parser('most', help='Execute MOST (Most Active Stocks) command')
    most_parser.add_argument('--tab', choices=['ACTIVE', 'GAINERS', 'LOSERS', 'VALUE'], 
                           default='ACTIVE', help='Tab to select (default: ACTIVE)')
    most_parser.add_argument('--limit', type=int, choices=[10, 25, 50, 75, 100], 
                           default=75, help='Number of results (default: 75)')
    most_parser.add_argument('--output', '-o', help='Output file path (CSV or JSON)')
    
    # G command
    g_parser = subparsers.add_parser('g', help='Execute G (Chart) command')
    g_parser.add_argument('ticker', help='Ticker symbol')
    g_parser.add_argument('--asset-class', default='EQ', help='Asset class (default: EQ)')
    
    # GIP command
    gip_parser = subparsers.add_parser('gip', help='Execute GIP (Intraday Chart) command')
    gip_parser.add_argument('ticker', help='Ticker symbol')
    gip_parser.add_argument('--asset-class', default='EQ', help='Asset class (default: EQ)')
    
    # QM command
    qm_parser = subparsers.add_parser('qm', help='Execute QM (Quote Monitor) command')
    qm_parser.add_argument('ticker', help='Ticker symbol')
    qm_parser.add_argument('--asset-class', default='EQ', help='Asset class (default: EQ)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Initialize controller
    print("Initializing Godel Terminal controller...")
    controller = GodelTerminalController(args.url, headless=args.headless)
    
    try:
        controller.connect()
        controller.login(GODEL_USERNAME, GODEL_PASSWORD)
        
        if args.layout:
            controller.load_layout(args.layout)
        
        # Execute command
        success = False
        if args.command == 'des':
            success = execute_des(controller, args.ticker, args.asset_class, args.output)
        elif args.command == 'prt':
            success = execute_prt(controller, args.tickers, args.output)
        elif args.command == 'most':
            success = execute_most(controller, args.tab, args.limit, args.output)
        elif args.command == 'g':
            success = execute_g(controller, args.ticker, args.asset_class)
        elif args.command == 'gip':
            success = execute_gip(controller, args.ticker, args.asset_class)
        elif args.command == 'qm':
            success = execute_qm(controller, args.ticker, args.asset_class)
        
        # Cleanup
        controller.close_all_windows()
        controller.disconnect()
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        controller.close_all_windows()
        controller.disconnect()
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        controller.close_all_windows()
        controller.disconnect()
        sys.exit(1)


if __name__ == '__main__':
    main()
