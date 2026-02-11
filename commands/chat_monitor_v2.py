"""
Chat Monitor v2 - Improved WebSocket capture and message parsing
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from godel_core import GodelSession, NetworkInterceptor
from db import get_db

logger = logging.getLogger("godel.chat_v2")


class ChatMonitorV2:
    """Improved chat monitor with better WebSocket handling."""
    
    def __init__(self, session: GodelSession, channels: Optional[List[str]] = None,
                 db_path: Optional[str] = None):
        self.session = session
        self.page = session.page
        self.channels = [c.lower() for c in channels] if channels else None
        self.db_path = db_path
        self._running = False
        self._message_count = 0
        self._seen_message_ids = set()  # Deduplication
        
    async def start(self, duration: Optional[int] = None):
        """Start monitoring chat."""
        db = await get_db(self.db_path)
        
        # Ensure interceptor is set up
        interceptor = self.session.interceptor
        if not interceptor:
            interceptor = NetworkInterceptor(self.page)
            self.session.interceptor = interceptor
        
        # Clear and start fresh
        interceptor.clear()
        interceptor.start(capture_ws=True)
        self._running = True
        
        logger.info(f"Chat monitor v2 started (channels={self.channels}, duration={duration}s)")
        
        # Open chat windows for specified channels
        if self.channels:
            for channel in self.channels:
                await self._open_channel(channel)
        else:
            await self._open_chat_general()
        
        try:
            elapsed = 0
            check_interval = 0.2  # Check every 200ms for new frames
            
            while self._running:
                # Process any new WebSocket frames
                await self._process_new_frames(interceptor, db)
                
                await asyncio.sleep(check_interval)
                elapsed += check_interval
                
                if duration and elapsed >= duration:
                    break
                    
        finally:
            self._running = False
            interceptor.stop()
            logger.info(f"Chat monitor stopped. {self._message_count} messages captured.")
    
    async def _open_channel(self, channel: str):
        """Try to open a specific chat channel."""
        logger.info(f"Opening chat channel: {channel}")
        
        # Try various chat commands
        commands = [
            f"CHAT #{channel}",
            f"CHAT {channel}",
            "CHAT",
        ]
        
        for cmd in commands:
            try:
                await self.session.send_command(cmd)
                await self.page.wait_for_timeout(2000)
                
                # Check if window opened
                windows = await self.session.get_current_windows()
                if windows:
                    logger.info(f"Window opened with command: {cmd}")
                    return True
            except Exception as e:
                logger.debug(f"Command {cmd} failed: {e}")
        
        return False
    
    async def _open_chat_general(self):
        """Open general chat."""
        return await self._open_channel("general")
    
    async def _process_new_frames(self, interceptor: NetworkInterceptor, db):
        """Process any new WebSocket frames."""
        # Get all frames since last check
        for frame in interceptor.ws_frames:
            await self._process_frame(frame, db)
        
        # Clear processed frames to save memory
        # (In production, you'd want a smarter approach)
        if len(interceptor.ws_frames) > 1000:
            interceptor.ws_frames = interceptor.ws_frames[-500:]
    
    async def _process_frame(self, frame: Dict, db):
        """Process a single WebSocket frame."""
        payload = frame.get("payload", "")
        if not isinstance(payload, str) or not payload:
            return
        
        # Try to parse as JSON
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            # Not JSON, skip
            return
        
        # Extract message using improved heuristics
        msg = self._extract_message(data)
        if not msg:
            return
        
        # Deduplication
        msg_id = msg.get("id") or f"{msg.get('sender')}:{msg.get('content', '')[:50]}"
        if msg_id in self._seen_message_ids:
            return
        self._seen_message_ids.add(msg_id)
        
        # Channel filter
        channel = msg.get("channel", "unknown").lower()
        if self.channels and channel not in self.channels:
            return
        
        # Store in database
        try:
            await db.save_message(
                channel=channel,
                sender=msg.get("sender", "unknown"),
                content=msg.get("content", ""),
                timestamp=msg.get("timestamp"),
                raw_data=json.dumps(data)[:5000],
            )
            self._message_count += 1
            logger.info(f"[{channel}] {msg.get('sender')}: {msg.get('content', '')[:60]}...")
        except Exception as e:
            logger.error(f"Failed to save message: {e}")
    
    def _extract_message(self, data: Any) -> Optional[Dict]:
        """Extract chat message from WebSocket data using multiple strategies."""
        
        if not isinstance(data, dict):
            return None
        
        # Strategy 1: Socket.IO format (common in web apps)
        # {"type": 2, "nsp": "/", "data": ["message", {...}]}
        if "type" in data and "data" in data:
            inner_data = data.get("data")
            if isinstance(inner_data, list) and len(inner_data) >= 2:
                event_type = inner_data[0]
                payload = inner_data[1]
                if isinstance(payload, dict):
                    return self._parse_message_dict(payload, event_type)
        
        # Strategy 2: Direct message format
        result = self._parse_message_dict(data)
        if result:
            return result
        
        # Strategy 3: Nested under common keys
        for key in ("data", "payload", "body", "message", "event"):
            nested = data.get(key)
            if isinstance(nested, dict):
                result = self._parse_message_dict(nested)
                if result:
                    return result
        
        # Strategy 4: Array of messages
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    result = self._parse_message_dict(item)
                    if result:
                        return result
        
        return None
    
    def _parse_message_dict(self, data: Dict, event_type: str = None) -> Optional[Dict]:
        """Try to parse a dict as a chat message."""
        
        # Look for content field
        content = None
        for key in ("text", "message", "content", "body", "msg"):
            if key in data:
                content = data[key]
                break
        
        if not content or not isinstance(content, str):
            return None
        
        # Look for sender field
        sender = "unknown"
        for key in ("user", "sender", "author", "from", "username", "name"):
            if key in data:
                val = data[key]
                if isinstance(val, str):
                    sender = val
                    break
                elif isinstance(val, dict):
                    # Sometimes sender is nested: {"name": "...", "id": "..."}
                    sender = val.get("name", val.get("username", "unknown"))
                    break
        
        # Look for channel field
        channel = "general"
        for key in ("channel", "room", "chat", "group"):
            if key in data:
                val = data[key]
                if isinstance(val, str):
                    channel = val
                    break
                elif isinstance(val, dict):
                    channel = val.get("name", "general")
                    break
        
        # Look for timestamp
        timestamp = None
        for key in ("timestamp", "ts", "time", "created_at", "date"):
            if key in data:
                timestamp = self._parse_timestamp(data[key])
                break
        
        # Look for message ID
        msg_id = None
        for key in ("id", "messageId", "msgId", "_id"):
            if key in data:
                msg_id = str(data[key])
                break
        
        # Look for event type indicators
        msg_type = event_type or data.get("type", "message")
        
        # Filter out non-message events
        if msg_type in ("typing", "presence", "status", "read_receipt"):
            return None
        
        return {
            "id": msg_id,
            "channel": channel,
            "sender": sender,
            "content": content,
            "timestamp": timestamp,
            "type": msg_type,
            "raw": data,
        }
    
    def _parse_timestamp(self, value) -> Optional[datetime]:
        """Parse various timestamp formats."""
        if value is None:
            return datetime.now(timezone.utc)
        
        if isinstance(value, (int, float)):
            # Handle both seconds and milliseconds
            if value > 1e12:  # Likely milliseconds
                value = value / 1000
            try:
                return datetime.fromtimestamp(value, tz=timezone.utc)
            except:
                return datetime.now(timezone.utc)
        
        if isinstance(value, str):
            # Try various formats
            formats = [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
                except:
                    continue
            
            # Try ISO format
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except:
                pass
        
        return datetime.now(timezone.utc)
    
    def stop(self):
        """Stop the monitor."""
        self._running = False
    
    @property
    def message_count(self) -> int:
        return self._message_count
