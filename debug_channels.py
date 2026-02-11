"""
Debug script to understand Public Channels expansion
"""

import asyncio
from godel_core import GodelManager

async def debug_public_channels():
    """Debug Public Channels expansion."""
    
    from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
    
    manager = GodelManager(headless=False, background=True, url=GODEL_URL)
    await manager.start()
    
    session = await manager.create_session("debug")
    await session.init_page()
    await session.login(GODEL_USERNAME, GODEL_PASSWORD)
    await session.load_layout("dev")
    
    print("✓ Logged in")
    await session.page.wait_for_timeout(3000)
    
    # Open CHAT
    try:
        chat_btn = session.page.locator("button:has-text('CHAT')").first
        await chat_btn.click()
        print("✓ Clicked CHAT")
    except Exception as e:
        print(f"CHAT button error: {e}")
    
    await session.page.wait_for_timeout(2000)
    await session.screenshot("output/debug_01_after_chat.png")
    
    # Look for Public Channels with different selectors
    selectors = [
        "text=Public Channels",
        "text=PUBLIC CHANNELS",
        "text=public channels",
        "[class*='public']",
        "[class*='channel']",
        ".sidebar >> text",
    ]
    
    print("\nSearching for Public Channels...")
    for sel in selectors:
        try:
            elems = session.page.locator(sel)
            count = await elems.count()
            if count > 0:
                print(f"  ✓ {sel}: {count} elements")
                for i in range(min(3, count)):
                    try:
                        text = await elems.nth(i).text_content()
                        visible = await elems.nth(i).is_visible()
                        print(f"      [{i}] '{text}' (visible={visible})")
                    except:
                        pass
        except Exception as e:
            print(f"  ✗ {sel}: {e}")
    
    # Try to find the expand arrow or clickable element
    print("\nTrying to find and click Public Channels...")
    try:
        # Look for element containing "Public Channels" text
        pc_elem = session.page.locator("text=Public Channels").first
        if await pc_elem.count() > 0:
            # Get parent element
            parent = pc_elem.locator("..")
            print(f"  Found Public Channels element")
            
            # Click the parent (might be the row with arrow)
            await parent.click()
            print("  ✓ Clicked parent of Public Channels")
            await session.page.wait_for_timeout(2000)
            
            await session.screenshot("output/debug_02_after_expand.png")
            
            # Now look for #general etc
            print("\nLooking for channels after expand...")
            channel_elems = session.page.locator("text=#general")
            count = await channel_elems.count()
            print(f"  #general elements found: {count}")
            
            if count > 0:
                await channel_elems.first.click()
                print("  ✓ Clicked #general")
                await session.page.wait_for_timeout(2000)
                await session.screenshot("output/debug_03_general.png")
    except Exception as e:
        print(f"  Error: {e}")
    
    await manager.shutdown()
    print("\n✓ Debug complete")

if __name__ == "__main__":
    asyncio.run(debug_public_channels())
