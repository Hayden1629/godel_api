"""
MOST (Most Active Stocks) Command — async Playwright
Extracts table data into a pandas DataFrame
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd

from godel_core import BaseCommand, GodelSession

logger = logging.getLogger("godel.most")


class MOSTCommand(BaseCommand):
    """Most Active Stocks (MOST) — extracts table to DataFrame."""

    def __init__(self, session: GodelSession, tab: str = "ACTIVE", limit: int = 75):
        super().__init__(session)
        self.tab = tab.upper()
        self.limit = limit
        self.df: Optional[pd.DataFrame] = None

    def get_command_string(self, ticker: str = None, asset_class: str = None) -> str:
        return "MOST"

    # -- UI interactions ----------------------------------------------------

    async def _select_tab(self, tab_name: str) -> bool:
        try:
            tab_el = self.window.locator(f"div.cursor-pointer:has-text('{tab_name}')").first
            await tab_el.click()
            await self.page.wait_for_timeout(1000)
            logger.info(f"Selected tab: {tab_name}")
            return True
        except Exception as e:
            logger.warning(f"Tab select failed: {e}")
            return False

    async def _set_limit(self, limit: int) -> bool:
        try:
            selects = await self.window.locator("select").all()
            if not selects:
                return False
            dropdown = selects[0]
            await dropdown.select_option(str(limit))
            await self.page.wait_for_timeout(1000)
            logger.info(f"Set limit: {limit}")
            return True
        except Exception as e:
            logger.warning(f"Set limit failed: {e}")
            return False

    async def _set_min_market_cap(self, value: str = "FIFTY_BILLION") -> bool:
        try:
            selects = await self.window.locator("select").all()
            if len(selects) < 2:
                return False
            await selects[1].select_option(value)
            await self.page.wait_for_timeout(1000)
            logger.info(f"Set min market cap: {value}")
            return True
        except Exception as e:
            logger.warning(f"Market cap failed: {e}")
            return False

    # -- extraction ---------------------------------------------------------

    async def extract_data(self) -> Dict:
        if not self.window:
            raise ValueError("No window available")

        df = await self._extract_table()
        if df is None:
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "window_id": self.window_id,
                "tab": self.tab,
                "error": "Failed to extract table data",
            }

        self.df = df
        records = df.to_dict("records")
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "window_id": self.window_id,
            "tab": self.tab,
            "limit": self.limit,
            "row_count": len(df),
            "columns": df.columns.tolist(),
            "records": records,
            "tickers": df["Ticker"].tolist() if "Ticker" in df.columns else [],
        }

    async def _extract_table(self) -> Optional[pd.DataFrame]:
        try:
            table = self.window.locator("table").first
            # Headers
            headers = []
            for th in await table.locator("thead th").all():
                headers.append((await th.inner_text()).strip())

            # Rows
            data = []
            rows = await table.locator("tbody tr").all()
            for row in rows:
                cells = await row.locator("td").all()
                row_data = []
                for cell in cells:
                    # Prefer span text
                    span = cell.locator("span").first
                    if await span.count() > 0:
                        row_data.append((await span.inner_text()).strip())
                    else:
                        row_data.append((await cell.inner_text()).strip())
                if row_data:
                    data.append(row_data)

            if not data:
                return None

            df = pd.DataFrame(data, columns=headers)
            df = self._clean_dataframe(df)
            logger.info(f"Extracted {len(df)} rows, {len(df.columns)} columns")
            return df
        except Exception as e:
            logger.error(f"Table extraction failed: {e}", exc_info=True)
            return None

    # -- DataFrame cleaning (unchanged from original) -----------------------

    @staticmethod
    def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        if "Chg %" in df.columns:
            df["Chg %"] = df["Chg %"].str.replace("%", "").replace("", "0")
            df["Chg % Numeric"] = pd.to_numeric(df["Chg %"], errors="coerce")
        for col in ["Vol", "Vol $", "M Cap"]:
            if col in df.columns:
                df[f"{col} Raw"] = df[col]
                df[f"{col} Numeric"] = df[col].apply(MOSTCommand._parse_number)
        if "Last" in df.columns:
            df["Last Numeric"] = pd.to_numeric(df["Last"], errors="coerce")
        if "Chg" in df.columns:
            df["Chg Numeric"] = pd.to_numeric(df["Chg"], errors="coerce")
        return df

    @staticmethod
    def _parse_number(value: str) -> float:
        if not value:
            return 0.0
        try:
            v = value.strip().upper()
            if "T" in v:
                return float(v.replace("T", "")) * 1_000_000_000_000
            elif "B" in v:
                return float(v.replace("B", "")) * 1_000_000_000
            elif "M" in v:
                return float(v.replace("M", "")) * 1_000_000
            elif "K" in v:
                return float(v.replace("K", "")) * 1_000
            return float(v)
        except Exception:
            return 0.0

    # -- custom execute (sets tab/limit/market cap before extraction) -------

    async def execute(self, ticker: str = None, asset_class: str = None) -> Dict:
        command_str = self.get_command_string()
        previous_count = len(await self.session.get_current_windows())

        logger.info(f"Executing: {command_str}  tab={self.tab} limit={self.limit}")

        if not await self.session.send_command(command_str):
            return {"success": False, "error": "Failed to send command", "command": command_str}

        self.window = await self.session.wait_for_new_window(previous_count, timeout=10000)
        if not self.window:
            return {"success": False, "error": "No new window", "command": command_str}

        self.window_id = await self.window.get_attribute("id")
        await self.page.wait_for_timeout(2000)

        # Configure filters
        if self.tab != "ACTIVE":
            await self._select_tab(self.tab)
        await self._set_limit(self.limit)
        await self._set_min_market_cap("FIFTY_BILLION")
        await self.page.wait_for_timeout(3000)

        try:
            data = await self.extract_data()
        except Exception as e:
            logger.error(f"Extraction error: {e}", exc_info=True)
            await self.session.screenshot(f"output/most_error.png")
            return {"success": False, "error": str(e), "window_id": self.window_id}

        if "error" in data:
            return {"success": False, "error": data["error"], "window_id": self.window_id}

        return {"success": True, "command": command_str, "data": data}

    # -- save helpers -------------------------------------------------------

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
