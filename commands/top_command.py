"""
TOP Command - Top movers, gainers, losers
"""
import asyncio
import pandas as pd
from typing import Optional


class TOPCommand:
    """Execute TOP command to get top movers."""
    
    def __init__(self, session, tab: str = "GAINERS", limit: int = 50):
        self.session = session
        self.page = session.page
        self.tab = tab
        self.limit = limit
        self.df = None
        
    async def execute(self) -> dict:
        """Execute TOP command and extract data."""
        try:
            # Open command palette
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
            await self.page.keyboard.press("x")
            await asyncio.sleep(0.5)
            
            # Type TOP command
            await self.page.keyboard.type("TOP")
            await asyncio.sleep(0.5)
            await self.page.keyboard.press("Enter")
            await asyncio.sleep(3)
            
            result = {
                "success": True,
                "tab": self.tab,
                "limit": self.limit,
                "data": []
            }
            
            # Look for Top Movers window
            windows = await self.page.locator("[class*='window']").all()
            top_window = None
            
            for w in windows:
                try:
                    title_elem = w.locator("[class*='title'], [class*='header']").first
                    if await title_elem.count() > 0:
                        title = await title_elem.inner_text()
                        if "Top" in title or "Movers" in title:
                            top_window = w
                            break
                except:
                    continue
            
            if top_window:
                # Extract table data
                rows = await top_window.locator("tr").all()
                data = []
                
                for row in rows[:self.limit + 1]:  # +1 for header
                    cells = await row.locator("td, th").all_inner_texts()
                    if cells:
                        data.append(cells)
                
                result["data"] = data
                
                # Create DataFrame
                if len(data) > 1:
                    self.df = pd.DataFrame(data[1:], columns=data[0] if data[0] else None)
                
                # Close window
                try:
                    close_btn = top_window.locator("button:has-text('Close'), [class*='close']").first
                    if await close_btn.count() > 0:
                        await close_btn.click()
                        await asyncio.sleep(0.5)
                except:
                    pass
            
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def save_to_csv(self, filename: str):
        """Save data to CSV."""
        if self.df is not None:
            self.df.to_csv(filename, index=False)
    
    def save_to_json(self, filename: str):
        """Save data to JSON."""
        if self.df is not None:
            self.df.to_json(filename, orient="records")
