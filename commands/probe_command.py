"""
Probe Command — Network traffic capture for reverse-engineering
Captures HTTP requests/responses and WebSocket frames, outputs JSON
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from godel_core import GodelSession, NetworkInterceptor

logger = logging.getLogger("godel.probe")


class ProbeCommand:
    """Capture and log all network traffic for a configurable duration.

    This is NOT a BaseCommand subclass — it doesn't open a terminal command window.
    Instead it attaches a NetworkInterceptor and records traffic.
    """

    def __init__(self, session: GodelSession, duration: int = 30,
                 filter_type: Optional[str] = None,
                 url_filter: Optional[str] = None):
        """
        Args:
            session: Active GodelSession
            duration: How many seconds to capture (default 30)
            filter_type: 'http', 'websocket', or None for all
            url_filter: Only capture URLs containing this string
        """
        self.session = session
        self.page = session.page
        self.duration = duration
        self.filter_type = filter_type
        self.url_filter = url_filter

    async def execute(self) -> Dict:
        """Run the probe and return captured traffic."""
        interceptor = self.session.interceptor
        if not interceptor:
            interceptor = NetworkInterceptor(self.page)
            self.session.interceptor = interceptor

        interceptor.clear()
        capture_ws = self.filter_type in (None, "websocket")
        interceptor.start(url_filter=self.url_filter, capture_ws=capture_ws)

        logger.info(f"Probe started — capturing for {self.duration}s (filter={self.filter_type}, url={self.url_filter})")

        await asyncio.sleep(self.duration)

        interceptor.stop()

        traffic = interceptor.dump(filter_type=self.filter_type)

        summary = {
            "success": True,
            "duration_seconds": self.duration,
            "filter_type": self.filter_type,
            "url_filter": self.url_filter,
            "counts": {
                "requests": len(traffic.get("requests", [])),
                "responses": len(traffic.get("responses", [])),
                "websocket_frames": len(traffic.get("websocket_frames", [])),
            },
            "data": traffic,
        }

        logger.info(
            f"Probe complete: {summary['counts']['requests']} reqs, "
            f"{summary['counts']['responses']} resps, "
            f"{summary['counts']['websocket_frames']} ws frames"
        )

        return summary

    async def execute_and_save(self, output_path: str = None) -> Dict:
        """Run probe, save to file, and return summary."""
        result = await self.execute()
        if output_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"output/probe_{ts}.json"

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Make data JSON-serializable (strip non-serializable bits)
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2, default=str)

        result["output_file"] = output_path
        logger.info(f"Probe data saved to {output_path}")
        return result
