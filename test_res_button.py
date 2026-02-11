"""
Test clicking RES button directly
"""

import asyncio
from godel_core import GodelManager

async def test_res_button():
    """Test clicking RES button."""
    
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
    
    # Try clicking RES button
    print("\nClicking RES button...")
    try:
        res_btn = session.page.locator("button:has-text('RES')").first
        if await res_btn.count() > 0:
            await res_btn.click()
            print("✓ Clicked RES button")
        else:
            print("✗ RES button not found")
    except Exception as e:
        print(f"✗ Error clicking RES: {e}")
    
    # Wait and check for windows
    await session.page.wait_for_timeout(3000)
    windows_after = await session.get_current_windows()
    print(f"Windows after: {len(windows_after)}")
    
    if len(windows_after) > len(windows_before):
        new_win = windows_after[-1]
        win_id = await new_win.get_attribute("id")
        print(f"✓ New window: {win_id}")
        
        # Screenshot
        await session.screenshot("output/res_button_click.png")
        
        # Get content
        text = await new_win.text_content()
        print(f"Content: {text[:300]}...")
    else:
        print("✗ No new window")
        await session.screenshot("output/res_no_button.png")
    
    await manager.shutdown()
    print("\n✓ Test complete")

if __name__ == "__main__":
    asyncio.run(test_res_button())
