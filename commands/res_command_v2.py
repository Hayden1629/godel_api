"""
RES (Research) Command — Text-based extraction
Parses research data from text content
"""

import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

from godel_core import BaseCommand, GodelSession

logger = logging.getLogger("godel.res")


class RESCommand(BaseCommand):
    """Research (RES) command — extracts research list from text."""

    def __init__(self, session: GodelSession, download_pdfs: bool = False,
                 output_dir: str = "output/pdfs", db_path: Optional[str] = None):
        super().__init__(session)
        self.download_pdfs = download_pdfs
        self.output_dir = output_dir
        self.db_path = db_path
        self.research_items: List[Dict] = []

    def get_command_string(self, ticker: str = None, asset_class: str = None) -> str:
        return "RES"

    async def extract_data(self) -> Dict:
        if not self.window:
            raise ValueError("No window available")

        await self.page.wait_for_timeout(3000)

        # Extract research items from text content
        self.research_items = await self._extract_from_text()

        return {
            "success": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "window_id": self.window_id,
            "research_items_found": len(self.research_items),
            "items": self.research_items[:100],  # Return first 100
        }

    async def _extract_from_text(self) -> List[Dict]:
        """Extract research items by parsing text content."""
        items = []
        
        try:
            # Get all text from the window
            text = await self.window.text_content()
            
            # The format is: Research Beta ... Date ▼TickerProviderTitle
            # Then: YYYY-MM-DDTICKERPROVIDERTITLE
            
            # Find the research data section (after "Title")
            if "Title" in text:
                data_section = text.split("Title", 1)[1]
            else:
                data_section = text
            
            # Pattern: Date (YYYY-MM-DD) followed by ticker, provider, title
            # Use regex to find date patterns and extract entries
            date_pattern = r'(\d{4}-\d{2}-\d{2})'
            
            # Find all date positions
            matches = list(re.finditer(date_pattern, data_section))
            
            for i, match in enumerate(matches):
                try:
                    date = match.group(1)
                    start_pos = match.start()
                    
                    # Get text from this date to next date (or end)
                    if i + 1 < len(matches):
                        end_pos = matches[i + 1].start()
                        entry_text = data_section[start_pos:end_pos]
                    else:
                        entry_text = data_section[start_pos:]
                    
                    # Parse the entry
                    # Format: DATETICKERPROVIDERTITLE
                    # Try to identify ticker (usually has . like RCUS.US)
                    lines = entry_text.split('\n')
                    entry_line = lines[0] if lines else entry_text
                    
                    # Try to extract components
                    # After date, look for ticker pattern (alphanumeric with optional dots)
                    ticker_match = re.search(r'\d{4}-\d{2}-\d{2}([A-Z][A-Za-z0-9\.]+)', entry_line)
                    
                    if ticker_match:
                        ticker = ticker_match.group(1)
                        # Everything after ticker is provider + title
                        remaining = entry_line[entry_line.find(ticker) + len(ticker):]
                        
                        # Provider is usually a known firm name
                        providers = ['Truist Securities', 'JPMorgan', 'KeyBanc', 'RBC', 'Jefferies', 
                                    'Goldman Sachs', 'Morgan Stanley', 'Bank of America', 'UBS', 'Deutsche Bank']
                        
                        provider = "Unknown"
                        title = remaining
                        
                        for prov in providers:
                            if prov in remaining:
                                provider = prov
                                title = remaining.replace(prov, "", 1).strip()
                                break
                        
                        items.append({
                            "date": date,
                            "ticker": ticker,
                            "provider": provider,
                            "title": title[:200],  # Limit length
                            "raw": entry_line[:300]
                        })
                
                except Exception as e:
                    logger.debug(f"Error parsing entry: {e}")
                    continue
            
            logger.info(f"Extracted {len(items)} research items from text")
            
        except Exception as e:
            logger.error(f"Error extracting research: {e}")
        
        return items
