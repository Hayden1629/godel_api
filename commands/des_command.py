"""
DES (Description) Command — async Playwright
Extracts company info, description, EPS estimates, analyst ratings, snapshot
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from godel_core import BaseCommand, GodelSession

logger = logging.getLogger("godel.des")


class DESCommand(BaseCommand):
    """Description (DES) command — extracts company information."""

    def get_command_string(self, ticker: str = None, asset_class: str = None) -> str:
        return f"{ticker} {asset_class or 'EQ'} DES"

    # -- helpers ------------------------------------------------------------

    async def _expand_description(self):
        try:
            see_more = self.window.locator("a.cursor-pointer:has-text('See more')").first
            if await see_more.count() > 0:
                await see_more.click()
                await self.page.wait_for_timeout(500)
        except Exception as e:
            logger.debug(f"See more not found or failed: {e}")

    async def _expand_analyst_ratings(self):
        try:
            show_all = self.window.locator("div.cursor-pointer.p-2:has-text('Show all')").first
            if await show_all.count() > 0:
                await show_all.evaluate("el => el.click()")
                await self.page.wait_for_timeout(500)
        except Exception as e:
            logger.debug(f"Show all not found or failed: {e}")

    # -- extraction ---------------------------------------------------------

    async def extract_data(self) -> Dict:
        if not self.window:
            raise ValueError("No window available")

        await self._expand_description()
        await self._expand_analyst_ratings()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "window_id": self.window_id,
            "ticker": await self._extract_ticker(),
            "company_info": await self._extract_company_header(),
            "description": await self._extract_description(),
            "eps_estimates": await self._extract_eps_estimates(),
            "analyst_ratings": await self._extract_analyst_ratings(),
            "snapshot": await self._extract_snapshot(),
        }

    async def _extract_ticker(self) -> Optional[str]:
        try:
            inp = self.window.locator("input.uppercase").first
            return await inp.input_value()
        except Exception:
            return None

    async def _extract_company_header(self) -> Dict:
        data: Dict = {}
        try:
            h1 = self.window.locator("h1.text-2xl").first
            full_text = await h1.inner_text()
            # Strip badge text
            badge = h1.locator("span.blue-box").first
            if await badge.count() > 0:
                badge_text = await badge.inner_text()
                data["company_name"] = full_text.replace(badge_text, "").strip()
                data["asset_class"] = badge_text.strip()
            else:
                data["company_name"] = full_text.strip()
                data["asset_class"] = None
        except Exception as e:
            logger.debug(f"Company header: {e}")
            data.setdefault("company_name", None)
            data.setdefault("asset_class", None)

        # Logo
        try:
            logo_div = self.window.locator("div.w-16.h-16").first
            style = await logo_div.get_attribute("style") or ""
            if "background-image" in style:
                url_part = style.split("url(")[1].split(")")[0].strip("\"' ")
                data["logo_url"] = url_part
            else:
                data["logo_url"] = None
        except Exception:
            data["logo_url"] = None

        # Website
        try:
            link = self.window.locator("a[target='_blank'][href]").first
            data["website"] = await link.get_attribute("href")
        except Exception:
            data["website"] = None

        # Address / CEO
        try:
            info_div = self.window.locator("div.text-right.uppercase").first
            text = await info_div.inner_text()
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            data["address"] = lines[0] if lines else None
            data["ceo"] = lines[1] if len(lines) > 1 else None
        except Exception:
            data.setdefault("address", None)
            data.setdefault("ceo", None)

        return data

    async def _extract_description(self) -> Optional[str]:
        try:
            divs = await self.window.locator("div[style*='color: rgb(234, 234, 234)']").all()
            for div in divs:
                text = (await div.inner_text()).strip()
                if len(text) > 100:
                    return text.replace("See more", "").replace("See less", "").strip()
        except Exception as e:
            logger.debug(f"Description: {e}")
        return None

    async def _extract_eps_estimates(self) -> Dict:
        eps: Dict = {}
        try:
            table = self.window.locator("xpath=.//span[text()='EPS ESTIMATES']/ancestor::div[1]/following-sibling::table").first
            # Headers
            headers = []
            header_cells = await table.locator("thead td").all()
            for cell in header_cells:
                t = (await cell.inner_text()).strip()
                if t:
                    headers.append(t)

            # Body rows
            rows = await table.locator("tbody tr").all()
            date_row = []
            eps_row = []
            for row in rows:
                cells = await row.locator("td").all()
                if not cells:
                    continue
                label = (await cells[0].inner_text()).strip().lower()
                if label == "date":
                    date_row = [(await c.inner_text()).strip() for c in cells[1:]]
                elif label == "eps":
                    eps_row = [(await c.inner_text()).strip() for c in cells[1:]]

            if date_row and eps_row and headers:
                for i, hdr in enumerate(headers):
                    if i < len(date_row) and i < len(eps_row):
                        eps[f"{hdr}, {date_row[i]}"] = eps_row[i]
        except Exception as e:
            logger.debug(f"EPS: {e}")
        return eps

    async def _extract_analyst_ratings(self) -> List[Dict]:
        ratings: List[Dict] = []
        try:
            table = self.window.locator(
                "xpath=.//span[text()='ANALYST RATINGS']/ancestor::div[1]/following-sibling::div[@class='w-full']//table"
            ).first
            rows = await table.locator("tbody tr").all()
            for row in rows:
                cells = await row.locator("td").all()
                if len(cells) < 5:
                    continue
                firm = (await cells[0].inner_text()).strip()
                if not firm:
                    continue
                # Target price spans
                target_spans = await cells[3].locator("span").all()
                old_target = (await target_spans[0].inner_text()).strip() if target_spans else ""
                new_target = old_target
                if len(target_spans) >= 3:
                    new_target = (await target_spans[-1].inner_text()).strip()
                elif len(target_spans) == 2:
                    new_target = (await target_spans[1].inner_text()).strip()

                rating = {
                    "Firm": firm,
                    "Analyst": (await cells[1].inner_text()).strip(),
                    "Rating": (await cells[2].inner_text()).strip(),
                    "Old_Target": old_target,
                    "New_Target": new_target,
                    "Date": (await cells[4].inner_text()).strip(),
                }
                if rating["Firm"] and rating["Analyst"] and rating["Rating"]:
                    ratings.append(rating)
        except Exception as e:
            logger.debug(f"Analyst ratings: {e}")
        return ratings

    async def _extract_snapshot(self) -> Dict:
        snapshot: Dict = {}
        try:
            snap_div = self.window.locator(
                "xpath=.//div[text()='SNAPSHOT']/following-sibling::div[@class='flex-1']"
            ).first
            pairs = await snap_div.locator("div.flex.justify-between.text-sm").all()
            for pair in pairs:
                spans = await pair.locator("span").all()
                if len(spans) >= 2:
                    key = (await spans[0].inner_text()).strip()
                    # Check for abbr
                    abbr = spans[1].locator("abbr").first
                    if await abbr.count() > 0:
                        value = (await abbr.get_attribute("title")) or (await abbr.inner_text()).strip()
                    else:
                        value = (await spans[1].inner_text()).strip()
                    if key and value:
                        snapshot[key] = value
        except Exception as e:
            logger.debug(f"Snapshot: {e}")
        return snapshot
