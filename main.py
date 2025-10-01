"""
Godel Terminal Debug Script
Non-headless mode for debugging with browser visible
"""

import json
import time
from pathlib import Path
from datetime import datetime
from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
from godel_core import GodelTerminalController
from commands import DESCommand


def main():
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


if __name__ == "__main__":
    main() 