"""
Chat Monitor — WebSocket interception + SQLite storage
Monitors chat channels and stores messages in the database
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from godel_core import GodelSession, NetworkInterceptor
from db import get_db

logger = logging.getLogger("godel.chat")


class ChatMonitor:
    """Long-running monitor that intercepts WebSocket frames for chat messages
    and stores them in SQLite.

    This is NOT a BaseCommand — it runs as a background coroutine.
    """

    def __init__(self, session: GodelSession, channels: Optional[List[str]] = None,
                 db_path: Optional[str] = None):
        """
        Args:
            session: Active GodelSession
            channels: Channel names to monitor (None = all)
            db_path: Override SQLite path
        """
        self.session = session
        self.page = session.page
        self.channels = [c.lower() for c in channels] if channels else None
        self.db_path = db_path
        self._running = False
        self._message_count = 0
        self._on_message_callbacks: List[Callable] = []

    def on_message(self, callback: Callable):
        """Register a callback invoked for each new message."""
        self._on_message_callbacks.append(callback)

    async def start(self, duration: Optional[int] = None):
        """Start monitoring. Runs until duration expires or stop() is called.

        Args:
            duration: Seconds to run, or None for indefinite (stop with stop())
        """
        db = await get_db(self.db_path)
        interceptor = self.session.interceptor
        if not interceptor:
            interceptor = NetworkInterceptor(self.page)
            self.session.interceptor = interceptor

        # We piggy-back on the interceptor's WS frame list but also process in real time
        original_ws_handler = interceptor._on_websocket

        processed_idx = 0
        interceptor.clear()
        interceptor.start(capture_ws=True)
        self._running = True

        logger.info(f"Chat monitor started (channels={self.channels}, duration={duration}s)")

        try:
            elapsed = 0
            while self._running:
                # Process new WS frames
                frames = interceptor.ws_frames[processed_idx:]
                for frame in frames:
                    await self._process_frame(frame, db)
                processed_idx = len(interceptor.ws_frames)

                await asyncio.sleep(0.5)
                elapsed += 0.5
                if duration and elapsed >= duration:
                    break
        finally:
            self._running = False
            interceptor.stop()
            logger.info(f"Chat monitor stopped. {self._message_count} messages captured.")

    def stop(self):
        """Signal the monitor to stop."""
        self._running = False

    async def _process_frame(self, frame: Dict, db):
        """Attempt to parse a WS frame as a chat message and store it."""
        payload = frame.get("payload", "")
        if not isinstance(payload, str):
            return

        # Try JSON parse
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return

        # Heuristic: look for chat-like message structures
        # The exact schema depends on the Godel Terminal implementation.
        # We store anything that looks like a message with content/text.
        msg = self._extract_chat_message(data, frame)
        if not msg:
            return

        # Channel filter
        channel = msg.get("channel", "unknown").lower()
        if self.channels and channel not in self.channels:
            return

        # Store
        try:
            await db.save_message(
                channel=msg.get("channel", "unknown"),
                sender=msg.get("sender", "unknown"),
                content=msg.get("content", ""),
                timestamp=msg.get("timestamp"),
                raw_data=payload[:5000],
            )
            self._message_count += 1
            logger.debug(f"Chat [{msg.get('channel')}] {msg.get('sender')}: {msg.get('content', '')[:80]}")

            for cb in self._on_message_callbacks:
                try:
                    cb(msg)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to save message: {e}")

    @staticmethod
    def _extract_chat_message(data: Any, frame: Dict) -> Optional[Dict]:
        """Try to pull channel, sender, content from a parsed JSON payload.

        This uses heuristics and will need tuning once we see actual WS traffic
        from the probe command.  Common patterns:
          - {"type": "message", "channel": "...", "user": "...", "text": "..."}
          - {"event": "chat", "data": {"channel": ..., "sender": ..., "message": ...}}
          - nested under a 'payload' or 'body' key
        """
        if isinstance(data, dict):
            # Direct match
            if "text" in data or "message" in data or "content" in data:
                return {
                    "channel": data.get("channel", data.get("room", "unknown")),
                    "sender": data.get("user", data.get("sender", data.get("author", "unknown"))),
                    "content": data.get("text", data.get("message", data.get("content", ""))),
                    "timestamp": _parse_ts(data.get("timestamp", data.get("ts", data.get("time")))),
                    "raw": data,
                }
            # Nested under common keys
            for key in ("data", "payload", "body", "msg"):
                nested = data.get(key)
                if isinstance(nested, dict) and ("text" in nested or "message" in nested or "content" in nested):
                    return {
                        "channel": nested.get("channel", nested.get("room", data.get("channel", "unknown"))),
                        "sender": nested.get("user", nested.get("sender", nested.get("author", "unknown"))),
                        "content": nested.get("text", nested.get("message", nested.get("content", ""))),
                        "timestamp": _parse_ts(nested.get("timestamp", nested.get("ts"))),
                        "raw": data,
                    }
        return None

    @property
    def message_count(self) -> int:
        return self._message_count


def _parse_ts(value) -> Optional[datetime]:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return datetime.now(timezone.utc)
    return datetime.now(timezone.utc)
