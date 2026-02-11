#!/usr/bin/env python3
"""
Standalone Godel Terminal Monitor
Runs continuous chat monitoring without OpenClaw.
"""
import asyncio
import json
import sys
import signal
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from godel_core import GodelManager
from dom_chat_monitor import DOMChatMonitor
from db import SQLiteBackend


class ContinuousChatMonitor:
    """Continuous chat monitoring for any computer."""
    
    def __init__(self, channels=None, headless=False, db_path="godel_chat.db"):
        self.channels = channels or ["general", "biotech", "paid"]
        self.headless = headless
        self.db_path = db_path
        self.manager = None
        self.sessions = {}
        self.running = False
        self.message_count = 0
        
    async def start(self):
        """Start continuous monitoring."""
        print(f"\n{'='*60}")
        print("GODEL TERMINAL - Continuous Chat Monitor")
        print(f"{'='*60}")
        print(f"Monitoring channels: {', '.join(self.channels)}")
        print(f"Database: {self.db_path}")
        print(f"Mode: {'Headless' if self.headless else 'Visible browser'}")
        print(f"{'='*60}\n")
        
        # Initialize database
        self.db = SQLiteBackend(self.db_path)
        await self.db.init()
        print("✓ Database initialized")
        
        # Load config
        try:
            from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
        except ImportError:
            print("\n❌ ERROR: config.py not found!")
            print("Create config.py with:")
            print("  GODEL_URL = 'https://app.godelterminal.com'")
            print("  GODEL_USERNAME = 'your_email'")
            print("  GODEL_PASSWORD = 'your_password'")
            sys.exit(1)
        
        # Start browser manager
        print("\n[1/4] Starting browser...")
        self.manager = GodelManager(
            headless=self.headless,
            background=True,
            url=GODEL_URL
        )
        await self.manager.start()
        print("✓ Browser started")
        
        # Login and setup for each channel
        print(f"\n[2/4] Setting up {len(self.channels)} channel(s)...")
        for channel in self.channels:
            session = await self.manager.create_session(f"chat_{channel}")
            await session.init_page()
            await session.login(GODEL_USERNAME, GODEL_PASSWORD)
            await session.load_layout("dev")
            
            # Navigate to channel
            await self._navigate_to_channel(session, channel)
            self.sessions[channel] = session
            print(f"✓ Channel #{channel} ready")
        
        print(f"\n[3/4] Starting monitors...")
        self.running = True
        
        # Start monitoring tasks
        tasks = []
        for channel, session in self.sessions.items():
            task = asyncio.create_task(
                self._monitor_channel(channel, session),
                name=f"monitor_{channel}"
            )
            tasks.append(task)
        
        # Start status reporter
        tasks.append(asyncio.create_task(self._status_reporter(), name="reporter"))
        
        print(f"✓ {len(self.channels)} monitor(s) active")
        print(f"\n[4/4] Monitoring started! Press Ctrl+C to stop.\n")
        print(f"{'='*60}")
        
        # Wait for all tasks
        await asyncio.gather(*tasks, return_exceptions=True)
        
    async def _navigate_to_channel(self, session, channel):
        """Navigate to a specific channel."""
        try:
            # Open chat
            chat_btn = session.page.locator("button:has-text('CHAT')").first
            if await chat_btn.count() > 0:
                await chat_btn.click()
                await asyncio.sleep(1)
            
            # Expand Public Channels
            public_channels = session.page.locator("text=Public Channels").first
            if await public_channels.count() > 0:
                parent = public_channels.locator("..")
                if await parent.count() > 0:
                    await parent.click()
                    await asyncio.sleep(1)
            
            # Click channel
            channel_elem = session.page.locator(f"text=#{channel}").first
            if await channel_elem.count() > 0:
                await channel_elem.click()
                await asyncio.sleep(2)
                
        except Exception as e:
            print(f"⚠ Warning: Navigation issue for #{channel}: {e}", file=sys.stderr)
    
    async def _monitor_channel(self, channel, session):
        """Monitor a single channel continuously."""
        monitor = DOMChatMonitor(session, channel)
        seen_ids = set()
        
        while self.running:
            try:
                # Poll for new messages
                messages = await self._extract_messages(session, channel)
                
                for msg in messages:
                    msg_id = msg.get('id') or f"{msg.get('sender')}_{msg.get('timestamp')}"
                    
                    if msg_id not in seen_ids:
                        seen_ids.add(msg_id)
                        
                        # Save to database
                        await self.db.save_message(
                            channel=channel,
                            sender=msg.get('sender'),
                            content=msg.get('content'),
                            timestamp=msg.get('timestamp'),
                            raw_data=json.dumps(msg)
                        )
                        
                        self.message_count += 1
                        
                        # Print real-time
                        print(f"[{channel}] {msg.get('sender')}: {msg.get('content', '')[:80]}...")
                
                await asyncio.sleep(3)  # Poll every 3 seconds
                
            except Exception as e:
                if self.running:
                    print(f"⚠ Error in #{channel}: {e}", file=sys.stderr)
                    await asyncio.sleep(5)
    
    async def _extract_messages(self, session, channel):
        """Extract messages from DOM."""
        messages = []
        
        try:
            # Find message containers
            msg_containers = await session.page.locator("[class*='message'").all()
            
            for container in msg_containers:
                try:
                    # Extract sender
                    sender_elem = container.locator("[class*='sender'], [class*='author'], [class*='user']").first
                    sender = await sender_elem.inner_text() if await sender_elem.count() > 0 else "Unknown"
                    
                    # Extract content
                    content_elem = container.locator("[class*='content'], [class*='text'], [class*='body']").first
                    content = await content_elem.inner_text() if await content_elem.count() > 0 else ""
                    
                    # Extract timestamp
                    time_elem = container.locator("[class*='time'], [class*='date']").first
                    timestamp = await time_elem.inner_text() if await time_elem.count() > 0 else ""
                    
                    messages.append({
                        'sender': sender.strip(),
                        'content': content.strip(),
                        'timestamp': timestamp,
                        'channel': channel
                    })
                except:
                    continue
                    
        except:
            pass
            
        return messages
    
    async def _status_reporter(self):
        """Report status periodically."""
        while self.running:
            await asyncio.sleep(60)  # Report every minute
            if self.running:
                print(f"\n[STATUS] Total messages captured: {self.message_count}")
                print(f"[STATUS] Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"[STATUS] Channels: {', '.join(self.channels)}")
                print(f"{'-'*60}\n")
    
    async def stop(self):
        """Stop monitoring."""
        self.running = False
        print("\n\nShutting down...")
        
        if self.manager:
            await self.manager.shutdown()
            
        print(f"✓ Monitoring stopped")
        print(f"Total messages: {self.message_count}")
        print(f"Database: {self.db_path}")
        print(f"\nTo replay messages:")
        print(f"  sqlite3 {self.db_path} 'SELECT * FROM chat_messages ORDER BY timestamp DESC LIMIT 20;'\n")


def signal_handler(monitor):
    """Handle Ctrl+C gracefully."""
    def handler(signum, frame):
        asyncio.create_task(monitor.stop())
    return handler


async def main():
    parser = argparse.ArgumentParser(
        description='Godel Terminal - Standalone Chat Monitor',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python standalone_monitor.py                    # Monitor default channels
  python standalone_monitor.py -c general         # Monitor only #general
  python standalone_monitor.py -c general,biotech -d mychat.db
        """
    )
    parser.add_argument('--channels', '-c', default='general,biotech,paid',
                       help='Comma-separated channel names (default: general,biotech,paid)')
    parser.add_argument('--database', '-d', default='godel_chat.db',
                       help='SQLite database path (default: godel_chat.db)')
    parser.add_argument('--headless', action='store_true',
                       help='Run browser headless (less reliable)')
    
    args = parser.parse_args()
    
    channels = [c.strip() for c in args.channels.split(',')]
    
    monitor = ContinuousChatMonitor(
        channels=channels,
        headless=args.headless,
        db_path=args.database
    )
    
    # Setup signal handler
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(monitor.stop()))
    
    try:
        await monitor.start()
    except KeyboardInterrupt:
        await monitor.stop()


if __name__ == '__main__':
    asyncio.run(main())
