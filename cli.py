"""
Godel Terminal CLI
Command-line interface for executing Godel Terminal commands
"""

import json
import sys
import os
import time
from io import StringIO
from contextlib import redirect_stdout
from pathlib import Path
from datetime import datetime
from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
from godel_core import GodelTerminalController
from commands import DESCommand, GCommand, GIPCommand, QMCommand, PRTCommand

# DEBUG MODE - Set to True to see execution details, False for silent operation
DEBUG = True  # <-- Change to False for production use
#TODO: FIND OUT WHY IT ONLY WORKS WITH DEBUG = TRUE


def debug_print(msg):
    """Print debug messages to stderr (bypasses stdout suppression)"""
    if DEBUG:
        print(f"[DEBUG] {msg}", file=sys.stderr)


def save_output(data, command_type, ticker):
    """Save output to JSON file"""
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    # Handle ticker being a string or list
    ticker_str = ticker if isinstance(ticker, str) else '_'.join(ticker[:3])  # Use first 3 tickers
    output_file = output_dir / f"{command_type.lower()}_{ticker_str}_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    return output_file


def main():
    """CLI main function - outputs only final JSON"""
    
    debug_print("CLI started")
    
    # Get command from arguments or prompt
    if len(sys.argv) > 1:
        # Command passed as argument
        command_input = ' '.join(sys.argv[1:]).strip()
        debug_print(f"Command from args: {command_input}")
    else:
        # Prompt for command
        command_input = input("Enter command: ").strip()
        debug_print(f"Command from input: {command_input}")
    
    if not command_input:
        debug_print("No command provided")
        sys.exit(1)
    
    # Parse command
    parts = command_input.split()
    
    # Check if it's a PRT command (special case: PRT AAPL NVDA MSFT ...)
    if parts[0].upper() == 'PRT':
        command_type = 'PRT'
        tickers = [t.upper() for t in parts[1:]]
        ticker = tickers  # For PRT, ticker is a list
        asset_class = None
        debug_print(f"Parsed PRT - Tickers: {tickers}")
    else:
        # Standard command format: TICKER ASSET COMMAND
        if len(parts) < 3:
            debug_print(f"Invalid command format: {parts}")
            sys.exit(1)
        
        ticker = parts[0].upper()
        asset_class = parts[1].upper()
        command_type = parts[2].upper()
        debug_print(f"Parsed - Ticker: {ticker}, Asset: {asset_class}, Command: {command_type}")
    
    # Command registry
    command_map = {
        'DES': DESCommand,
        'G': GCommand,
        'GIP': GIPCommand,
        'QM': QMCommand,
        'PRT': PRTCommand
    }
    
    if command_type not in command_map:
        debug_print(f"Unknown command type: {command_type}")
        sys.exit(1)
    
    debug_print("Initializing controller...")
    
    # Initialize controller (non-headless required)
    controller = GodelTerminalController(GODEL_URL, headless=False)
    
    # Register the command
    controller.register_command(command_type, command_map[command_type])
    
    debug_print(f"Command '{command_type}' registered")
    
    try:
        # Suppress stdout during execution if not in debug mode
        if not DEBUG:
            old_stdout = sys.stdout
            sys.stdout = open(os.devnull, 'w')
        
        try:
            # Execute
            debug_print("Connecting to browser...")
            controller.connect()
            
            debug_print("Logging in...")
            controller.login(GODEL_USERNAME, GODEL_PASSWORD)
            
            debug_print("Loading dev layout...")
            controller.load_layout("dev")
            
            debug_print("Opening terminal...")
            controller.open_terminal()
            
            # Execute command (now handles both PRT and standard commands)
            if command_type == 'PRT':
                debug_print(f"Executing PRT with tickers: {tickers}")
                result, cmd = controller.execute_command(command_type, ticker=tickers)
            else:
                debug_print(f"Executing command: {ticker} {asset_class} {command_type}")
                result, cmd = controller.execute_command(command_type, ticker, asset_class)
            
            debug_print(f"Command execution result - Success: {result.get('success')}")
        finally:
            # Restore stdout
            if not DEBUG:
                sys.stdout.close()
                sys.stdout = old_stdout
        
        if result['success']:
            debug_print("Saving output...")
            # Save output
            save_output(result, command_type, ticker)
            
            debug_print("Outputting JSON...")
            # Output only the data JSON
            print(json.dumps(result['data'], indent=2))
            
            debug_print("Closing window...")
            # Close window
            cmd.close()
            
            debug_print("Waiting 3 seconds before disconnect...")
            time.sleep(3)
        else:
            debug_print(f"Command failed: {result.get('error')}")
            sys.exit(1)
        
    except Exception as e:
        debug_print(f"Exception occurred: {type(e).__name__}: {e}")
        import traceback
        if DEBUG:
            traceback.print_exc(file=sys.stderr)
        sys.exit(1)
        
    finally:
        debug_print("Disconnecting...")
        controller.disconnect()
        debug_print("CLI finished")


if __name__ == "__main__":
    main() 