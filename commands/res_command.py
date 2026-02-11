"""
RES (Research) Command — Smart text parser
"""

import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

from godel_core import BaseCommand, GodelSession

logger = logging.getLogger("godel.res")

# Known providers to help with parsing
KNOWN_PROVIDERS = [
    'Truist Securities', 'JPMorgan', 'J.P. Morgan', 'KeyBanc Capital Markets',
    'RBC Capital Markets', 'Jefferies', 'Goldman Sachs', 'Morgan Stanley',
    'Bank of America', 'UBS', 'Deutsche Bank', 'Wells Fargo Securities',
    'William Blair', 'KB Securities', 'Fubon Research', 'CLSA',
    'Asia Pacific Equity Research', 'Morning Notes'
]


class RESCommand(BaseCommand):
    """Research (RES) command — extracts research from concatenated text."""

    def __init__(self, session: GodelSession, download_pdfs: bool = False,
                 output_dir: str = "output/pdfs", db_path: Optional[str] = None):
        super().__init__(session)
        self.download_pdfs = download_pdfs
        self.output_dir = output_dir
        self.db_path = db_path

    def get_command_string(self, ticker: str = None, asset_class: str = None) -> str:
        return "RES"

    async def extract_data(self) -> Dict:
        if not self.window:
            raise ValueError("No window available")

        await self.page.wait_for_timeout(3000)

        # Extract text and parse
        text = await self.window.text_content()
        
        # Parse research items from text
        items = self._parse_research_text(text)
        
        return {
            "success": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "window_id": self.window_id,
            "research_items_found": len(items),
            "items": items[:50],
        }

    def _parse_research_text(self, text: str) -> List[Dict]:
        """Parse research items from concatenated text."""
        items = []
        
        # Find where actual data starts (after "Title")
        if "Title" in text:
            text = text.split("Title", 1)[1]
        
        # Find all date positions
        import re
        date_pattern = r'\d{4}-\d{2}-\d{2}'
        dates = list(re.finditer(date_pattern, text))
        
        for i, date_match in enumerate(dates):
            try:
                date = date_match.group(0)
                start_pos = date_match.end()  # Start after the date
                
                # End at next date or end of text
                if i + 1 < len(dates):
                    end_pos = dates[i + 1].start()
                else:
                    end_pos = len(text)
                
                entry = text[start_pos:end_pos]
                
                # Skip if entry starts with another date (overlap issue)
                if re.match(r'^\d{4}-\d{2}-\d{2}', entry):
                    entry = entry[10:]  # Skip the duplicate date
                
                # Try to find ticker at start of entry
                # Tickers usually have format: SYMBOL.XX (like RCUS.US, AAPL.US)
                ticker_match = re.match(r'^([A-Z][A-Z]+\.[A-Z]{2})', entry)
                
                if ticker_match:
                    ticker = ticker_match.group(1)
                    remaining = entry[len(ticker):]
                else:
                    # No ticker found - use placeholder
                    ticker = "N/A"
                    remaining = entry
                
                # Find provider
                provider = "Unknown"
                title = remaining
                
                for prov in KNOWN_PROVIDERS:
                    if prov in remaining:
                        provider = prov
                        title = remaining.split(prov, 1)[1].strip()
                        break
                
                # Clean up title
                title = title.replace('INVITE:', '').replace('First Take:', '').strip()
                
                # Only add if we have meaningful content
                if title and len(title) > 5:
                    items.append({
                        "date": date,
                        "ticker": ticker,
                        "provider": provider,
                        "title": title[:150],
                    })
                
            except Exception as e:
                logger.debug(f"Error parsing entry {i}: {e}")
                continue
        
        return items
