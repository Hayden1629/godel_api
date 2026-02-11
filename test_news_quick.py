"""
Test N (News) command
"""

import asyncio
from godel_core import GodelManager
from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD

async def test_news():
    manager = GodelManager(headless=False, background=True, url=GODEL_URL)
    await manager.start()
    
    session = await manager.create_session('news_test')
    await session.init_page()
    await session.login(GODEL_USERNAME, GODEL_PASSWORD)
    await session.load_layout('dev')
    
    print("✓ Logged in")
    await asyncio.sleep(2)
    
    # Try different formats
    commands = ["AAPL N", "AAPL EQ N", "N AAPL"]
    
    for cmd in commands:
        print(f"\nTesting: {cmd}")
        windows_before = len(await session.get_current_windows())
        await session.send_command(cmd)
        await asyncio.sleep(4)
        windows_after = len(await session.get_current_windows())
        
        if windows_after > windows_before:
            print(f"✅ News works with: {cmd}")
            await session.screenshot(f"output/news_{cmd.replace(' ', '_')}.png")
            new_win = (await session.get_current_windows())[-1]
            text = await new_win.text_content()
            print(f"Content: {text[:400]}...")
            break
    else:
        print("❌ News command failed - all formats tried")
    
    await manager.shutdown()

asyncio.run(test_news())
