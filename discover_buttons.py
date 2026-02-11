"""
Discover available buttons in Godel Terminal
"""

import asyncio
from godel_core import GodelManager

async def discover_buttons():
    """Find all buttons in the top bar."""
    
    from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
    
    manager = GodelManager(headless=False, background=True, url=GODEL_URL)
    await manager.start()
    
    session = await manager.create_session("test")
    await session.init_page()
    await session.login(GODEL_USERNAME, GODEL_PASSWORD)
    await session.load_layout("dev")
    
    print("✓ Logged in")
    await session.page.wait_for_timeout(2000)
    
    # Take screenshot
    await session.screenshot("output/buttons_overview.png")
    print("✓ Screenshot saved")
    
    # Find all buttons
    print("\nFinding all buttons...")
    buttons = await session.page.locator("button").all()
    print(f"Found {len(buttons)} buttons")
    
    for i, btn in enumerate(buttons[:30]):  # First 30
        try:
            text = await btn.text_content()
            visible = await btn.is_visible()
            if text and len(text.strip()) > 0:
                print(f"  [{i}] '{text.strip()}' (visible={visible})")
        except:
            pass
    
    # Find buttons with specific text patterns
    print("\nLooking for RES-related elements...")
    for text in ["RES", "Research", "PDF", "Download", "Docs"]:
        elems = await session.page.locator(f"text={text}").all()
        print(f"  '{text}': {len(elems)} elements")
    
    await manager.shutdown()
    print("\n✓ Discovery complete")

if __name__ == "__main__":
    asyncio.run(discover_buttons())
