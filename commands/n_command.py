"""
N Command - News
"""
import asyncio
from typing import Optional


class NCommand:
    """Execute N command for news."""
    
    def __init__(self, session):
        self.session = session
        self.page = session.page
        
    async def execute(self, ticker: Optional[str] = None, asset_class: str = "EQ") -> dict:
        """Execute N command and extract news."""
        try:
            # Open command palette
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
            await self.page.keyboard.press("x")
            await asyncio.sleep(0.5)
            
            # Type N command
            if ticker:
                cmd = f"{ticker} {asset_class} N"
            else:
                cmd = "N"
            
            await self.page.keyboard.type(cmd)
            await asyncio.sleep(0.5)
            await self.page.keyboard.press("Enter")
            await asyncio.sleep(3)
            
            result = {
                "success": True,
                "ticker": ticker,
                "asset_class": asset_class,
                "news": []
            }
            
            # Look for News window
            windows = await self.page.locator("[class*='window']").all()
            news_window = None
            
            for w in windows:
                try:
                    title_elem = w.locator("[class*='title'], [class*='header']").first
                    if await title_elem.count() > 0:
                        title = await title_elem.inner_text()
                        if "News" in title:
                            news_window = w
                            break
                except:
                    continue
            
            if news_window:
                # Extract news items
                content = await news_window.inner_text()
                result["content_preview"] = content[:3000] if content else ""
                
                # Try to extract news headlines
                headlines = []
                lines = content.split("\n") if content else []
                
                for line in lines:
                    line = line.strip()
                    # News headlines often have dates/times
                    if len(line) > 20 and any(x in line for x in ["2024", "2025", "2026", "AM", "PM", "ET"]):
                        headlines.append(line)
                
                result["headlines"] = headlines[:20]  # First 20 headlines
                
                # Close window
                try:
                    close_btn = news_window.locator("button:has-text('Close'), [class*='close']").first
                    if await close_btn.count() > 0:
                        await close_btn.click()
                        await asyncio.sleep(0.5)
                except:
                    pass
            
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e), "ticker": ticker}
