"""
Simple test: Can we click on chat channels and see messages?
"""

import asyncio
from godel_core import GodelManager

async def simple_channel_test():
    """Test clicking chat channels and monitoring for messages."""
    
    from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
    
    manager = GodelManager(headless=False, background=True, url=GODEL_URL)
    await manager.start()
    
    session = await manager.create_session("test")
    await session.init_page()
    await session.login(GODEL_USERNAME, GODEL_PASSWORD)
    await session.load_layout("dev")
    
    print("✓ Logged in")
    await session.page.wait_for_timeout(3000)
    
    # Ensure chat is open
    try:
        chat_btn = session.page.locator("button:has-text('CHAT')").first
        if await chat_btn.count() > 0:
            await chat_btn.click()
            print("✓ Opened CHAT")
            await session.page.wait_for_timeout(2000)
    except:
        pass
    
    # Expand Public Channels
    try:
        public_channels = session.page.locator("text=Public Channels").first
        if await public_channels.count() > 0:
            text = await public_channels.text_content()
            print(f"✓ Found Public Channels: {text[:50]}")
            if "▶" in text or "►" in text:
                await public_channels.click()
                print("✓ Expanded Public Channels")
                await session.page.wait_for_timeout(2000)
    except Exception as e:
        print(f"✗ Could not expand Public Channels: {e}")
    
    # Now try to find and click #general
    print("\nLooking for #general...")
    try:
        # Try different selectors
        selectors = [
            "text=#general",
            ".channel:has-text('general')",
            "[data-channel='general']",
            ".sidebar >> text=general",
        ]
        
        for sel in selectors:
            try:
                elem = session.page.locator(sel).first
                count = await elem.count()
                if count > 0:
                    print(f"  ✓ Found with selector: {sel}")
                    await elem.click()
                    print(f"  ✓ Clicked #general")
                    await session.page.wait_for_timeout(3000)
                    
                    # Take screenshot
                    await session.screenshot("output/general_channel.png")
                    print("  ✓ Screenshot saved")
                    break
            except Exception as e:
                print(f"  ✗ {sel}: {e}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Wait and monitor for messages
    print("\nMonitoring for 30 seconds...")
    await session.page.wait_for_timeout(30000)
    
    # Try to read messages from DOM
    print("\nTrying to read messages from DOM...")
    try:
        msg_selectors = [
            ".message",
            ".chat-message",
            "[class*='message']",
            ".message-content",
            ".msg",
        ]
        
        for sel in msg_selectors:
            try:
                msgs = session.page.locator(sel)
                count = await msgs.count()
                if count > 0:
                    print(f"  ✓ Found {count} messages with '{sel}'")
                    for i in range(min(3, count)):
                        text = await msgs.nth(i).text_content()
                        print(f"    - {text[:100]}...")
                    break
            except:
                pass
        else:
            print("  ✗ No messages found in DOM")
    except Exception as e:
        print(f"  ✗ Error: {e}")
    
    await manager.shutdown()
    print("\n✓ Test complete")

if __name__ == "__main__":
    asyncio.run(simple_channel_test())
