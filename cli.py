"""
Godel Terminal CLI
Command-line interface for executing Godel Terminal commands
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
from godel_core import GodelTerminalController
from commands import DESCommand, GCommand, GIPCommand, QMCommand


def save_output(data, command_type, ticker):
    """Save output to JSON file"""
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f"{command_type.lower()}_{ticker}_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    return output_file


def main():
    """CLI main function - outputs only final JSON"""
    
    # Get command from user
    command_input = input("Enter command: ").strip()
    
    if not command_input:
        sys.exit(1)
    
    # Parse command
    parts = command_input.split()
    if len(parts) < 3:
        sys.exit(1)
    
    ticker = parts[0].upper()
    asset_class = parts[1].upper()
    command_type = parts[2].upper()
    
    # Command registry
    command_map = {
        'DES': DESCommand,
        'G': GCommand,
        'GIP': GIPCommand,
        'QM': QMCommand
    }
    
    if command_type not in command_map:
        sys.exit(1)
    
    # Suppress output from controller
    sys.stdout = open(os.devnull, 'w')
    
    # Initialize controller (non-headless required)
    controller = GodelTerminalController(GODEL_URL, headless=False)
    controller.register_command(command_type, command_map[command_type])
    
    try:
        # Execute
        controller.connect()
        controller.login(GODEL_USERNAME, GODEL_PASSWORD)
        controller.open_terminal()
        result, cmd = controller.execute_command(command_type, ticker, asset_class)
        
        # Restore stdout
        sys.stdout = sys.__stdout__
        
        if result['success']:
            # Save output
            save_output(result, command_type, ticker)
            
            # Output only the data JSON
            print(json.dumps(result['data'], indent=2))
            
            # Close window
            cmd.close()
        else:
            sys.exit(1)
        
    except Exception:
        sys.stdout = sys.__stdout__
        sys.exit(1)
        
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main() 