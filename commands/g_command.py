"""
G (Chart) Command — async Playwright
Opens price chart window (data extraction placeholder)
"""

from datetime import datetime, timezone
from typing import Dict, Optional

from godel_core import BaseCommand


class GCommand(BaseCommand):
    """Chart (G) command."""

    def get_command_string(self, ticker: str = None, asset_class: str = None) -> str:
        return f"{ticker} {asset_class or 'EQ'} G"

    async def extract_data(self) -> Dict:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "window_id": self.window_id,
            "ticker": await self._get_ticker(),
            "type": "chart",
            "note": "Chart data extraction not yet implemented",
        }

    async def _get_ticker(self) -> Optional[str]:
        try:
            inp = self.window.locator("input[value]").first
            return await inp.input_value()
        except Exception:
            return None
