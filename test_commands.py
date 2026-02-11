"""
Test various Godel Terminal commands to see which ones work
"""

import asyncio
from godel_core import GodelManager
from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD

async def test_command(cmd_str):
    """Test a single command."""
    manager = GodelManager(headless=False, background=True, url=GODEL_URL)
    await manager.start()
    
    try:
        session = await manager.create_session('test')
        await session.init_page()
        await session.login(GODEL_USERNAME, GODEL_PASSWORD)
        await session.load_layout('dev')
        
        windows_before = len(await session.get_current_windows())
        await session.send_command(cmd_str)
        await asyncio.sleep(3)
        windows_after = len(await session.get_current_windows())
        
        success = windows_after > windows_before
        return success
    finally:
        await manager.shutdown()

async def main():
    commands = [
        'FA AAPL',      # Financial Analysis
        'ANR AAPL',     # Analyst Recommendations  
        'HMS AAPL',     # Historical Multiples
        'SI AAPL',      # Short Interest
        'TOP',          # Top movers
        'WEI AAPL',     # Weighted exposure
        'TAS AAPL',     # Time & Sales
        'FOCUS AAPL',   # Focus
        'HDS AAPL',     # Holders
    ]
    
    print("Testing Godel Terminal commands:\n")
    for cmd in commands:
        try:
            result = await test_command(cmd)
            status = "✅" if result else "❌"
            print(f"{cmd:15} {status}")
        except Exception as e:
            print(f"{cmd:15} ❌ ({str(e)[:40]})")

if __name__ == "__main__":
    asyncio.run(main())
