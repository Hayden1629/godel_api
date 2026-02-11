"""
Multi-Instance Chat Monitor for Godel Terminal
Runs multiple chat monitoring sessions simultaneously, one per channel.
"""

import asyncio
import json
import logging
import sys
from typing import List, Optional

from godel_core import GodelManager, GodelSession
from commands import ChatMonitor, ChatMonitorV2
from db import get_db, close_db

logger = logging.getLogger("godel.multi_chat")


class MultiChannelChatMonitor:
    """Monitor multiple chat channels simultaneously using separate sessions."""
    
    def __init__(self, channels: List[str], duration: Optional[int] = None,
                 url: str = "https://app.godelterminal.com",
                 username: str = None, password: str = None):
        """
        Args:
            channels: List of channel names to monitor (e.g., ['general', 'biotech', 'paid'])
            duration: How long to monitor in seconds (None = indefinite)
            url: Godel Terminal URL
            username: Login username
            password: Login password
        """
        self.channels = channels
        self.duration = duration
        self.url = url
        self.username = username
        self.password = password
        self.manager: Optional[GodelManager] = None
        self.sessions: dict = {}  # channel -> GodelSession
        self.monitors: dict = {}  # channel -> ChatMonitor
        self.results: dict = {}   # channel -> result dict
        
    async def start(self, background: bool = True):
        """Start monitoring all channels in parallel."""
        logger.info(f"Starting multi-channel monitor for: {self.channels}")
        
        # Create manager
        self.manager = GodelManager(headless=False, background=background, url=self.url)
        await self.manager.start()
        
        # Create sessions and login for each channel
        login_tasks = []
        for channel in self.channels:
            task = self._setup_channel_session(channel)
            login_tasks.append(task)
        
        # Wait for all logins to complete
        await asyncio.gather(*login_tasks, return_exceptions=True)
        
        # Start monitoring all channels
        monitor_tasks = []
        for channel in self.channels:
            if channel in self.sessions:
                task = self._monitor_channel(channel)
                monitor_tasks.append(task)
        
        # Run all monitors concurrently
        if self.duration:
            logger.info(f"Monitoring for {self.duration} seconds...")
            await asyncio.wait_for(
                asyncio.gather(*monitor_tasks, return_exceptions=True),
                timeout=self.duration
            )
        else:
            logger.info("Monitoring indefinitely (Ctrl+C to stop)...")
            await asyncio.gather(*monitor_tasks, return_exceptions=True)
    
    async def _setup_channel_session(self, channel: str):
        """Setup a session for a specific channel."""
        try:
            session_id = f"chat_{channel}"
            session = await self.manager.create_session(session_id)
            await session.init_page()
            await session.login(self.username, self.password)
            await session.load_layout("dev")
            
            self.sessions[channel] = session
            logger.info(f"Session ready for channel: {channel}")
            
            # Open the chat window for this channel
            await self._open_chat_window(session, channel)
            
        except Exception as e:
            logger.error(f"Failed to setup session for {channel}: {e}")
            self.results[channel] = {"error": str(e)}
    
    async def _open_chat_window(self, session: GodelSession, channel: str):
        """Open the chat window for a specific channel."""
        try:
            # Try different possible chat commands
            # Godel Terminal likely uses something like CHAT #channel or just opens chat
            
            # First, try to find if there's a chat UI element
            # Look for chat-related buttons or menu items
            
            # Try clicking on a chat menu/button if it exists
            chat_selectors = [
                "button:has-text('Chat')",
                "a:has-text('Chat')",
                "[data-testid='chat']",
                "text=Chat",
            ]
            
            for selector in chat_selectors:
                try:
                    chat_btn = session.page.locator(selector).first
                    if await chat_btn.count() > 0:
                        await chat_btn.click()
                        logger.info(f"Opened chat UI for {channel}")
                        await session.page.wait_for_timeout(2000)
                        break
                except:
                    continue
            
            # Try sending a chat command to the terminal
            # Common patterns: CHAT, CHAT #channel, /join #channel, etc.
            chat_commands = [
                f"CHAT #{channel}",
                f"CHAT {channel}",
                "CHAT",
                f"/join #{channel}",
                f"/chat {channel}",
            ]
            
            for cmd in chat_commands:
                try:
                    await session.send_command(cmd)
                    await session.page.wait_for_timeout(3000)
                    
                    # Check if a chat window opened
                    windows = await session.get_current_windows()
                    if windows:
                        logger.info(f"Chat window opened for {channel} with command: {cmd}")
                        return
                except:
                    continue
            
            logger.warning(f"Could not open chat window for {channel}, will monitor WebSocket anyway")
            
        except Exception as e:
            logger.error(f"Error opening chat for {channel}: {e}")
    
    async def _monitor_channel(self, channel: str):
        """Monitor a single channel."""
        session = self.sessions.get(channel)
        if not session:
            return
        
        try:
            # Use ChatMonitorV2 for better WebSocket handling
            monitor = ChatMonitorV2(session, channels=[channel])
            self.monitors[channel] = monitor
            
            # Run until duration expires
            if self.duration:
                await asyncio.wait_for(monitor.start(), timeout=self.duration)
            else:
                await monitor.start()
                
        except asyncio.TimeoutError:
            logger.info(f"Monitor timeout for {channel}")
        except Exception as e:
            logger.error(f"Monitor error for {channel}: {e}")
        finally:
            self.results[channel] = {
                "channel": channel,
                "messages_captured": monitor.message_count if monitor else 0,
            }
    
    def stop(self):
        """Stop all monitors."""
        for monitor in self.monitors.values():
            monitor.stop()
    
    async def shutdown(self):
        """Cleanup all resources."""
        self.stop()
        await asyncio.sleep(1)
        
        if self.manager:
            await self.manager.shutdown()
        
        await close_db()
    
    def get_summary(self) -> dict:
        """Get summary of all monitoring results."""
        total_messages = sum(r.get("messages_captured", 0) for r in self.results.values())
        return {
            "channels": self.channels,
            "total_messages": total_messages,
            "channel_results": self.results,
        }


async def main():
    """CLI entry point for multi-channel chat monitoring."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor multiple Godel chat channels simultaneously")
    parser.add_argument("--channels", "-c", default="general,biotech,paid",
                       help="Comma-separated channel names (default: general,biotech,paid)")
    parser.add_argument("--duration", "-d", type=int, default=60,
                       help="Monitoring duration in seconds (default: 60)")
    parser.add_argument("--background", "-bg", action="store_true", default=True,
                       help="Run browser off-screen (default: True)")
    parser.add_argument("--visible", action="store_true",
                       help="Run browser visibly (for debugging)")
    
    args = parser.parse_args()
    
    # Load config
    try:
        from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
    except ImportError:
        print(json.dumps({"error": "config.py not found. Copy config-example.py to config.py."}))
        sys.exit(1)
    
    channels = [c.strip() for c in args.channels.split(",")]
    background = not args.visible if args.visible else args.background
    
    monitor = MultiChannelChatMonitor(
        channels=channels,
        duration=args.duration,
        url=GODEL_URL,
        username=GODEL_USERNAME,
        password=GODEL_PASSWORD
    )
    
    try:
        await monitor.start(background=background)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await monitor.shutdown()
    
    # Output results
    summary = monitor.get_summary()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
