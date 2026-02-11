"""
PRT (Pattern Real-Time) Command — async Playwright
Batch analysis on multiple tickers, exports CSV
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from godel_core import BaseCommand, GodelSession

logger = logging.getLogger("godel.prt")


class PRTCommand(BaseCommand):
    """Pattern Real-Time (PRT) — batch analysis with CSV export."""

    def __init__(self, session: GodelSession, tickers: List[str] = None):
        super().__init__(session)
        self.tickers = tickers or []
        self.csv_file_path: Optional[str] = None
        self.df: Optional[pd.DataFrame] = None

    def get_command_string(self, ticker: str = None, asset_class: str = None) -> str:
        return "PRT"

    # -- UI interactions ----------------------------------------------------

    async def _input_tickers(self) -> bool:
        try:
            textarea = self.window.locator("xpath=.//label[contains(., 'Symbols')]//textarea").first
            await textarea.fill("")
            await textarea.type(" ".join(self.tickers), delay=10)
            await self.page.wait_for_timeout(200)
            logger.info(f"Tickers entered: {' '.join(self.tickers)}")
            return True
        except Exception as e:
            logger.error(f"Ticker input failed: {e}")
            return False

    async def _click_run(self) -> bool:
        for attempt in range(3):
            try:
                run_btn = self.window.locator("button.bg-emerald-600:has-text('Run')").first
                await run_btn.scroll_into_view_if_needed()
                await self.page.wait_for_timeout(500)
                await run_btn.click(force=True)
                logger.info(f"Run clicked (attempt {attempt+1})")
                await self.page.wait_for_timeout(1000)
                return True
            except Exception as e:
                logger.warning(f"Run click attempt {attempt+1} failed: {e}")
                await self.page.wait_for_timeout(1000)
        return False

    async def _wait_for_completion(self, timeout: int = 120) -> bool:
        import time
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                bar = self.window.locator("div.h-full.bg-\\[\\#10b981\\]").first
                style = await bar.get_attribute("style") or ""
                if "width: 100%" in style or "width:100%" in style:
                    await self.page.wait_for_timeout(500)
                    return True
            except Exception:
                pass
            try:
                prog = self.window.locator("xpath=.//div[contains(text(), '/')]").first
                text = await prog.inner_text()
                if "/" in text:
                    parts = text.split("/")
                    if len(parts) == 2 and parts[0].strip() == parts[1].strip():
                        await self.page.wait_for_timeout(500)
                        return True
            except Exception:
                pass
            await self.page.wait_for_timeout(1000)
        return False

    async def _export_csv(self) -> Optional[str]:
        try:
            download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            existing = set(f for f in os.listdir(download_dir) if f.endswith(".csv")) if os.path.exists(download_dir) else set()

            export_btn = self.window.locator("button:has-text('Export CSV')").first
            await export_btn.click()
            await self.page.wait_for_timeout(500)

            # Wait for new file
            for _ in range(20):
                if os.path.exists(download_dir):
                    current = set(f for f in os.listdir(download_dir) if f.endswith(".csv"))
                    new_files = current - existing
                    if new_files:
                        path = os.path.join(download_dir, new_files.pop())
                        self.csv_file_path = path
                        try:
                            self.df = pd.read_csv(path)
                        except Exception:
                            pass
                        return path
                await self.page.wait_for_timeout(500)
            return None
        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            return None

    # -- extraction ---------------------------------------------------------

    async def extract_data(self) -> Dict:
        data: Dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "window_id": self.window_id,
            "tickers": self.tickers,
            "csv_file_path": self.csv_file_path,
        }
        # Performance summary
        try:
            table = self.window.locator("xpath=.//div[contains(text(), 'Performance Summary')]/..//table").first
            summary = []
            for row in await table.locator("tbody tr").all():
                cells = await row.locator("td").all()
                if len(cells) >= 7:
                    summary.append({
                        "bucket": (await cells[0].inner_text()).strip(),
                        "n": (await cells[1].inner_text()).strip(),
                        "long": (await cells[2].inner_text()).strip(),
                        "short": (await cells[3].inner_text()).strip(),
                        "win_rate": (await cells[4].inner_text()).strip(),
                        "mean_pl": (await cells[5].inner_text()).strip(),
                        "median_pl": (await cells[6].inner_text()).strip(),
                    })
            data["performance_summary"] = summary
        except Exception:
            data["performance_summary"] = []

        # Progress
        try:
            prog = self.window.locator("xpath=.//div[contains(text(), '/')]").first
            text = await prog.inner_text()
            parts = text.split("/")
            data["progress"] = {"completed": parts[0].strip(), "total": parts[1].strip()} if len(parts) == 2 else None
        except Exception:
            data["progress"] = None

        # Failures
        try:
            strong = self.window.locator("xpath=.//div[contains(text(), 'Failures in last batch')]//strong").first
            data["failures"] = int((await strong.inner_text()).strip())
        except Exception:
            data["failures"] = 0

        return data

    # -- custom execute -----------------------------------------------------

    async def execute(self, ticker: str = None, asset_class: str = None) -> Dict:
        command_str = self.get_command_string()
        previous_count = len(await self.session.get_current_windows())

        logger.info(f"Executing PRT for {len(self.tickers)} tickers")

        if not await self.session.send_command(command_str):
            return {"success": False, "error": "Failed to send command", "command": command_str}

        self.window = await self.session.wait_for_new_window(previous_count, timeout=10000)
        if not self.window:
            return {"success": False, "error": "No new window", "command": command_str}

        self.window_id = await self.window.get_attribute("id")
        await self.page.wait_for_timeout(500)

        if self.tickers and not await self._input_tickers():
            return {"success": False, "error": "Failed to input tickers", "window_id": self.window_id}

        if not await self._click_run():
            return {"success": False, "error": "Failed to click Run", "window_id": self.window_id}

        if not await self._wait_for_completion():
            return {"success": False, "error": "Analysis timeout", "window_id": self.window_id}

        csv_path = await self._export_csv()
        if not csv_path:
            return {"success": False, "error": "CSV export failed", "window_id": self.window_id}

        try:
            data = await self.extract_data()
            data["csv_file_path"] = csv_path
            data["row_count"] = len(self.df) if self.df is not None else 0
            data["columns"] = self.df.columns.tolist() if self.df is not None else []
        except Exception as e:
            data = {"csv_file_path": csv_path, "row_count": 0, "columns": []}

        return {"success": True, "command": command_str, "data": data, "csv_file": csv_path}

    # -- save helpers -------------------------------------------------------

    def get_dataframe(self) -> Optional[pd.DataFrame]:
        return self.df

    def save_to_csv(self, filepath: str) -> bool:
        if self.df is not None:
            self.df.to_csv(filepath, index=False)
            return True
        return False

    def save_to_json(self, filepath: str) -> bool:
        if self.df is not None:
            self.df.to_json(filepath, orient="records", indent=2)
            return True
        return False
