"""
EM Command - Earnings Matrix
"""
import asyncio
from typing import Optional


class EMCommand:
    """Execute EM command for earnings data."""
    
    def __init__(self, session):
        self.session = session
        self.page = session.page
        
    async def execute(self, ticker: str, asset_class: str = "EQ") -> dict:
        """Execute EM command and extract earnings data."""
        try:
            # Open command palette
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
            await self.page.keyboard.press("x")
            await asyncio.sleep(0.5)
            
            # Type EM command
            cmd = f"{ticker} {asset_class} EM"
            await self.page.keyboard.type(cmd)
            await asyncio.sleep(0.5)
            await self.page.keyboard.press("Enter")
            await asyncio.sleep(3)
            
            result = {
                "success": True,
                "ticker": ticker,
                "asset_class": asset_class,
                "data": {}
            }
            
            # Look for Earnings Matrix window
            windows = await self.page.locator("[class*='window']").all()
            em_window = None
            
            for w in windows:
                try:
                    title_elem = w.locator("[class*='title'], [class*='header']").first
                    if await title_elem.count() > 0:
                        title = await title_elem.inner_text()
                        if "Earnings" in title or "Matrix" in title:
                            em_window = w
                            break
                except:
                    continue
            
            if em_window:
                content = await em_window.inner_text()
                result["data"]["window_title"] = title if 'title' in locals() else "Earnings Matrix"
                result["data"]["content_preview"] = content[:3000] if content else ""
                
                # Extract EPS estimates and actuals
                eps_data = {}
                lines = content.split("\n") if content else []
                
                for i, line in enumerate(lines):
                    line = line.strip()
                    if "EPS" in line or "Earnings" in line or "Q" in line[:2]:
                        eps_data[f"line_{i}"] = line
                
                result["data"]["eps_lines"] = eps_data
                
                # Close window
                try:
                    close_btn = em_window.locator("button:has-text('Close'), [class*='close']").first
                    if await close_btn.count() > 0:
                        await close_btn.click()
                        await asyncio.sleep(0.5)
                except:
                    pass
            
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e), "ticker": ticker}
