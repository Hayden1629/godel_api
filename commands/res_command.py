"""
RES (Research) Command — async Playwright
Opens the RES window and downloads PDFs
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from godel_core import BaseCommand, GodelSession
from db import get_db

logger = logging.getLogger("godel.res")


class RESCommand(BaseCommand):
    """Research (RES) command — lists and downloads research PDFs."""

    def __init__(self, session: GodelSession, download_pdfs: bool = True,
                 output_dir: str = "output/pdfs", db_path: Optional[str] = None):
        super().__init__(session)
        self.download_pdfs = download_pdfs
        self.output_dir = output_dir
        self.db_path = db_path
        self.downloaded_files: List[Dict] = []

    def get_command_string(self, ticker: str = None, asset_class: str = None) -> str:
        return f"{ticker} {asset_class or 'EQ'} RES"

    async def extract_data(self) -> Dict:
        if not self.window:
            raise ValueError("No window available")

        await self.page.wait_for_timeout(2000)

        pdf_links = await self._find_pdf_links()
        downloaded = []

        if self.download_pdfs and pdf_links:
            downloaded = await self._download_pdfs(pdf_links)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "window_id": self.window_id,
            "pdf_links_found": len(pdf_links),
            "pdfs_downloaded": len(downloaded),
            "files": downloaded,
        }

    async def _find_pdf_links(self) -> List[Dict]:
        """Find all PDF links in the RES window."""
        links = []
        try:
            # Look for anchor tags with pdf-like hrefs or text
            anchors = await self.window.locator("a[href]").all()
            for a in anchors:
                href = await a.get_attribute("href") or ""
                text = (await a.inner_text()).strip()
                if ".pdf" in href.lower() or "pdf" in text.lower() or "research" in text.lower():
                    links.append({"href": href, "text": text})

            # Also look for clickable elements that might trigger downloads
            buttons = await self.window.locator("button:has-text('PDF'), button:has-text('Download'), [class*='download']").all()
            for btn in buttons:
                text = (await btn.inner_text()).strip()
                links.append({"href": None, "text": text, "element": btn})

            logger.info(f"Found {len(links)} potential PDF links")
        except Exception as e:
            logger.error(f"Error finding PDF links: {e}")

        return links

    async def _download_pdfs(self, links: List[Dict]) -> List[Dict]:
        """Download PDFs using Playwright's download handling."""
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        downloaded = []
        db = await get_db(self.db_path)

        for link_info in links:
            try:
                href = link_info.get("href")
                if href and href.startswith("http"):
                    # Direct link — trigger download via navigation
                    async with self.page.expect_download(timeout=30000) as download_info:
                        # Open in new tab to avoid navigating away
                        await self.page.evaluate(f"window.open('{href}', '_blank')")
                    download = await download_info.value
                elif "element" in link_info:
                    # Click-triggered download
                    async with self.page.expect_download(timeout=30000) as download_info:
                        await link_info["element"].click()
                    download = await download_info.value
                else:
                    continue

                # Save to output dir
                filename = download.suggested_filename or f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                save_path = str(Path(self.output_dir) / filename)
                await download.save_as(save_path)

                file_record = {
                    "filename": filename,
                    "filepath": save_path,
                    "source_text": link_info.get("text", ""),
                    "source_url": href or "",
                }
                downloaded.append(file_record)

                # Record in DB
                await db.save_pdf_record(
                    ticker=self.window_id or "unknown",
                    command="RES",
                    filename=filename,
                    filepath=save_path,
                )

                logger.info(f"Downloaded: {filename}")

            except Exception as e:
                logger.warning(f"Download failed for {link_info.get('text', '?')}: {e}")
                continue

        self.downloaded_files = downloaded
        return downloaded
