"""
Simplified Multi-Channel Chat Monitor using DOM extraction
"""

import asyncio
import logging
import sys
from typing import List

from godel_core import GodelManager, GodelSession
from dom_chat_monitor import DOMChatMonitor
from db import close_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("godel.simple_multichat")


async def monitor_channel(manager: GodelManager, channel: str, username: str, password: str, duration: int):
    """Monitor a single channel."""
    logger.info(f"Setting up monitor for #{channel}")
    
    # Create session
    session = await manager.create_session(f"chat_{channel}")
    await session.init_page()
    await session.login(username, password)
    await session.load_layout("dev")
    
    logger.info(f"✓ Logged in for #{channel}")
    await session.page.wait_for_timeout(2000)
    
    # Open chat
    try:
        chat_btn = session.page.locator("button:has-text('CHAT')").first
        if await chat_btn.count() > 0:
            await chat_btn.click()
            logger.info(f"✓ Opened CHAT for #{channel}")
            await session.page.wait_for_timeout(2000)
    except:
        pass
    
    # Expand Public Channels
    try:
        public_channels = session.page.locator("text=Public Channels").first
        if await public_channels.count() > 0:
            parent = public_channels.locator("..")
            if await parent.count() > 0:
                await parent.click()
                logger.info(f"✓ Expanded Public Channels for #{channel}")
                await session.page.wait_for_timeout(2000)
    except Exception as e:
        logger.warning(f"Could not expand Public Channels: {e}")
    
    # Click the channel
    try:
        channel_elem = session.page.locator(f"text=#{channel}").first
        if await channel_elem.count() > 0:
            await channel_elem.click()
            logger.info(f"✓ Clicked on #{channel}")
            await session.page.wait_for_timeout(3000)
    except Exception as e:
        logger.error(f"Could not click #{channel}: {e}")
        return {"channel": channel, "messages": 0, "error": str(e)}
    
    # Start DOM-based monitoring
    monitor = DOMChatMonitor(session, channel)
    
    try:
        await monitor.start(duration=duration, poll_interval=3.0)
    except Exception as e:
        logger.error(f"Monitor error for {channel}: {e}")
    
    return {
        "channel": channel,
        "messages": monitor.message_count,
    }


async def main():
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--channels", "-c", default="general,biotech,paid")
    parser.add_argument("--duration", "-d", type=int, default=60)
    parser.add_argument("--background", "-bg", action="store_true", default=True)
    parser.add_argument("--visible", action="store_true")
    args = parser.parse_args()
    
    from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
    
    channels = [c.strip() for c in args.channels.split(",")]
    background = not args.visible if args.visible else args.background
    
    # Create single manager for all sessions
    manager = GodelManager(headless=False, background=background, url=GODEL_URL)
    await manager.start()
    
    logger.info(f"Starting multi-channel monitoring: {channels}")
    
    try:
        # Monitor all channels concurrently
        tasks = [
            monitor_channel(manager, channel, GODEL_USERNAME, GODEL_PASSWORD, args.duration)
            for channel in channels
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Print summary
        print("\n" + "="*50)
        print("MONITORING COMPLETE")
        print("="*50)
        
        total_messages = 0
        for result in results:
            if isinstance(result, dict):
                channel = result.get("channel", "unknown")
                messages = result.get("messages", 0)
                total_messages += messages
                print(f"#{channel}: {messages} messages")
            else:
                print(f"Error: {result}")
        
        print(f"\nTotal: {total_messages} messages from {len(channels)} channels")
        
    finally:
        await manager.shutdown()
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
