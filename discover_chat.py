"""
Test to discover chat channel UI structure
"""

import asyncio
import sys
from godel_core import GodelManager

async def discover_chat_ui():
    """Discover how to access chat channels."""
    
    try:
        from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
    except ImportError:
        print("config.py not found")
        return
    
    manager = GodelManager(headless=False, background=True, url=GODEL_URL)
    await manager.start()
    
    session = await manager.create_session("test")
    await session.init_page()
    await session.login(GODEL_USERNAME, GODEL_PASSWORD)
    await session.load_layout("dev")
    
    print("✓ Logged in")
    await session.page.wait_for_timeout(3000)
    
    # Take initial screenshot
    await session.screenshot("output/discover_initial.png")
    print("✓ Initial screenshot saved")
    
    # Try clicking CHAT button at top to ensure chat is open
    print("\nClicking CHAT button...")
    try:
        chat_btn = session.page.locator("button:has-text('CHAT')").first
        if await chat_btn.count() > 0:
            await chat_btn.click()
            print("  ✓ Clicked CHAT button")
            await session.page.wait_for_timeout(2000)
    except Exception as e:
        print(f"  ✗ Could not click CHAT: {e}")
    
    # Try clicking the Chat sidebar/header
    print("\nTrying to expand chat sidebar...")
    try:
        # Look for "Public Channels" or channel list headers
        headers = ["Public Channels", "DMs / Groups", "Channels"]
        for header in headers:
            try:
                elem = session.page.locator(f"text={header}").first
                if await elem.count() > 0:
                    print(f"  ✓ Found header: {header}")
                    await elem.click()
                    print(f"  ✓ Clicked {header}")
                    await session.page.wait_for_timeout(1000)
            except:
                pass
    except Exception as e:
        print(f"  ✗ Error: {e}")
    
    # List all text on the left side of chat window
    print("\nScanning chat sidebar for text elements...")
    try:
        # Get all text elements in the left sidebar area
        text_elems = await session.page.locator(".chat-sidebar >> text").all()
        print(f"  Found {len(text_elems)} text elements")
        
        # Or try broader selector
        all_text = await session.page.locator("text").all()
        print(f"  Total text elements on page: {len(all_text)}")
        
        # Print text content of elements that look like channels
        for elem in all_text[:30]:  # First 30
            try:
                text = await elem.text_content()
                if text and ("#" in text or "general" in text.lower() or "biotech" in text.lower()):
                    print(f"    - '{text}'")
            except:
                pass
    except Exception as e:
        print(f"  ✗ Error scanning: {e}")
    
    # Try different selectors for channels
    print("\nTrying different channel selectors...")
    selectors = [
        "text=#general",
        "text=#biotech", 
        "text=#paid",
        ".channel",
        ".chat-channel",
        "[class*='channel']",
        ".sidebar >> text",
        ".channels >> text",
        "[role='listitem']",
        "button:has-text('#')",
    ]
    
    for selector in selectors:
        try:
            elems = session.page.locator(selector)
            count = await elems.count()
            if count > 0:
                print(f"  ✓ {selector}: {count} elements")
                # Show first few
                for i in range(min(3, count)):
                    text = await elems.nth(i).text_content()
                    print(f"      - '{text}'")
            else:
                print(f"  ✗ {selector}: 0 elements")
        except Exception as e:
            print(f"  ✗ {selector}: error - {e}")
    
    # Take final screenshot
    await session.screenshot("output/discover_final.png")
    print("\n✓ Final screenshot: output/discover_final.png")
    
    await manager.shutdown()
    print("✓ Discovery complete")

if __name__ == "__main__":
    asyncio.run(discover_chat_ui())
