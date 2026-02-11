"""
Test script to discover chat functionality in Godel Terminal
"""

import asyncio
import sys
from godel_core import GodelManager

async def test_chat_commands():
    """Test various ways to open chat in Godel Terminal."""
    
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
    
    print("✓ Logged in successfully")
    
    # Try to find chat UI elements
    print("\nSearching for chat UI elements...")
    
    selectors = [
        "button:has-text('Chat')",
        "a:has-text('Chat')",
        "[data-testid='chat']",
        "text=Chat",
        "button:has-text('chat')",
        "a:has-text('chat')",
        "#chat",
        ".chat",
        "[href*='chat']",
        "button svg[data-icon='message']",
        "button svg[data-icon='comment']",
    ]
    
    for selector in selectors:
        try:
            elem = session.page.locator(selector).first
            count = await elem.count()
            if count > 0:
                visible = await elem.is_visible()
                text = await elem.text_content()
                print(f"  ✓ Found: {selector} - visible={visible}, text='{text[:30]}...'")
        except Exception as e:
            print(f"  ✗ {selector}: {e}")
    
    # Try chat commands
    print("\nTrying chat commands...")
    commands = [
        "CHAT",
        "CHAT #general",
        "chat",
        "chat general",
        "/chat",
        "/join #general",
        "MSG",
        "IM",
    ]
    
    for cmd in commands:
        try:
            print(f"\n  Trying: {cmd}")
            await session.send_command(cmd)
            await session.page.wait_for_timeout(3000)
            
            # Check what windows opened
            windows = await session.get_current_windows()
            print(f"    Windows open: {len(windows)}")
            
            for i, win in enumerate(windows[-3:]):  # Check last 3 windows
                try:
                    win_id = await win.get_attribute("id")
                    title_elem = win.locator(".window-title, .title, h1, h2, h3").first
                    title = await title_elem.text_content() if await title_elem.count() > 0 else "no title"
                    print(f"      Window {i}: id={win_id}, title='{title[:40]}...'")
                except:
                    pass
                    
        except Exception as e:
            print(f"    Error: {e}")
    
    # Take screenshot
    await session.screenshot("output/chat_test.png")
    print("\n✓ Screenshot saved to output/chat_test.png")
    
    await manager.shutdown()
    print("\n✓ Test complete")

if __name__ == "__main__":
    asyncio.run(test_chat_commands())
