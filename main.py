"""
Godel Terminal Main Script
Example usage of the command framework
"""

import json
import os
from datetime import datetime
from pathlib import Path
from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
from godel_core import GodelTerminalController
from commands import DESCommand, GCommand, GIPCommand, QMCommand


def main():
    """Main execution function"""
    
    # Configuration
    TICKER = "ABVX"
    ASSET_CLASS = "EQ"
    
    print("=" * 60)
    print("Godel Terminal Command Framework")
    print("=" * 60)
    
    # Initialize controller
    controller = GodelTerminalController(GODEL_URL, headless=False)
    
    # Register available commands
    controller.register_command('DES', DESCommand)
    controller.register_command('G', GCommand)
    controller.register_command('GIP', GIPCommand)
    controller.register_command('QM', QMCommand)
    
    try:
        # Connect and login
        controller.connect()
        controller.login(GODEL_USERNAME, GODEL_PASSWORD)
        
        # Open terminal
        if not controller.open_terminal():
            print("Failed to open terminal")
            return
        
        # Execute DES command
        result, des_command = controller.execute_command('DES', TICKER, ASSET_CLASS)
        
        # Display results
        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60)
        
        if result['success']:
            # Create output directory if it doesn't exist
            output_dir = Path(__file__).parent / "output"
            output_dir.mkdir(exist_ok=True)
            
            # Save full data to JSON
            output_file = output_dir / f"des_data_{TICKER}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"\n✓ Full data saved to: {output_file}")
            
            # Close the window
            des_command.close()
        else:
            print(f"✗ Command failed: {result.get('error')}")
        
        # Keep browser open for inspection
        print("\n" + "=" * 60)
        input("Press Enter to close browser...")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main() 