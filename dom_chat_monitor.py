"""
DOM-based Chat Monitor for Godel Terminal
Extracts messages directly from the DOM instead of WebSocket interception.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from godel_core import GodelSession
from db import get_db

logger = logging.getLogger("godel.dom_chat")


def clean_for_hash(text: str) -> str:
    """Remove dynamic price data from message text for consistent hashing.
    
    Godel updates stock prices in real-time (e.g., "+0.00%", "US -0.46-2.51%"),
    which causes the same message to hash differently every few seconds.
    """
    # Remove patterns like "+0.00%", "-0.46-2.51%", "US -0.46-2.56%"
    cleaned = re.sub(r'\s+[-+]?\d+\.?\d*%', ' ', text)
    cleaned = re.sub(r'\s+US\s+[-+]?\d+\.?\d*-[-+]?\d+\.?\d*%', ' ', cleaned)
    # Remove extra whitespace
    cleaned = ' '.join(cleaned.split())
    return cleaned.strip()


class DOMChatMonitor:
    """Monitor chat by polling the DOM for messages.
    
    This is more reliable than WebSocket interception since we can see
    exactly what's rendered on the page.
    """
    
    def __init__(self, session: GodelSession, channel: str, db_path: Optional[str] = None):
        self.session = session
        self.page = session.page
        self.channel = channel
        self.db_path = db_path
        self._running = False
        self._message_count = 0
        self._seen_messages: Set[str] = set()  # Deduplication
        
    async def start(self, duration: Optional[int] = None, poll_interval: float = 2.0):
        """Start monitoring chat via DOM polling.
        
        Args:
            duration: How long to monitor in seconds (None = indefinite)
            poll_interval: Seconds between DOM polls
        """
        db = await get_db(self.db_path)
        self._running = True
        
        logger.info(f"DOM Chat monitor started for #{self.channel} (duration={duration}s, interval={poll_interval}s)")
        
        try:
            elapsed = 0
            while self._running:
                # Extract messages from DOM
                messages = await self._extract_messages()
                
                # Process and store new messages
                for msg in messages:
                    await self._process_message(msg, db)
                
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                
                if duration and elapsed >= duration:
                    break
                    
        finally:
            self._running = False
            logger.info(f"DOM Chat monitor stopped. {self._message_count} new messages captured.")
    
    async def _extract_messages(self) -> List[Dict]:
        """Extract messages from the chat DOM."""
        messages = []
        
        # Try different selectors for message elements
        selectors = [
            "[class*='message']",
            ".chat-message", 
            ".message",
            ".msg",
            "[data-testid='message']",
            ".message-content",
        ]
        
        for selector in selectors:
            try:
                msg_elements = self.page.locator(selector)
                count = await msg_elements.count()
                
                if count > 0:
                    logger.debug(f"Found {count} messages with selector: {selector}")
                    
                    for i in range(count):
                        try:
                            elem = msg_elements.nth(i)
                            msg_data = await self._parse_message_element(elem)
                            if msg_data:
                                messages.append(msg_data)
                        except Exception as e:
                            logger.debug(f"Error parsing message element: {e}")
                    
                    # If we found messages, don't try other selectors
                    if messages:
                        break
                        
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
        
        return messages
    
    async def _parse_message_element(self, elem) -> Optional[Dict]:
        """Parse a single message element from the DOM."""
        try:
            # Get message text/content
            text = await elem.text_content()
            if not text or not text.strip():
                return None
            
            # Skip system messages or empty content
            if "(jump to message)" in text and len(text) < 30:
                return None
            
            # Extract sender - try different selectors
            sender = "unknown"
            sender_selectors = [
                ".username",
                ".sender", 
                ".author",
                ".user",
                "[class*='username']",
                "[class*='sender']",
            ]
            
            for sel in sender_selectors:
                try:
                    sender_elem = elem.locator(sel).first
                    if await sender_elem.count() > 0:
                        sender_text = await sender_elem.text_content()
                        if sender_text and sender_text.strip():
                            sender = sender_text.strip().replace("@", "")
                            break
                except:
                    continue
            
            # If no sender found via selectors, try to extract from text
            # Format often: "@username: message content"
            if sender == "unknown" and text.startswith("@"):
                parts = text.split(":", 1)
                if len(parts) > 1:
                    sender = parts[0].replace("@", "").strip()
                    text = parts[1].strip()
            
            # Create unique ID for deduplication (strip dynamic price data)
            clean_text = clean_for_hash(text)
            msg_id = f"{sender}:{clean_text[:100]}"
            
            return {
                "id": msg_id,
                "channel": self.channel,
                "sender": sender,
                "username": sender,  # Store username separately
                "content": text,
                "timestamp": datetime.now(timezone.utc),
                "raw": None,
            }
            
        except Exception as e:
            logger.debug(f"Error parsing message: {e}")
            return None
    
    async def _process_message(self, msg: Dict, db):
        """Process a single message - deduplicate and store."""
        msg_id = msg.get("id")
        
        # Skip if already seen
        if msg_id in self._seen_messages:
            return
        
        self._seen_messages.add(msg_id)
        
        # Store in database
        try:
            await db.save_message(
                channel=self.channel,
                sender=msg.get("sender", "unknown"),
                content=msg.get("content", ""),
                timestamp=msg.get("timestamp"),
                raw_data=json.dumps({"source": "dom", "id": msg_id}),
                message_id=msg_id,
                username=msg.get("username"),
            )
            self._message_count += 1
            logger.info(f"[{self.channel}] {msg.get('sender')}: {msg.get('content', '')[:60]}...")
        except Exception as e:
            logger.error(f"Failed to save message: {e}")
    
    def stop(self):
        """Stop the monitor."""
        self._running = False
    
    @property
    def message_count(self) -> int:
        return self._message_count
