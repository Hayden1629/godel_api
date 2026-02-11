"""
Quick test of FA command (Financial Analysis)
"""

import asyncio
from godel_core import GodelManager

async def test_fa():
    from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
    
    manager = GodelManager(headless=False, background=True, url=GODEL_URL)
    await manager.start()
    
    session = await manager.create_session('test')
    await session.init_page()
    await session.login(GODEL_USERNAME, GODEL_PASSWORD)
    await session.load_layout('dev')
    
    print("✓ Logged in")
    await asyncio.sleep(2)
    
    # Test FA AAPL
    print("\nTesting: FA AAPL")
    windows_before = len(await session.get_current_windows())
    await session.send_command("AAPL EQ FA")
    await asyncio.sleep(3)
    windows_after = len(await session.get_current_windows())
    
    if windows_after > windows_before:
        print("✅ FA command works!")
        await session.screenshot("output/fa_aapl.png")
    else:
        print("❌ FA command failed")
    
    await manager.shutdown()

if __name__ == "__main__":
    asyncio.run(test_fa())
