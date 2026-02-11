"""
Quick test to validate chat channel clicking works
"""

import asyncio
import sys
from godel_core import GodelManager

async def test_chat_channels():
    """Test clicking on chat channels."""
    
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
    
    # Take initial screenshot
    await session.screenshot("output/before_chat.png")
    print("✓ Screenshot before: output/before_chat.png")
    
    # Try clicking on chat channels
    channels = ["general", "biotech", "paid"]
    
    for channel in channels:
        print(f"\nTrying to click on #{channel}...")
        try:
            # Look for the channel in the sidebar
            channel_elem = session.page.locator(f"text=#{channel}").first
            count = await channel_elem.count()
            
            if count > 0:
                print(f"  ✓ Found channel element")
                visible = await channel_elem.is_visible()
                print(f"  ✓ Visible: {visible}")
                
                if visible:
                    await channel_elem.click()
                    print(f"  ✓ Clicked on #{channel}")
                    await session.page.wait_for_timeout(2000)
                    
                    # Take screenshot
                    await session.screenshot(f"output/chat_{channel}.png")
                    print(f"  ✓ Screenshot saved: output/chat_{channel}.png")
                    
                    # Check for messages
                    msg_selectors = [
                        ".message",
                        ".chat-message", 
                        "[class*='message']",
                        ".message-content",
                    ]
                    
                    for sel in msg_selectors:
                        try:
                            msgs = session.page.locator(sel)
                            msg_count = await msgs.count()
                            if msg_count > 0:
                                print(f"  ✓ Found {msg_count} messages with selector: {sel}")
                                # Print first few messages
                                for i in range(min(3, msg_count)):
                                    text = await msgs.nth(i).text_content()
                                    print(f"    - {text[:80]}...")
                                break
                        except:
                            continue
                    else:
                        print(f"  ⚠ No messages found (channel might be empty)")
            else:
                print(f"  ✗ Channel #{channel} not found")
                
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    await manager.shutdown()
    print("\n✓ Test complete")

if __name__ == "__main__":
    asyncio.run(test_chat_channels())
