"""
Debug test for RES command - understand window creation
"""

import asyncio
from godel_core import GodelManager

async def test_res_command():
    """Test RES command window creation."""
    
    from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
    
    manager = GodelManager(headless=False, background=True, url=GODEL_URL)
    await manager.start()
    
    session = await manager.create_session("test")
    await session.init_page()
    await session.login(GODEL_USERNAME, GODEL_PASSWORD)
    await session.load_layout("dev")
    
    print("✓ Logged in")
    await session.page.wait_for_timeout(2000)
    
    # Count windows before
    windows_before = await session.get_current_windows()
    print(f"Windows before: {len(windows_before)}")
    
    # Send RES command
    print("\nSending RES command for AAPL...")
    await session.send_command("AAPL EQ RES")
    
    # Wait and take screenshots
    for i in range(10):
        await session.page.wait_for_timeout(1000)
        windows = await session.get_current_windows()
        print(f"  After {i+1}s: {len(windows)} windows")
        
        if len(windows) > len(windows_before):
            print(f"  ✓ New window detected!")
            new_win = windows[-1]
            win_id = await new_win.get_attribute("id")
            print(f"  Window ID: {win_id}")
            
            # Take screenshot
            await session.screenshot(f"output/res_window_{i}.png")
            print(f"  ✓ Screenshot saved")
            
            # Try to see what's in the window
            text = await new_win.text_content()
            print(f"  Content preview: {text[:200]}...")
            break
    else:
        print("  ✗ No new window appeared after 10s")
        await session.screenshot("output/res_no_window.png")
    
    await manager.shutdown()
    print("\n✓ Test complete")

if __name__ == "__main__":
    asyncio.run(test_res_command())
