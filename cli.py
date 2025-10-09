"""
Godel Terminal CLI
Command-line interface for executing Godel Terminal commands
"""

import json
import sys
import os
import time
import logging
from pathlib import Path
from datetime import datetime
from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
from godel_core import GodelTerminalController
from commands import DESCommand, GCommand, GIPCommand, QMCommand, PRTCommand, MOSTCommand

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set to DEBUG for verbose output, INFO for minimal output
    format='[%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('godel_cli.log'),  # Log to file
        # Uncomment the next line if you want console output too:
        # logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

# You can change log level via environment variable:
# set GODEL_DEBUG=1  (Windows) or export GODEL_DEBUG=1 (Mac/Linux)
if os.environ.get('GODEL_DEBUG', '').lower() in ('1', 'true', 'yes'):
    logger.setLevel(logging.DEBUG)
    # Add console handler for debug mode
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.DEBUG)
    logger.addHandler(console)


def save_output(data, command_type, ticker):
    """Save output to JSON file (and CSV for MOST command)"""
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    # Handle ticker being a string or list
    ticker_str = ticker if isinstance(ticker, str) else '_'.join(ticker[:3])  # Use first 3 tickers
    output_file = output_dir / f"{command_type.lower()}_{ticker_str}_{timestamp}.json"
    
    # For MOST command, remove DataFrame before saving JSON
    if command_type == 'MOST' and 'dataframe' in data:
        data_copy = data.copy()
        df = data_copy.pop('dataframe')
        
        # Save JSON without DataFrame
        with open(output_file, 'w') as f:
            json.dump(data_copy, f, indent=2)
        
        # Also save as CSV
        csv_file = output_dir / f"{command_type.lower()}_{ticker_str}_{timestamp}.csv"
        df.to_csv(csv_file, index=False)
        logger.info(f"Saved CSV to: {csv_file}")
    else:
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    logger.info(f"Saved JSON to: {output_file}")
    return output_file


def main():
    """CLI main function - outputs only final JSON"""
    
    logger.info("CLI started")
    
    # Get command from arguments or prompt
    if len(sys.argv) > 1:
        # Command passed as argument
        command_input = ' '.join(sys.argv[1:]).strip()
        logger.debug(f"Command from args: {command_input}")
    else:
        # Prompt for command
        command_input = input("Enter command: ").strip()
        logger.debug(f"Command from input: {command_input}")
    
    if not command_input:
        logger.error("No command provided")
        sys.exit(1)
    
    # Parse command
    parts = command_input.split()
    
    # Check if it's a PRT command (special case: PRT AAPL NVDA MSFT ...)
    if parts[0].upper() == 'PRT':
        command_type = 'PRT'
        tickers = [t.upper() for t in parts[1:]]
        ticker = tickers  # For PRT, ticker is a list
        asset_class = None
        logger.debug(f"Parsed PRT - Tickers: {tickers}")
    # Check if it's a MOST command (MOST [TAB] [LIMIT])
    elif parts[0].upper() == 'MOST':
        command_type = 'MOST'
        tab = parts[1].upper() if len(parts) > 1 else "ACTIVE"
        limit = int(parts[2]) if len(parts) > 2 else 75
        ticker = tab  # Use tab as ticker for passing
        asset_class = limit  # Use limit as asset_class for passing
        logger.debug(f"Parsed MOST - Tab: {tab}, Limit: {limit}")
    else:
        # Standard command format: TICKER ASSET COMMAND
        if len(parts) < 3:
            logger.error(f"Invalid command format: {parts}")
            sys.exit(1)
        
        ticker = parts[0].upper()
        asset_class = parts[1].upper()
        command_type = parts[2].upper()
        logger.debug(f"Parsed - Ticker: {ticker}, Asset: {asset_class}, Command: {command_type}")
    
    # Command registry
    command_map = {
        'DES': DESCommand,
        'G': GCommand,
        'GIP': GIPCommand,
        'QM': QMCommand,
        'PRT': PRTCommand,
        'MOST': MOSTCommand
    }
    
    if command_type not in command_map:
        logger.error(f"Unknown command type: {command_type}")
        sys.exit(1)
    
    logger.info(f"Initializing controller for {command_type}...")
    
    # Initialize controller (non-headless required)
    controller = GodelTerminalController(GODEL_URL, headless=False)
    
    # Register the command
    controller.register_command(command_type, command_map[command_type])
    
    logger.debug(f"Command '{command_type}' registered")
    
    try:
        # Execute
        logger.info("Connecting to browser...")
        controller.connect()
        
        logger.info("Logging in...")
        controller.login(GODEL_USERNAME, GODEL_PASSWORD)
        
        logger.info("Loading dev layout...")
        controller.load_layout("dev")
        
        logger.info("Opening terminal...")
        controller.open_terminal()
        
        # Execute command (handles PRT, MOST, and standard commands)
        if command_type == 'PRT':
            logger.info(f"Executing PRT with tickers: {tickers}")
            result, cmd = controller.execute_command(command_type, ticker=tickers)
        elif command_type == 'MOST':
            logger.info(f"Executing MOST with tab: {ticker}, limit: {asset_class}")
            result, cmd = controller.execute_command(command_type, ticker, asset_class)
        else:
            logger.info(f"Executing command: {ticker} {asset_class} {command_type}")
            result, cmd = controller.execute_command(command_type, ticker, asset_class)
        
        logger.debug(f"Command execution result - Success: {result.get('success')}")
        
        if result['success']:
            logger.info("Command executed successfully")
            
            # Save output
            save_output(result, command_type, ticker)
            logger.debug("Output saved to file")
            
            # Output only the data JSON to stdout
            # For MOST command, we need to handle DataFrame serialization
            if command_type == 'MOST' and 'dataframe' in result['data']:
                # Remove DataFrame from output (not JSON serializable)
                output_data = result['data'].copy()
                del output_data['dataframe']
                print(json.dumps(output_data, indent=2))
            else:
                print(json.dumps(result['data'], indent=2))
            
            logger.debug("Closing window...")
            # Close window
            cmd.close()
            
            logger.debug("Waiting before disconnect...")
            time.sleep(3)
        else:
            logger.error(f"Command failed: {result.get('error')}")
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Exception occurred: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    finally:
        logger.info("Disconnecting...")
        controller.disconnect()
        logger.info("CLI finished")


if __name__ == "__main__":
    main() 