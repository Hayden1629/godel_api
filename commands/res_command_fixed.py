"""
RES (Research) Command — Fixed version
Opens the RES window and extracts research data
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from godel_core import BaseCommand, GodelSession
from db import get_db

logger = logging.getLogger("godel.res")


class RESCommand(BaseCommand):
    """Research (RES) command — extracts research list."""

    def __init__(self, session: GodelSession, download_pdfs: bool = False,
                 output_dir: str = "output/pdfs", db_path: Optional[str] = None):
        super().__init__(session)
        self.download_pdfs = download_pdfs
        self.output_dir = output_dir
        self.db_path = db_path
        self.research_items: List[Dict] = []

    def get_command_string(self, ticker: str = None, asset_class: str = None) -> str:
        # RES command opens general research feed
        # For ticker-specific, may need to filter after opening
        return "RES"

    async def extract_data(self) -> Dict:
        if not self.window:
            raise ValueError("No window available")

        await self.page.wait_for_timeout(3000)

        # Extract research items from the table
        self.research_items = await self._extract_research_list()

        return {
            "success": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "window_id": self.window_id,
            "research_items_found": len(self.research_items),
            "items": self.research_items[:50],  # Return first 50
        }

    async def _extract_research_list(self) -> List[Dict]:
        """Extract research items from the RES table."""
        items = []
        
        try:
            # Try to find grid/table rows - RES uses grid layout
            row_selectors = [
                "[class*='grid'] > div",  # Grid direct children
                "[class*='row']",  # Row classes
                "[role='row']",  # ARIA rows
                "tr",  # Standard table
            ]
            
            for selector in row_selectors:
                try:
                    rows = await self.window.locator(selector).all()
                    logger.info(f"Selector '{selector}' found {len(rows)} elements")
                    
                    if len(rows) > 5:  # Likely data rows (not just header)
                        for row in rows:
                            try:
                                # Get text content of the row
                                text = await row.text_content()
                                if not text:
                                    continue
                                
                                # Try to get child elements (columns)
                                children = await row.locator("*").all()
                                if len(children) >= 4:
                                    # Assume columns: Date, Ticker, Provider, Title
                                    values = []
                                    for child in children[:4]:
                                        val = await child.text_content()
                                        values.append(val.strip() if val else "")
                                    
                                    if values[0] and values[1]:  # Must have date and ticker
                                        items.append({
                                            "date": values[0],
                                            "ticker": values[1],
                                            "provider": values[2] if len(values) > 2 else "",
                                            "title": values[3] if len(values) > 3 else "",
                                        })
                                elif text.strip():
                                    # Fallback: try to parse text line
                                    parts = text.strip().split()
                                    if len(parts) >= 4:
                                        # Guess: first is date, second is ticker
                                        items.append({
                                            "date": parts[0],
                                            "ticker": parts[1],
                                            "provider": parts[2] if len(parts) > 2 else "",
                                            "title": " ".join(parts[3:]) if len(parts) > 3 else "",
                                        })
                            except Exception as e:
                                logger.debug(f"Error parsing row: {e}")
                                continue
                        
                        if items:
                            logger.info(f"Extracted {len(items)} items with selector: {selector}")
                            break
                            
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            # If no items found, try simple text extraction
            if not items:
                logger.info("Trying simple text extraction...")
                all_text = await self.window.text_content()
                # Look for lines that look like research items
                lines = all_text.split('\n')
                for line in lines:
                    # Check if line looks like a research entry (date pattern)
                    if any(x in line for x in ['2026-', '2025-', 'JPMorgan', 'Truist', 'RBC']):
                        items.append({"raw": line.strip()})
                        
        except Exception as e:
            logger.error(f"Error extracting research list: {e}")
        
        logger.info(f"Extracted {len(items)} research items total")
        return items
