"""
Working multi-instance chat monitor for Godel Terminal
Monitors #general, #biotech, #paid channels simultaneously
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from godel_core import GodelManager, GodelSession
from commands.chat_monitor_v2 import ChatMonitorV2
from db import get_db, close_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("godel.working_multichat")


class WorkingMultiChat:
    """Multi-instance chat monitor that actually works."""
    
    def __init__(self, channels: List[str], duration: int = 60):
        self.channels = channels
        self.duration = duration
        self.manager: Optional[GodelManager] = None
        self.sessions = {}
        self.monitors = {}
        self.all_messages = []
        
    async def run(self):
        """Run multi-channel monitoring."""
        logger.info(f"Starting multi-chat for channels: {self.channels}")
        
        # Create manager
        self.manager = GodelManager(
            headless=False,
            background=True,
            url="https://app.godelterminal.com"
        )
        await self.manager.start()
        logger.info("✓ Manager started")
        
        # Create and login to all sessions SEQUENTIALLY to avoid conflicts
        from config import GODEL_USERNAME, GODEL_PASSWORD
        
        for channel in self.channels:
            await self._create_and_login_session(channel, GODEL_USERNAME, GODEL_PASSWORD)
            # Small delay between logins to avoid rate limiting
            await asyncio.sleep(2)
        
        logger.info(f"✓ Logged into {len(self.sessions)} sessions")
        
        # Open chat channels for all sessions
        channel_tasks = []
        for channel in self.channels:
            if channel in self.sessions:
                task = self._open_channel(self.sessions[channel], channel)
                channel_tasks.append(task)
        
        await asyncio.gather(*channel_tasks, return_exceptions=True)
        logger.info("✓ Opened all chat channels")
        
        # Start monitoring all channels
        monitor_tasks = []
        for channel in self.channels:
            if channel in self.sessions:
                task = self._monitor_channel(channel)
                monitor_tasks.append(task)
        
        # Run all monitors concurrently for the specified duration
        logger.info(f"Monitoring for {self.duration} seconds...")
        try:
            await asyncio.wait_for(
                asyncio.gather(*monitor_tasks, return_exceptions=True),
                timeout=self.duration
            )
        except asyncio.TimeoutError:
            logger.info("Monitoring complete (timeout)")
        
        # Shutdown
        await self.shutdown()
        
        # Return results
        return {
            "channels": self.channels,
            "total_messages": len(self.all_messages),
            "messages": self.all_messages[:50]  # First 50 messages
        }
    
    async def _create_and_login_session(self, channel: str, username: str, password: str):
        """Create and login a session for a channel."""
        try:
            session_id = f"chat_{channel}"
            session = await self.manager.create_session(session_id)
            await session.init_page()
            await session.login(username, password)
            await session.load_layout("dev")
            self.sessions[channel] = session
            logger.info(f"✓ Session ready for #{channel}")
        except Exception as e:
            logger.error(f"✗ Failed to create session for #{channel}: {e}")
    
    async def _open_channel(self, session: GodelSession, channel: str):
        """Open a specific chat channel by clicking in the sidebar."""
        try:
            logger.info(f"Opening #{channel}...")
            
            # Click CHAT button to ensure chat is open
            try:
                chat_btn = session.page.locator("button:has-text('CHAT')").first
                if await chat_btn.count() > 0:
                    await chat_btn.click()
                    await asyncio.sleep(1)
            except:
                pass
            
            # Click Public Channels to expand
            try:
                public_channels = session.page.locator("text=Public Channels").first
                if await public_channels.count() > 0:
                    text = await public_channels.text_content()
                    if "▶" in text or "►" in text:
                        await public_channels.click()
                        await asyncio.sleep(1)
                        logger.info(f"  ✓ Expanded Public Channels for #{channel}")
            except Exception as e:
                logger.debug(f"Could not expand Public Channels: {e}")
            
            # Click the specific channel
            channel_elem = session.page.locator(f"text=#{channel}").first
            if await channel_elem.count() > 0:
                await channel_elem.click()
                await asyncio.sleep(2)
                logger.info(f"  ✓ Clicked on #{channel}")
            else:
                logger.warning(f"  ✗ Could not find #{channel}")
                
        except Exception as e:
            logger.error(f"  ✗ Error opening #{channel}: {e}")
    
    async def _monitor_channel(self, channel: str):
        """Monitor a single channel for messages."""
        session = self.sessions.get(channel)
        if not session:
            return
        
        logger.info(f"Starting monitor for #{channel}")
        
        # Get database connection
        db = await get_db()
        
        # Start WebSocket monitoring
        monitor = ChatMonitorV2(session, channels=[channel])
        self.monitors[channel] = monitor
        
        # Run WebSocket monitor
        ws_task = asyncio.create_task(monitor.start())
        
        # Also poll DOM for messages
        last_message_count = 0
        seen_contents = set()  # Track seen message contents to avoid duplicates
        
        while True:
            try:
                # Extract messages from DOM
                messages = await self._extract_messages_from_dom(session, channel)
                
                # Store new messages
                for msg in messages:
                    # Create unique key for deduplication
                    msg_key = f"{msg['channel']}:{msg['sender']}:{msg['content'][:50]}"
                    
                    if msg_key not in seen_contents:
                        seen_contents.add(msg_key)
                        self.all_messages.append(msg)
                        
                        # Save to database
                        try:
                            await db.save_message(
                                channel=msg['channel'],
                                sender=msg['sender'],
                                content=msg['content'],
                                timestamp=datetime.now(timezone.utc),
                                raw_data=json.dumps(msg)
                            )
                        except Exception as e:
                            logger.error(f"Failed to save message to DB: {e}")
                
                if len(messages) != last_message_count:
                    last_message_count = len(messages)
                    logger.info(f"  #{channel}: {len(messages)} messages in DOM, {len(seen_contents)} unique")
                
                await asyncio.sleep(2)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring #{channel}: {e}")
                await asyncio.sleep(2)
    
    async def _extract_messages_from_dom(self, session: GodelSession, channel: str) -> List[dict]:
        """Extract chat messages from the DOM."""
        messages = []
        
        try:
            # Try different selectors for message elements
            selectors = [
                ".message",
                ".chat-message",
                "[class*='message']",
                ".message-content",
                ".msg",
            ]
            
            for selector in selectors:
                try:
                    msg_elems = session.page.locator(selector)
                    count = await msg_elems.count()
                    
                    if count > 0:
                        for i in range(count):
                            try:
                                elem = msg_elems.nth(i)
                                text = await elem.text_content()
                                
                                # Try to extract sender
                                sender = "unknown"
                                try:
                                    # Look for username nearby
                                    parent = elem.locator("..")
                                    user_elem = parent.locator("[class*='user'], [class*='name'], [class*='author]").first
                                    if await user_elem.count() > 0:
                                        sender = await user_elem.text_content()
                                except:
                                    pass
                                
                                if text and len(text) > 0:
                                    messages.append({
                                        "channel": channel,
                                        "sender": sender,
                                        "content": text,
                                        "timestamp": datetime.now(timezone.utc).isoformat(),
                                        "source": "dom"
                                    })
                            except:
                                pass
                        break  # Found messages with this selector
                        
                except:
                    continue
                    
        except Exception as e:
            logger.error(f"Error extracting messages from DOM: {e}")
        
        return messages
    
    async def shutdown(self):
        """Clean up all resources."""
        logger.info("Shutting down...")
        
        for monitor in self.monitors.values():
            monitor.stop()
        
        await asyncio.sleep(1)
        
        if self.manager:
            await self.manager.shutdown()
        
        await close_db()
        logger.info("✓ Shutdown complete")


async def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor multiple Godel chat channels")
    parser.add_argument("--channels", "-c", default="general,biotech,paid",
                       help="Comma-separated channel names")
    parser.add_argument("--duration", "-d", type=int, default=60,
                       help="Monitoring duration in seconds")
    
    args = parser.parse_args()
    
    channels = [c.strip() for c in args.channels.split(",")]
    
    monitor = WorkingMultiChat(channels=channels, duration=args.duration)
    
    try:
        results = await monitor.run()
        print("\n" + "="*60)
        print("MULTI-CHAT RESULTS")
        print("="*60)
        print(json.dumps(results, indent=2))
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")


if __name__ == "__main__":
    asyncio.run(main())
