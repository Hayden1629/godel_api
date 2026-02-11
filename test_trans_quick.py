"""
Test TRAN (Transcripts) command
"""

import asyncio
from godel_core import GodelManager
from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD

async def test_trans():
    manager = GodelManager(headless=False, background=True, url=GODEL_URL)
    await manager.start()
    
    session = await manager.create_session('trans_test')
    await session.init_page()
    await session.login(GODEL_USERNAME, GODEL_PASSWORD)
    await session.load_layout('dev')
    
    print("✓ Logged in")
    await asyncio.sleep(2)
    
    print("\nTesting: AAPL EQ TRAN")
    windows_before = len(await session.get_current_windows())
    await session.send_command("AAPL EQ TRAN")
    await asyncio.sleep(4)
    windows_after = len(await session.get_current_windows())
    
    if windows_after > windows_before:
        print("✅ TRAN command works!")
        await session.screenshot("output/trans_test.png")
        new_win = (await session.get_current_windows())[-1]
        text = await new_win.text_content()
        print(f"Content: {text[:400]}...")
    else:
        print("❌ TRAN command failed")
    
    await manager.shutdown()

asyncio.run(test_trans())
